"""小说视频生成 Celery 任务。"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db_sync import SessionLocal
from app.models import NovelChapter, NovelCharacter, NovelProject, BgmLibrary, ChapterReview
from app.services.flow_log import log_sync
from app.services.novel_script_gen import generate_script, extract_characters_from_script
from app.services.fish_audio_tts import synthesize_scene
from app.services.novel_compose import generate_scene_image, compose_chapter_video
from app.services.ai_video_gen import ai_image_to_video, batch_ai_image_to_video
from app.services.siliconflow_img import generate_image as siliconflow_generate
from app.services.prompt_review import review_prompts, regenerate_prompt, MAX_REVIEW_ROUNDS as PROMPT_MAX_ROUNDS
from app.services.image_review import review_images, MAX_REVIEW_ROUNDS as IMAGE_MAX_ROUNDS
from app.services.tts_audio import ffprobe_duration
from app.tasks import celery_app

settings = get_settings()
log = logging.getLogger(__name__)

MAX_PARALLEL_TTS = 4
MAX_PARALLEL_IMG = 2


@celery_app.task(name="generate_novel_script", bind=True)
def generate_novel_script_task(self, chapter_id: int):
    db = SessionLocal()
    try:
        ch = db.get(NovelChapter, chapter_id)
        if not ch:
            return {"error": "chapter not found"}

        proj = db.get(NovelProject, ch.project_id)
        if not proj:
            return {"error": "project not found"}

        ch.script_status = "generating"
        db.commit()

        chars = db.execute(
            select(NovelCharacter.name).where(NovelCharacter.project_id == proj.id)
        ).scalars().all()

        script = generate_script(
            db,
            chapter_title=ch.title,
            chapter_no=ch.chapter_no,
            raw_text=ch.raw_text or "",
            existing_characters=list(chars) if chars else None,
            review_notes=ch.script_review_notes if ch.script_status == "rejected" else None,
        )

        ch.script = script
        ch.script_status = "draft"
        ch.estimated_duration = script.get("estimated_duration_sec")
        ch.error = None
        db.commit()

        new_names = extract_characters_from_script(script)
        existing = set(chars)
        for name in new_names:
            if name not in existing:
                db.add(NovelCharacter(project_id=proj.id, name=name))
        db.commit()

        log_sync(db, "novel_chapter", ch.id, "script_done", f"脚本生成完成，{len(script.get('scenes', []))}个场景", "info")
        return {"status": "draft", "scenes": len(script.get("scenes", []))}
    except Exception as e:
        if "ch" in locals() and ch:
            ch.script_status = "pending"
            ch.error = str(e)[:2000]
            db.commit()
        log_sync(db, "novel_chapter", chapter_id, "script_fail", str(e), "error")
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="review_chapter_prompts", bind=True)
def review_chapter_prompts_task(self, chapter_id: int):
    """AI 评审章节分镜脚本中的图片提示词。"""
    db = SessionLocal()
    try:
        ch = db.get(NovelChapter, chapter_id)
        if not ch:
            return {"error": "chapter not found"}
        proj = db.get(NovelProject, ch.project_id)
        if not proj:
            return {"error": "project not found"}
        if ch.script_status != "approved":
            return {"error": "脚本未通过审核"}

        ch.prompt_status = "reviewing"
        ch.prompt_review_round = (ch.prompt_review_round or 0) + 1
        db.commit()

        scenes = (ch.script or {}).get("scenes", [])
        if not scenes:
            ch.prompt_status = "approved"
            db.commit()
            return {"status": "approved", "reason": "无场景"}

        chars = db.execute(
            select(NovelCharacter).where(NovelCharacter.project_id == proj.id)
        ).scalars().all()
        char_appearances = {c.name: c.appearance or "" for c in chars if c.appearance}

        result = review_prompts(
            db, chapter_id, scenes, ch.raw_text or "",
            visual_style=proj.visual_style or "",
            characters=char_appearances,
        )

        review = ChapterReview(
            chapter_id=chapter_id,
            review_stage="prompt",
            review_round=ch.prompt_review_round,
            status="approved" if result["overall_pass"] else "rejected",
            reviewer_type="ai",
            notes=f"AI评审第{ch.prompt_review_round}轮",
            review_detail=result,
        )
        db.add(review)

        if result["overall_pass"]:
            ch.prompt_status = "approved"
            prompts_map = {s.get("scene_id", i): s.get("visual_prompt", "")
                          for i, s in enumerate(scenes)}
            ch.image_prompts = prompts_map
            db.commit()
            log_sync(db, "novel_chapter", ch.id, "prompt_approved", "提示词评审通过", "info")
            return {"status": "approved"}

        if ch.prompt_review_round >= PROMPT_MAX_ROUNDS:
            ch.prompt_status = "rejected"
            ch.prompt_review_notes = f"经过{PROMPT_MAX_ROUNDS}轮评审仍未通过，需人工介入"
            db.commit()
            log_sync(db, "novel_chapter", ch.id, "prompt_max_retries",
                     f"提示词评审{PROMPT_MAX_ROUNDS}轮未通过", "warning")
            return {"status": "rejected", "reason": "max_retries"}

        updated_scenes = list(scenes)
        for sr in result.get("scenes", []):
            if not sr.get("pass", True) and sr.get("suggested_prompt"):
                for s in updated_scenes:
                    if s.get("scene_id") == sr.get("scene_id"):
                        s["visual_prompt"] = sr["suggested_prompt"]
                        break

        script = ch.script or {}
        script["scenes"] = updated_scenes
        ch.script = script
        ch.prompt_status = "pending"
        ch.prompt_review_notes = json.dumps(result, ensure_ascii=False)[:2000] if 'json' in dir() else str(result)[:2000]
        db.commit()

        review_chapter_prompts_task.delay(chapter_id)
        return {"status": "retrying", "round": ch.prompt_review_round}

    except Exception as e:
        if "ch" in locals() and ch:
            ch.prompt_status = "pending"
            ch.error = str(e)[:2000]
            db.commit()
        log_sync(db, "novel_chapter", chapter_id, "prompt_review_fail", str(e), "error")
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="generate_chapter_images", bind=True)
def generate_chapter_images_task(self, chapter_id: int):
    """生成章节的所有场景图片（提示词评审通过后调用）。"""
    db = SessionLocal()
    try:
        ch = db.get(NovelChapter, chapter_id)
        if not ch:
            return {"error": "chapter not found"}
        proj = db.get(NovelProject, ch.project_id)
        if not proj:
            return {"error": "project not found"}
        if ch.prompt_status != "approved":
            return {"error": "提示词评审未通过"}

        ch.image_status = "generating"
        db.commit()

        scenes = (ch.script or {}).get("scenes", [])
        chars_map = {}
        chars = db.execute(
            select(NovelCharacter).where(NovelCharacter.project_id == proj.id)
        ).scalars().all()
        for c in chars:
            chars_map[c.name] = c

        assets_dir = Path(settings.novel_assets_dir) / f"project_{proj.id}" / f"chapter_{ch.id}"
        visual_dir = assets_dir / "visual"
        visual_dir.mkdir(parents=True, exist_ok=True)

        orientation = proj.video_orientation or "portrait"
        img_w, img_h = (1920, 1080) if orientation == "landscape" else (1080, 1920)

        def _img_worker(scene):
            sid = scene.get("scene_id", 0)
            speaker = scene.get("speaker")
            visual_prompt = scene.get("visual_prompt", "")
            mood = scene.get("mood", "neutral")
            text = scene.get("text") or ""
            img_path = visual_dir / f"scene_{sid:03d}.png"

            full_prompt = ""
            if proj.visual_style:
                full_prompt += proj.visual_style + ", "
            if speaker and speaker in chars_map and chars_map[speaker].appearance:
                full_prompt += chars_map[speaker].appearance + ", "
            full_prompt += visual_prompt

            db_local = SessionLocal()
            try:
                ok = siliconflow_generate(db_local, full_prompt, img_path, width=img_w, height=img_h)
                if not ok:
                    generate_scene_image(visual_prompt, mood, img_path, width=img_w, height=img_h,
                                         speaker=speaker, text=text)
            except Exception as e:
                log.warning("Image gen fail scene %d: %s", sid, e)
                generate_scene_image(visual_prompt, mood, img_path, width=img_w, height=img_h,
                                     speaker=speaker, text=text)
            finally:
                db_local.close()
            return sid, img_path

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_IMG) as pool:
            futures = [pool.submit(_img_worker, s) for s in scenes]
            visual_assets = {}
            for f in as_completed(futures):
                sid, path = f.result()
                visual_assets[str(sid)] = str(path)

        ch.visual_assets = visual_assets
        ch.image_status = "reviewing"
        db.commit()

        log_sync(db, "novel_chapter", ch.id, "images_generated",
                 f"图片生成完成, {len(visual_assets)}个场景", "info")
        return {"status": "reviewing", "count": len(visual_assets)}

    except Exception as e:
        if "ch" in locals() and ch:
            ch.image_status = "pending"
            ch.error = str(e)[:2000]
            db.commit()
        log_sync(db, "novel_chapter", chapter_id, "image_gen_fail", str(e), "error")
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="review_chapter_images", bind=True)
def review_chapter_images_task(self, chapter_id: int):
    """AI 评审生成的章节图片。"""
    db = SessionLocal()
    try:
        ch = db.get(NovelChapter, chapter_id)
        if not ch:
            return {"error": "chapter not found"}
        proj = db.get(NovelProject, ch.project_id)
        if not proj:
            return {"error": "project not found"}

        ch.image_status = "reviewing"
        ch.image_review_round = (ch.image_review_round or 0) + 1
        db.commit()

        visual_assets = ch.visual_assets or {}
        if not visual_assets:
            ch.image_status = "approved"
            db.commit()
            return {"status": "approved", "reason": "无图片资产"}

        scene_images = {int(k): Path(v) for k, v in visual_assets.items()}
        scenes = (ch.script or {}).get("scenes", [])
        scene_prompts = {s.get("scene_id", i): s.get("visual_prompt", "")
                        for i, s in enumerate(scenes)}

        result = review_images(
            db, chapter_id, scene_images, scene_prompts,
            visual_style=proj.visual_style or "",
        )

        review = ChapterReview(
            chapter_id=chapter_id,
            review_stage="image",
            review_round=ch.image_review_round,
            status="approved" if result["overall_pass"] else "rejected",
            reviewer_type="ai",
            notes=f"AI图片评审第{ch.image_review_round}轮",
            review_detail=result,
        )
        db.add(review)

        if result["overall_pass"]:
            ch.image_status = "approved"
            db.commit()
            log_sync(db, "novel_chapter", ch.id, "image_approved", "图片评审通过", "info")
            return {"status": "approved"}

        if ch.image_review_round >= IMAGE_MAX_ROUNDS:
            ch.image_status = "approved"
            ch.image_review_notes = f"经过{IMAGE_MAX_ROUNDS}轮评审仍有瑕疵，强制通过（使用当前图片）"
            db.commit()
            log_sync(db, "novel_chapter", ch.id, "image_force_approved",
                     f"图片评审{IMAGE_MAX_ROUNDS}轮后强制通过", "warning")
            return {"status": "approved", "reason": "force_after_max_retries"}

        failed_sids = [s["scene_id"] for s in result.get("scenes", []) if not s.get("pass", True)]
        if failed_sids:
            _regenerate_failed_images(db, ch, proj, failed_sids)

        ch.image_status = "generating"
        db.commit()

        generate_chapter_images_task.apply_async(
            args=[chapter_id],
            countdown=2,
        )
        return {"status": "retrying", "round": ch.image_review_round, "failed_scenes": failed_sids}

    except Exception as e:
        if "ch" in locals() and ch:
            ch.image_status = "reviewing"
            ch.error = str(e)[:2000]
            db.commit()
        log_sync(db, "novel_chapter", chapter_id, "image_review_fail", str(e), "error")
        return {"error": str(e)}
    finally:
        db.close()


def _regenerate_failed_images(db, ch, proj, failed_sids):
    """重新生成失败的场景图片。"""
    scenes = (ch.script or {}).get("scenes", [])
    scene_map = {s["scene_id"]: s for s in scenes}
    chars_map = {}
    chars = db.execute(
        select(NovelCharacter).where(NovelCharacter.project_id == proj.id)
    ).scalars().all()
    for c in chars:
        chars_map[c.name] = c

    assets_dir = Path(settings.novel_assets_dir) / f"project_{proj.id}" / f"chapter_{ch.id}"
    visual_dir = assets_dir / "visual"
    orientation = proj.video_orientation or "portrait"
    img_w, img_h = (1920, 1080) if orientation == "landscape" else (1080, 1920)

    for sid in failed_sids:
        scene = scene_map.get(sid)
        if not scene:
            continue
        img_path = visual_dir / f"scene_{sid:03d}.png"
        speaker = scene.get("speaker")
        full_prompt = ""
        if proj.visual_style:
            full_prompt += proj.visual_style + ", "
        if speaker and speaker in chars_map and chars_map[speaker].appearance:
            full_prompt += chars_map[speaker].appearance + ", "
        full_prompt += scene.get("visual_prompt", "")
        full_prompt += ", high quality, no deformation, correct anatomy"

        ok = siliconflow_generate(db, full_prompt, img_path, width=img_w, height=img_h,
                                  negative_prompt="blurry, deformed, ugly, extra limbs, extra fingers, bad anatomy, watermark, text")
        if not ok:
            generate_scene_image(scene.get("visual_prompt", ""), scene.get("mood", "neutral"),
                                 img_path, width=img_w, height=img_h,
                                 speaker=speaker, text=scene.get("text"))


import json  # noqa: E402 — needed by prompt review task serialization


@celery_app.task(name="generate_chapter_video", bind=True)
def generate_chapter_video_task(self, chapter_id: int):
    db = SessionLocal()
    try:
        ch = db.get(NovelChapter, chapter_id)
        if not ch:
            return {"error": "chapter not found"}
        proj = db.get(NovelProject, ch.project_id)
        if not proj:
            return {"error": "project not found"}
        if ch.script_status != "approved":
            return {"error": "脚本未通过审核"}
        if ch.image_status != "approved":
            return {"error": "图片评审未通过，请先完成图片评审"}

        ch.video_status = "generating"
        ch.error = None
        db.commit()

        scenes = (ch.script or {}).get("scenes", [])
        if not scenes:
            ch.video_status = "pending"
            ch.error = "脚本为空，无法生成视频"
            db.commit()
            return {"error": ch.error}

        chars_map = {}
        chars = db.execute(
            select(NovelCharacter).where(NovelCharacter.project_id == proj.id)
        ).scalars().all()
        for c in chars:
            chars_map[c.name] = c

        assets_dir = Path(settings.novel_assets_dir) / f"project_{proj.id}" / f"chapter_{ch.id}"
        audio_dir = assets_dir / "audio"
        visual_dir = assets_dir / "visual"
        video_dir = assets_dir / "video"
        audio_dir.mkdir(parents=True, exist_ok=True)
        visual_dir.mkdir(parents=True, exist_ok=True)
        video_dir.mkdir(parents=True, exist_ok=True)

        orientation = proj.video_orientation or "portrait"
        if orientation == "landscape":
            img_w, img_h = 1920, 1080
        else:
            img_w, img_h = 1080, 1920

        # ── 预处理场景元数据 ──
        scene_metas = []
        for scene in scenes:
            sid = scene.get("scene_id", 0)
            stype = scene.get("type", "narration")
            speaker = scene.get("speaker")
            text = scene.get("text") or ""
            visual_prompt = scene.get("visual_prompt", "")
            mood = scene.get("mood", "neutral")
            dur_hint = float(scene.get("duration_hint", 5))

            voice_id = None
            gender = "female"
            is_narrator = (speaker == "narrator" or stype == "narration")
            if is_narrator and proj.narrator_voice_id:
                voice_id = proj.narrator_voice_id
            elif speaker and speaker in chars_map:
                char = chars_map[speaker]
                voice_id = char.voice_id
                gender = char.gender or "female"

            full_prompt = ""
            if proj.visual_style:
                full_prompt += proj.visual_style + ", "
            if speaker and speaker in chars_map and chars_map[speaker].appearance:
                full_prompt += chars_map[speaker].appearance + ", "
            full_prompt += visual_prompt

            scene_metas.append({
                "sid": sid, "stype": stype, "speaker": speaker,
                "text": text, "visual_prompt": visual_prompt, "mood": mood,
                "dur_hint": dur_hint, "voice_id": voice_id, "gender": gender,
                "is_narrator": is_narrator, "full_prompt": full_prompt,
                "audio_path": audio_dir / f"scene_{sid:03d}.mp3",
                "img_path": visual_dir / f"scene_{sid:03d}.png",
                "vid_path": video_dir / f"scene_{sid:03d}.mp4",
            })

        total_t0 = time.time()

        # ── Phase 1: 并行 TTS ──
        phase_t0 = time.time()
        log_sync(db, "novel_chapter", ch.id, "phase_tts", f"开始并行TTS ({len(scene_metas)}个场景)", "info")

        def _tts_worker(meta):
            if not meta["text"] or meta["stype"] == "transition":
                meta["audio_path"].write_bytes(b"")
                return meta["sid"], meta["dur_hint"]
            db_local = SessionLocal()
            try:
                synthesize_scene(
                    db_local, meta["text"], meta["audio_path"],
                    voice_id=meta["voice_id"], gender=meta["gender"],
                    is_narrator=meta["is_narrator"],
                )
                real_dur = ffprobe_duration(meta["audio_path"])
                if real_dur and real_dur > 0.5:
                    return meta["sid"], real_dur
            except Exception as e:
                log.warning("TTS fail scene %d: %s", meta["sid"], e)
                meta["audio_path"].write_bytes(b"")
            finally:
                db_local.close()
            return meta["sid"], meta["dur_hint"]

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_TTS) as pool:
            tts_futures = {pool.submit(_tts_worker, m): m for m in scene_metas}
            for future in as_completed(tts_futures):
                sid, dur = future.result()
                for m in scene_metas:
                    if m["sid"] == sid:
                        m["dur_hint"] = dur
                        break

        log_sync(db, "novel_chapter", ch.id, "phase_tts_done",
                 f"TTS完成 ({time.time() - phase_t0:.1f}s)", "info")

        # ── Phase 2: 并行图片生成 ──
        phase_t0 = time.time()
        log_sync(db, "novel_chapter", ch.id, "phase_img", f"开始并行图片生成", "info")

        def _img_worker(meta):
            db_local = SessionLocal()
            try:
                ok = siliconflow_generate(
                    db_local, meta["full_prompt"], meta["img_path"],
                    width=img_w, height=img_h,
                )
                if not ok:
                    generate_scene_image(
                        meta["visual_prompt"], meta["mood"], meta["img_path"],
                        width=img_w, height=img_h,
                        speaker=meta["speaker"], text=meta["text"],
                    )
            except Exception as e:
                log.warning("Image gen fail scene %d: %s", meta["sid"], e)
                generate_scene_image(
                    meta["visual_prompt"], meta["mood"], meta["img_path"],
                    width=img_w, height=img_h,
                    speaker=meta["speaker"], text=meta["text"],
                )
            finally:
                db_local.close()
            return meta["sid"]

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_IMG) as pool:
            img_futures = [pool.submit(_img_worker, m) for m in scene_metas]
            for f in as_completed(img_futures):
                f.result()

        log_sync(db, "novel_chapter", ch.id, "phase_img_done",
                 f"图片生成完成 ({time.time() - phase_t0:.1f}s)", "info")

        # ── Phase 3: 批量 I2V（全部提交 → 全部轮询） ──
        phase_t0 = time.time()
        log_sync(db, "novel_chapter", ch.id, "phase_i2v", f"开始批量I2V", "info")

        i2v_tasks = [
            {
                "scene_id": m["sid"],
                "image_path": m["img_path"],
                "out_path": m["vid_path"],
                "duration": m["dur_hint"],
                "prompt": m["visual_prompt"][:200],
            }
            for m in scene_metas
        ]
        i2v_results = batch_ai_image_to_video(db, i2v_tasks, max_wait=600)

        sf_count = sum(1 for v in i2v_results.values() if v == "siliconflow")
        log_sync(db, "novel_chapter", ch.id, "phase_i2v_done",
                 f"I2V完成 ({time.time() - phase_t0:.1f}s): {sf_count}个AI生成, "
                 f"{len(i2v_results) - sf_count}个Ken Burns", "info")

        # ── 收集资产 ──
        audio_assets = {}
        visual_assets = {}
        scene_videos = []
        scene_audios = []
        for m in scene_metas:
            audio_assets[str(m["sid"])] = str(m["audio_path"])
            visual_assets[str(m["sid"])] = str(m["img_path"])
            scene_videos.append(m["vid_path"])
            scene_audios.append(m["audio_path"])
            engine = i2v_results.get(m["sid"], "kenburns")
            log_sync(db, "novel_chapter", ch.id, "img2vid", f"scene {m['sid']}: engine={engine}", "info")

        total_asset_time = time.time() - total_t0
        log_sync(db, "novel_chapter", ch.id, "assets_done",
                 f"全部素材生成完成 ({total_asset_time:.1f}s / {total_asset_time/60:.1f}min)", "info")

        ch.audio_assets = audio_assets
        ch.visual_assets = visual_assets
        ch.video_status = "compositing"
        db.commit()

        # ── BGM ──
        bgm_path = None
        if ch.bgm_id:
            bgm = db.get(BgmLibrary, ch.bgm_id)
            if bgm:
                bgm_path = Path(bgm.file_path)
        if not bgm_path and proj.default_bgm_id:
            bgm = db.get(BgmLibrary, proj.default_bgm_id)
            if bgm:
                bgm_path = Path(bgm.file_path)
        if not bgm_path:
            default = Path(settings.default_bgm_path)
            if default.is_file():
                bgm_path = default

        # ── 合成 ──
        out_dir = Path(settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"novel_{proj.id}_ch{ch.chapter_no}.mp4"

        try:
            compose_chapter_video(
                scene_videos=scene_videos,
                scene_audios=scene_audios,
                bgm_path=bgm_path,
                bgm_volume=ch.bgm_volume,
                output_path=output_path,
                title_text=f"{proj.novel_title} 第{ch.chapter_no}章 {ch.title}",
            )
        except Exception as e:
            ch.video_status = "pending"
            ch.error = f"视频合成失败: {e}"
            db.commit()
            log_sync(db, "novel_chapter", ch.id, "compose_fail", str(e), "error")
            return {"error": str(e)}

        ch.output_path = str(output_path)
        ch.video_status = "reviewing"
        ch.actual_duration = ffprobe_duration(output_path)
        ch.error = None
        db.commit()
        log_sync(db, "novel_chapter", ch.id, "video_done", f"章节视频合成完成: {output_path.name}", "info")
        return {"status": "reviewing", "output": str(output_path)}
    except Exception as e:
        if "ch" in locals() and ch:
            ch.video_status = "pending"
            ch.error = str(e)[:2000]
            db.commit()
        log_sync(db, "novel_chapter", chapter_id, "video_fail", str(e), "error")
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="regenerate_scene_assets", bind=True)
def regenerate_scene_assets_task(self, chapter_id: int, scene_ids: list[int], target: str = "all"):
    """增量重做指定场景的素材，然后重新合成。"""
    db = SessionLocal()
    try:
        ch = db.get(NovelChapter, chapter_id)
        if not ch:
            return {"error": "chapter not found"}
        proj = db.get(NovelProject, ch.project_id)
        if not proj:
            return {"error": "project not found"}

        scenes = (ch.script or {}).get("scenes", [])
        scene_map = {s["scene_id"]: s for s in scenes}

        chars_map = {}
        chars = db.execute(
            select(NovelCharacter).where(NovelCharacter.project_id == proj.id)
        ).scalars().all()
        for c in chars:
            chars_map[c.name] = c

        assets_dir = Path(settings.novel_assets_dir) / f"project_{proj.id}" / f"chapter_{ch.id}"
        audio_dir = assets_dir / "audio"
        visual_dir = assets_dir / "visual"
        video_dir = assets_dir / "video"

        orientation = proj.video_orientation or "portrait"
        img_w, img_h = (1920, 1080) if orientation == "landscape" else (1080, 1920)

        audio_assets = ch.audio_assets or {}
        visual_assets = ch.visual_assets or {}

        ch.video_status = "generating"
        db.commit()

        for sid in scene_ids:
            scene = scene_map.get(sid)
            if not scene:
                continue

            speaker = scene.get("speaker")
            text = scene.get("text") or ""
            visual_prompt = scene.get("visual_prompt", "")
            mood = scene.get("mood", "neutral")
            dur_hint = float(scene.get("duration_hint", 5))

            audio_path = audio_dir / f"scene_{sid:03d}.mp3"
            img_path = visual_dir / f"scene_{sid:03d}.png"
            vid_path = video_dir / f"scene_{sid:03d}.mp4"

            if target in ("all", "audio") and text and scene.get("type") != "transition":
                voice_id = None
                gender = "female"
                is_narrator = (speaker == "narrator" or scene.get("type") == "narration")
                if is_narrator and proj.narrator_voice_id:
                    voice_id = proj.narrator_voice_id
                elif speaker and speaker in chars_map:
                    char = chars_map[speaker]
                    voice_id = char.voice_id
                    gender = char.gender or "female"
                try:
                    synthesize_scene(db, text, audio_path, voice_id=voice_id, gender=gender, is_narrator=is_narrator)
                    real_dur = ffprobe_duration(audio_path)
                    if real_dur and real_dur > 0.5:
                        dur_hint = real_dur
                except Exception as e:
                    log_sync(db, "novel_chapter", ch.id, "regen_tts_fail", f"scene {sid}: {e}", "error")

            if target in ("all", "visual"):
                full_prompt = ""
                if proj.visual_style:
                    full_prompt += proj.visual_style + ", "
                if speaker and speaker in chars_map and chars_map[speaker].appearance:
                    full_prompt += chars_map[speaker].appearance + ", "
                full_prompt += visual_prompt

                ai_ok = siliconflow_generate(db, full_prompt, img_path, width=img_w, height=img_h)
                if not ai_ok:
                    generate_scene_image(visual_prompt, mood, img_path, width=img_w, height=img_h, speaker=speaker, text=text)

                try:
                    engine = ai_image_to_video(
                        db, img_path, vid_path,
                        duration=dur_hint,
                        prompt=visual_prompt[:200],
                        aspect_ratio="16:9" if orientation == "landscape" else "9:16",
                    )
                    log_sync(db, "novel_chapter", ch.id, "regen_img2vid", f"scene {sid}: engine={engine}", "info")
                except Exception as e:
                    log_sync(db, "novel_chapter", ch.id, "regen_img2vid_fail", f"scene {sid}: {e}", "error")

            audio_assets[str(sid)] = str(audio_path)
            visual_assets[str(sid)] = str(img_path)

        ch.audio_assets = audio_assets
        ch.visual_assets = visual_assets
        ch.video_status = "compositing"
        db.commit()

        all_scenes = sorted(scenes, key=lambda s: s["scene_id"])
        scene_videos = []
        scene_audios = []
        for s in all_scenes:
            sid = s["scene_id"]
            scene_videos.append(video_dir / f"scene_{sid:03d}.mp4")
            scene_audios.append(audio_dir / f"scene_{sid:03d}.mp3")

        bgm_path = None
        if ch.bgm_id:
            bgm = db.get(BgmLibrary, ch.bgm_id)
            if bgm:
                bgm_path = Path(bgm.file_path)
        if not bgm_path and proj.default_bgm_id:
            bgm = db.get(BgmLibrary, proj.default_bgm_id)
            if bgm:
                bgm_path = Path(bgm.file_path)
        if not bgm_path:
            default = Path(settings.default_bgm_path)
            if default.is_file():
                bgm_path = default

        out_dir = Path(settings.output_dir)
        output_path = out_dir / f"novel_{proj.id}_ch{ch.chapter_no}.mp4"

        try:
            compose_chapter_video(
                scene_videos=scene_videos,
                scene_audios=scene_audios,
                bgm_path=bgm_path,
                bgm_volume=ch.bgm_volume,
                output_path=output_path,
            )
        except Exception as e:
            ch.video_status = "reviewing"
            ch.error = f"重新合成失败: {e}"
            db.commit()
            return {"error": str(e)}

        ch.output_path = str(output_path)
        ch.video_status = "reviewing"
        ch.actual_duration = ffprobe_duration(output_path)
        ch.error = None
        db.commit()
        log_sync(db, "novel_chapter", ch.id, "regen_done", f"增量重做完成: scenes={scene_ids}", "info")
        return {"status": "reviewing"}
    except Exception as e:
        if "ch" in locals() and ch:
            ch.video_status = "reviewing"
            ch.error = str(e)[:2000]
            db.commit()
        return {"error": str(e)}
    finally:
        db.close()
