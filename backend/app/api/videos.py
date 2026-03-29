import os
import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models import GenerationJob, PublishJob, User, UserVideo, VoicePrint
from app.services.tts_audio import ffprobe_duration

router = APIRouter(prefix="/videos", tags=["videos"])


class UserVideoOut(BaseModel):
    id: int
    original_name: str
    stored_path: str
    mime: str
    size_bytes: int
    duration_sec: Optional[float]
    category_id: Optional[int]
    status: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[UserVideoOut])
async def list_my_videos(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    rows = (await db.execute(select(UserVideo).where(UserVideo.user_id == user.id).order_by(UserVideo.id.desc()))).scalars().all()
    return rows


@router.post("/upload", response_model=UserVideoOut)
async def upload_video(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    category_id: Optional[int] = Form(None),
):
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")
    ext = Path(file.filename).suffix.lower() or ".mp4"
    if ext not in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
        raise HTTPException(status_code=400, detail="暂不支持该格式")

    sub = Path(f"user_{user.id}")
    dest_dir = Path(settings.upload_dir) / sub
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    dest = dest_dir / name

    size = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            f.write(chunk)
            if size > 500 * 1024 * 1024:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="文件过大（>500MB）")

    rel = str(sub / name)
    dur = ffprobe_duration(dest)

    uv = UserVideo(
        user_id=user.id,
        category_id=category_id,
        original_name=file.filename,
        stored_path=rel,
        mime=file.content_type or "application/octet-stream",
        size_bytes=size,
        duration_sec=dur,
        status="ready",
    )
    db.add(uv)
    await db.flush()
    return uv


@router.delete("/{video_id}")
async def delete_my_video(
    video_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    settings = get_settings()

    video = await db.get(UserVideo, video_id)
    if not video or video.user_id != user.id:
        raise HTTPException(status_code=404, detail="视频不存在或无权删除")

    # 先清理所有外键关联数据，避免 FK 约束导致删除失败。
    jobs = (
        await db.execute(select(GenerationJob).where(GenerationJob.user_video_id == video.id))
    ).scalars().all()
    job_ids = [j.id for j in jobs]

    if job_ids:
        publish_rows = (
            await db.execute(select(PublishJob).where(PublishJob.generation_job_id.in_(job_ids)))
        ).scalars().all()
        for pj in publish_rows:
            db.delete(pj)

    # 删除用户生成产物文件（按 job_id 推断文件名 + 兜底 output_path）。
    out_dir = Path(settings.output_dir)
    for job in jobs:
        if job.output_path:
            try:
                Path(job.output_path).unlink(missing_ok=True)
            except Exception:
                # 不阻断删除流程：文件可能已被清理或路径异常
                pass
        (out_dir / f"job_{job.id}.mp4").unlink(missing_ok=True)
        (out_dir / f"job_{job.id}.mp3").unlink(missing_ok=True)
        (out_dir / f"job_{job.id}_mixed.mp3").unlink(missing_ok=True)
        (out_dir / f"job_{job.id}_retalk.mp4").unlink(missing_ok=True)

    for job in jobs:
        db.delete(job)

    voiceprints = (
        await db.execute(
            select(VoicePrint).where(
                VoicePrint.user_id == user.id,
                VoicePrint.source_type == "video",
                VoicePrint.source_video_id == video.id,
            )
        )
    ).scalars().all()
    for vp in voiceprints:
        db.delete(vp)

    # 删除上传文件本身。
    upload_root = Path(settings.upload_dir).resolve()
    try:
        target = (upload_root / Path(video.stored_path)).resolve()
        if str(target).startswith(str(upload_root)):
            target.unlink(missing_ok=True)
    except Exception:
        # 仍然允许删除 DB 记录，避免卡死。
        pass

    db.delete(video)
    await db.flush()
    return {"ok": True}
