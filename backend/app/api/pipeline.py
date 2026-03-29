from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models import Article, GenerationJob, User, UserVideo, VoicePrint
from app.services.tts_audio import has_audio_stream
from app.tasks import run_generation_job_task, run_voice_clone_task

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class GenJobCreate(BaseModel):
    """创建生成任务。"""

    generation_mode: str = Field(
        "article",
        description="article=资讯口播；text_prompt=按文字需求生成文案后再成片",
    )
    article_id: Optional[int] = None
    user_video_id: int
    tts_language: str = "zh-CN"
    voice_profile_id: Optional[int] = None
    # 文案模式
    user_prompt: Optional[str] = None
    direct_script: Optional[str] = None
    script_source: str = Field(
        "article",
        description="article | deepseek | direct（资讯/DeepSeek 生成/直接粘贴口播）",
    )
    display_title: Optional[str] = None
    # 音频：tts=仅口播；tts_bgm=口播+背景音乐；bgm_only=仅字幕+背景音乐（无口播人声）
    audio_mode: str = Field("tts", description="tts | tts_bgm | bgm_only")
    bgm_volume: float = Field(0.22, ge=0.0, le=1.0)
    lip_sync: bool = True
    output_description: Optional[str] = None


class GenJobOut(BaseModel):
    id: int
    article_id: Optional[int] = None
    user_video_id: int
    status: str
    output_path: Optional[str]
    narration_text: Optional[str]
    output_description: Optional[str]
    error: Optional[str]
    meta: Optional[dict] = None
    # 全局队列（pending + processing，按 id 升序）；已完成/失败为 null
    queue_position: Optional[int] = None
    queue_pending_total: Optional[int] = None

    class Config:
        from_attributes = True


async def _queue_position_maps(db: AsyncSession) -> tuple[dict[int, int], int]:
    r = await db.execute(
        select(GenerationJob.id)
        .where(GenerationJob.status.in_(["pending", "processing"]))
        .order_by(GenerationJob.id.asc())
    )
    ids = [row[0] for row in r.all()]
    total = len(ids)
    pos_map = {jid: i + 1 for i, jid in enumerate(ids)}
    return pos_map, total


def _gen_job_out(
    job: GenerationJob,
    pos_map: dict[int, int],
    queue_total: int,
) -> GenJobOut:
    qp = qt = None
    if job.status in ("pending", "processing") and job.id in pos_map:
        qp = pos_map[job.id]
        qt = queue_total
    return GenJobOut(
        id=job.id,
        article_id=job.article_id,
        user_video_id=job.user_video_id,
        status=job.status,
        output_path=job.output_path,
        narration_text=job.narration_text,
        output_description=job.output_description,
        error=job.error,
        meta=job.meta,
        queue_position=qp,
        queue_pending_total=qt,
    )


class JobDescriptionIn(BaseModel):
    output_description: str = Field(..., min_length=0, max_length=2000)


async def _resolve_native_voiceprint(
    db: AsyncSession,
    user: User,
    vid: UserVideo,
    tts_language: str,
    audio_mode: str,
) -> Optional[int]:
    """未选手动声纹时，若视频有音轨则尝试绑定原生声纹（仅口播类模式）。"""
    if audio_mode == "bgm_only":
        return None
    if not tts_language.lower().startswith("zh"):
        return None
    settings = get_settings()
    v_path = Path(settings.upload_dir) / vid.stored_path
    if not has_audio_stream(v_path):
        return None

    q = (
        select(VoicePrint)
        .where(
            VoicePrint.user_id == user.id,
            VoicePrint.source_type == "video",
            VoicePrint.source_video_id == vid.id,
            VoicePrint.status == "ready",
        )
        .order_by(VoicePrint.id.desc())
        .limit(1)
    )
    ready_vp = (await db.execute(q)).scalar_one_or_none()
    if ready_vp:
        return ready_vp.id

    pending_q = (
        select(VoicePrint)
        .where(
            VoicePrint.user_id == user.id,
            VoicePrint.source_type == "video",
            VoicePrint.source_video_id == vid.id,
            VoicePrint.status.in_(["pending", "processing"]),
        )
        .order_by(VoicePrint.id.desc())
        .limit(1)
    )
    pending_vp = (await db.execute(pending_q)).scalar_one_or_none()
    if pending_vp:
        raise HTTPException(status_code=409, detail="检测到视频原声音轨，正在提取原生声纹，请稍后重试创建任务")

    auto_vp = VoicePrint(
        user_id=user.id,
        source_type="video",
        source_video_id=vid.id,
        stored_path=vid.stored_path,
        original_name=vid.original_name,
        status="pending",
        provider="tencent_vrs",
        voice_gender=1,
        tts_language="zh-CN",
    )
    db.add(auto_vp)
    await db.commit()
    run_voice_clone_task.delay(auto_vp.id)
    raise HTTPException(status_code=409, detail="检测到视频原声音轨，已自动发起原生声纹提取，请1-2分钟后重试创建任务")


