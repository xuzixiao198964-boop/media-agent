import tempfile
import asyncio
from datetime import datetime
from pathlib import Path

from celery import Celery
from sqlalchemy import select

from app.config import get_settings
from app.db_sync import SessionLocal
from app.models import Article, Category, GenerationJob, PublishJob, UserVideo, VoicePrint
from app.services.ai_text import build_narration, build_script_from_user_prompt
from app.services.audio_mix import loop_bgm_to_length, mix_voice_and_bgm
from app.services.flow_log import log_sync
from app.services.publisher import run_publish
from app.services.render_video import render_short_video
from app.services.rss_fetch import fetch_category_rss
from app.services.tts_audio import ffprobe_duration, has_audio_stream, synthesize_speech
from app.services.vrs_voice_clone import clone_voiceprint_vrs_one_sentence
from app.services.keyvault import get_provider_key_sync
from app.services.videoretalk import create_videoretalk_task, download_file, wait_videoretalk_task

settings = get_settings()
celery_app = Celery(
    "media_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


@celery_app.task(name="fetch_all_categories")
def fetch_all_categories():
    db = SessionLocal()
    try:
        cats = db.execute(select(Category).where(Category.is_active.is_(True))).scalars().all()
        total = 0
        for c in cats:
            n = fetch_category_rss(db, c)
            total += n
            log_sync(db, "category", c.id, "rss_fetch", f"栏目 {c.slug} 新增 {n} 条", "info")
        return {"added": total}
    finally:
        db.close()


@celery_app.task(name="fetch_category", bind=True)
def fetch_category_task(self, category_id: int):
    db = SessionLocal()
    try:
        c = db.get(Category, category_id)
        if not c:
            return {"error": "category not found"}
        n = fetch_category_rss(db, c)
        log_sync(db, "category", c.id, "rss_fetch", f"手动触发：新增 {n} 条", "info")
        return {"added": n}
    finally:
        db.close()


@celery_app.task(name="run_generation_job", bind=True)
def run_generation_job_task(self, job_id: int):
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if not job:
            return {"error": "job not found"}
        job.status = "processing"
        db.commit()
        log_sync(db, "generation_job", job.id, "start", "开始生成短视频", "info")

        video = db.get(UserVideo, job.user_video_id)
        if not video:
            job.status = "failed"
            job.error = "关联视频不存在"
            db.commit()
            return {"error": job.error}

        meta = job.meta or {}
        generation_mode = meta.get("generation_mode", "article")
        audio_mode = meta.get("audio_mode", "tts")
        lip_sync = bool(meta.get("lip_sync", True))

        if generation_mode == "article":
            article = db.get(Article, job.article_id)
            if not article:
                job.status = "failed"
                job.error = "关联文章不存在"
                db.commit()
                return {"error": job.error}
            narration = build_narration(
                db,
                article.title,
                article.summary or "",
                article.body or "",
            )
            banner_title = article.title
            banner_summary = article.summary or ""
        else:
            script_source = meta.get("script_source", "deepseek")
            if script_source == "direct":
                narration = (meta.get("direct_script") or "").strip()
            else:
                narration = build_script_from_user_prompt(db, meta.get("user_prompt") or "")
            banner_title = (meta.get("display_title") or "").strip() or "短视频"
            banner_summary = ""

        job.narration_text = narration
        db.commit()

        upload_root = Path(settings.upload_dir)
        in_path = Path(video.stored_path)
        if not in_path.is_file():
            in_path = upload_root / video.stored_path
        if not in_path.is_file():
            job.status = "failed"
            job.error = f"找不到上传文件: {in_path}"
            db.commit()
            return {"error": job.error}

        out_dir = Path(settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_mp4 = out_dir / f"job_{job.id}.mp4"
        voice_mp3 = out_dir / f"job_{job.id}.mp3"

        tts_language = (meta.get("tts_language") or "zh-CN").strip()
        voice_profile_id = meta.get("voice_profile_id")
        tencent_fast_voice_type = None
        tencent_voice_type = None
        if voice_profile_id:
            vp = db.get(VoicePrint, int(voice_profile_id))
            if vp and vp.user_id == job.user_id:
                if vp.status != "ready" or not (vp.fast_voice_type or vp.voice_type):
                    job.status = "failed"
                    job.error = f"声纹未就绪：{vp.status}"
                    db.commit()
                    log_sync(db, "generation_job", job.id, "voice_not_ready", job.error, "error")
                    return {"error": job.error}
                tencent_fast_voice_type = vp.fast_voice_type
                tencent_voice_type = vp.voice_type

        bgm_vol = float(meta.get("bgm_volume") or 0.22)
        final_audio = voice_mp3
        mixed_mp3 = out_dir / f"job_{job.id}_mixed.mp3"

        if audio_mode == "bgm_only":
            bgm_file = Path(settings.default_bgm_path) if (settings.default_bgm_path or "").strip() else None
            if not bgm_file or not bgm_file.is_file():
                job.status = "failed"
                job.error = "未配置有效背景音乐文件（default_bgm_path）"
                db.commit()
                return {"error": job.error}
            vdur = ffprobe_duration(in_path) or 60.0
            vdur = min(max(vdur, 2.0), 120.0)
            try:
                loop_bgm_to_length(bgm_file, vdur, voice_mp3)
            except Exception as e:
                job.status = "failed"
                job.error = f"背景音乐铺底失败: {e}"
                db.commit()
                return {"error": job.error}
            final_audio = voice_mp3
        else:
            try:
                synthesize_speech(
                    db,
                    narration,
                    voice_mp3,
                    language=tts_language,
                    tencent_voice_type=tencent_voice_type,
                    tencent_fast_voice_type=tencent_fast_voice_type,
                )
            except Exception as e:
                job.status = "failed"
                job.error = f"TTS 失败: {e}"
                db.commit()
                log_sync(db, "generation_job", job.id, "tts_fail", str(e), "error")
                return {"error": str(e)}

            if audio_mode == "tts_bgm":
                bgm_file = Path(settings.default_bgm_path) if (settings.default_bgm_path or "").strip() else None
                if not bgm_file or not bgm_file.is_file():
                    job.status = "failed"
                    job.error = "未配置有效背景音乐文件（default_bgm_path）"
                    db.commit()
                    return {"error": job.error}
                try:
                    mix_voice_and_bgm(
                        voice_mp3,
                        bgm_file,
                        mixed_mp3,
                        voice_volume=1.0,
                        bgm_volume=bgm_vol,
                    )
                    final_audio = mixed_mp3
                except Exception as e:
                    job.status = "failed"
                    job.error = f"口播与背景音乐混音失败: {e}"
                    db.commit()
                    return {"error": str(e)}

        # 如果配置了阿里云 VideoRetalk Key，则用它生成“口型匹配视频”
        dashscope_key = get_provider_key_sync(db, "dashscope_api_key")
        use_videoretalk = bool(dashscope_key) and lip_sync and audio_mode != "bgm_only"
        if use_videoretalk:
            # VideoRetalk 约束：视频/音频时长需在 2~120 秒
            if video.duration_sec is not None and (video.duration_sec < 2.0 or video.duration_sec > 120.0):
                job.status = "failed"
                job.error = f"VideoRetalk 不支持该视频时长：{video.duration_sec:.2f}s（需 2~120s）"
                db.commit()
                log_sync(db, "generation_job", job.id, "retalk_bad_video_duration", job.error, "error")
                log_sync(db, "api", None, "dashscope_videoretalk", job.error, "error")
                return {"error": job.error}
            voice_dur = ffprobe_duration(final_audio)
            if voice_dur is not None and (voice_dur < 2.0 or voice_dur > 120.0):
                job.status = "failed"
                job.error = f"VideoRetalk 不支持该音频时长：{voice_dur:.2f}s（需 2~120s）"
                db.commit()
                log_sync(db, "generation_job", job.id, "retalk_bad_audio_duration", job.error, "error")
                log_sync(db, "api", None, "dashscope_videoretalk", job.error, "error")
                return {"error": job.error}

            retalk_video_path = out_dir / f"job_{job.id}_retalk.mp4"
            try:
                web_base_url = settings.public_base_url
                task_id = asyncio.run(
                    create_videoretalk_task(
                        api_key=dashscope_key,
                        web_base_url=web_base_url,
                        input_video_path=in_path,
                        input_audio_path=final_audio,
                        video_extension=False,
                    )
                )
                video_url = asyncio.run(
                    wait_videoretalk_task(api_key=dashscope_key, task_id=task_id, timeout_s=20 * 60)
                )
                asyncio.run(download_file(video_url, retalk_video_path))
                # 最后做你现有的横幅/竖屏输出处理（保持音轨为 voice_mp3）
                render_short_video(
                    retalk_video_path,
                    final_audio,
                    banner_title,
                    banner_summary,
                    narration,
                    out_mp4,
                    max_seconds=60.0,
                )
            except Exception as e:
                job.status = "failed"
                job.error = f"VideoRetalk 失败: {e}"
                db.commit()
                log_sync(db, "generation_job", job.id, "retalk_fail", str(e), "error")
                log_sync(db, "api", None, "dashscope_videoretalk", str(e), "error")
                return {"error": str(e)}
        else:
            try:
                render_short_video(
                    in_path,
                    final_audio,
                    banner_title,
                    banner_summary,
                    narration,
                    out_mp4,
                    max_seconds=60.0,
                )
            except Exception as e:
                job.status = "failed"
                job.error = f"渲染失败: {e}"
                db.commit()
                log_sync(db, "generation_job", job.id, "render_fail", str(e), "error")
                return {"error": str(e)}

        if not has_audio_stream(out_mp4):
            job.status = "failed"
            job.error = "渲染结果缺少音轨，请检查 TTS 配置或网络"
            db.commit()
            log_sync(db, "generation_job", job.id, "audio_missing", job.error, "error")
            return {"error": job.error}

        job.output_path = str(out_mp4)
        job.status = "done"
        job.error = None
        job.meta = {**(job.meta or {}), "finished_at": datetime.utcnow().isoformat() + "Z"}
        db.commit()
        log_sync(db, "generation_job", job.id, "done", f"输出 {out_mp4.name}", "info")
        return {"path": job.output_path}
    finally:
        db.close()


@celery_app.task(name="run_voice_clone_task", bind=True)
def run_voice_clone_task(self, voiceprint_id: int):
    db = SessionLocal()
    try:
        vp = db.get(VoicePrint, voiceprint_id)
        if not vp:
            return {"error": "voiceprint not found"}

        vp.status = "processing"
        vp.error = None
        db.commit()

        settings = get_settings()
        input_rel = vp.stored_path
        input_path = Path(settings.upload_dir) / input_rel
        if not input_path.is_file():
            vp.status = "failed"
            vp.error = f"找不到导入文件: {input_path}"
            db.commit()
            return {"error": vp.error}

        # One-sentence VRS 复刻：VRS 输出可用于 TTS FastVoiceType
        voice_name = f"voice_{vp.user_id}_{vp.id}"

        voice_type, fast_voice_type = clone_voiceprint_vrs_one_sentence(
            db,
            input_path=input_path,
            voice_name=voice_name,
            voice_gender=vp.voice_gender,
            voice_language=1,  # 当前仅实现中文
        )

        vp.tencent_vrs_task_id = vp.tencent_vrs_task_id or None
        vp.voice_type = voice_type
        vp.fast_voice_type = fast_voice_type
        vp.status = "ready"
        vp.error = None
        db.commit()
        log_sync(db, "voice_print", vp.id, "ready", f"FastVoiceType: {bool(fast_voice_type)}", "info")
        return {"status": "ready"}
    except Exception as e:
        if 'vp' in locals() and vp:
            vp.status = "failed"
            vp.error = str(e)
            db.commit()
            log_sync(db, "voice_print", vp.id, "failed", str(e), "error")
            return {"error": str(e)}
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="run_publish_job")
def run_publish_job_task(publish_job_id: int):
    db = SessionLocal()
    try:
        pj = db.get(PublishJob, publish_job_id)
        if not pj:
            return {"error": "publish job not found"}
        log_sync(db, "publish_job", pj.id, "start", f"平台 {pj.platform} 发布中", "info")
        run_publish(db, pj)
        log_sync(db, "publish_job", pj.id, pj.status, pj.error or "ok", "info" if pj.status == "success" else "error")
        return {"status": pj.status}
    finally:
        db.close()


# Celery beat 调度在 docker-compose 通过命令行配置，此处注册周期任务备用
@celery_app.on_after_configure.connect
def setup_periodic(sender, **kwargs):
    sender.add_periodic_task(
        settings.rss_fetch_interval_seconds,
        fetch_all_categories.s(),
        name="periodic rss fetch all",
    )