@router.post("/jobs", response_model=GenJobOut)
async def create_job(
    data: GenJobCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    vid = await db.get(UserVideo, data.user_video_id)
    if not vid or vid.user_id != user.id:
        raise HTTPException(status_code=404, detail="视频不存在或无权使用")

    if data.generation_mode not in ("article", "text_prompt"):
        raise HTTPException(status_code=400, detail="generation_mode 只能是 article 或 text_prompt")

    if data.audio_mode not in ("tts", "tts_bgm", "bgm_only"):
        raise HTTPException(status_code=400, detail="audio_mode 只能是 tts / tts_bgm / bgm_only")

    article_id: Optional[int] = None
    if data.generation_mode == "article":
        if not data.article_id:
            raise HTTPException(status_code=400, detail="资讯模式需要 article_id")
        art = await db.get(Article, data.article_id)
        if not art:
            raise HTTPException(status_code=404, detail="文章不存在")
        article_id = data.article_id
        if data.script_source != "article":
            raise HTTPException(status_code=400, detail="资讯模式请将 script_source 设为 article")
    else:
        if data.script_source not in ("deepseek", "direct"):
            raise HTTPException(status_code=400, detail="文案模式 script_source 应为 deepseek 或 direct")
        if data.script_source == "deepseek" and not (data.user_prompt or "").strip():
            raise HTTPException(status_code=400, detail="请填写需求说明 user_prompt，或改用 direct 粘贴口播")
        if data.script_source == "direct" and not (data.direct_script or "").strip():
            raise HTTPException(status_code=400, detail="请粘贴口播正文 direct_script")

    if data.audio_mode in ("tts_bgm", "bgm_only"):
        settings = get_settings()
        if not (settings.default_bgm_path or "").strip():
            raise HTTPException(
                status_code=400,
                detail="服务器未配置 default_bgm_path（背景音乐文件路径），无法使用口播+BGM 或纯BGM 模式",
            )
        bgm_p = Path(settings.default_bgm_path)
        if not bgm_p.is_file():
            raise HTTPException(status_code=400, detail=f"背景音乐文件不存在：{bgm_p}")

    selected_voice_profile_id = data.voice_profile_id
    if selected_voice_profile_id is None and data.audio_mode != "bgm_only":
        try:
            selected_voice_profile_id = await _resolve_native_voiceprint(
                db, user, vid, data.tts_language, data.audio_mode
            )
        except HTTPException:
            raise

    meta = {
        "generation_mode": data.generation_mode,
        "tts_language": data.tts_language,
        "voice_profile_id": selected_voice_profile_id,
        "script_source": data.script_source,
        "user_prompt": (data.user_prompt or "").strip(),
        "direct_script": (data.direct_script or "").strip(),
        "audio_mode": data.audio_mode,
        "bgm_volume": data.bgm_volume,
        "lip_sync": data.lip_sync,
        "display_title": (data.display_title or "").strip() or None,
    }

    job = GenerationJob(
        user_id=user.id,
        article_id=article_id,
        user_video_id=data.user_video_id,
        status="pending",
        meta=meta,
        output_description=(data.output_description or "").strip() or None,
    )
    db.add(job)
    await db.commit()
    run_generation_job_task.delay(job.id)
    pos_map, qtotal = await _queue_position_maps(db)
    return _gen_job_out(job, pos_map, qtotal)


@router.get("/jobs", response_model=list[GenJobOut])
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
):
    q = (
        select(GenerationJob)
        .where(GenerationJob.user_id == user.id)
        .order_by(GenerationJob.id.desc())
        .limit(min(limit, 200))
    )
    rows = (await db.execute(q)).scalars().all()
    pos_map, qtotal = await _queue_position_maps(db)
    return [_gen_job_out(j, pos_map, qtotal) for j in rows]


@router.get("/jobs/{job_id}", response_model=GenJobOut)
async def get_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    job = await db.get(GenerationJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    pos_map, qtotal = await _queue_position_maps(db)
    return _gen_job_out(job, pos_map, qtotal)


@router.patch("/jobs/{job_id}/description", response_model=GenJobOut)
async def update_job_description(
    job_id: int,
    body: JobDescriptionIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    job = await db.get(GenerationJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    job.output_description = body.output_description.strip()
    await db.flush()
    pos_map, qtotal = await _queue_position_maps(db)
    return _gen_job_out(job, pos_map, qtotal)


@router.post("/jobs/{job_id}/retry", response_model=GenJobOut)
async def retry_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    job = await db.get(GenerationJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="任务不存在")
    job.status = "pending"
    job.error = None
    job.output_path = None
    await db.commit()
    run_generation_job_task.delay(job.id)
    pos_map, qtotal = await _queue_position_maps(db)
    return _gen_job_out(job, pos_map, qtotal)
