from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import get_current_user
from app.database import get_db
from app.db_sync import SessionLocal
from app.models import User, UserVideo, VoicePrint
from app.services.tts_audio import synthesize_speech
from app.tasks import run_voice_clone_task

router = APIRouter(prefix="/voiceprints", tags=["voiceprints"])


# 常见腾讯云在线音色编号 → 中文说明（其余走兜底文案）
TENCENT_VOICE_TYPE_ZH: dict[int, str] = {
    101001: "智瑜（女声，通用播报）",
    101002: "智聆（女声）",
    101003: "智美（女声）",
    101004: "智云（男声）",
    101005: "智莉（女声）",
    101006: "智言（男声）",
    101007: "智琪（女声）",
    101008: "智芸（女声）",
    101009: "智华（男声）",
    101010: "智燕（女声）",
    101011: "智丹（女声）",
    101012: "智辉（男声）",
    101013: "智宁（男声）",
    101014: "智萌（男童声）",
    101015: "智甜（女童声）",
    101016: "智蓉（女声）",
    101017: "智靖（男声）",
    101018: "智彤（粤语女声）",
    101019: "智刚（男声）",
    101020: "智瑞（男声）",
    101021: "智虹（女声）",
    101022: "智萱（女声）",
    101023: "智皓（男声）",
    101024: "智薇（女声）",
    101025: "智希（女声）",
    101026: "智梅（女声）",
    101027: "智洁（女声）",
    101028: "智凯（男声）",
    101029: "智柯（男声）",
    101030: "智奎（男声）",
}


class VoicePrintOut(BaseModel):
    id: int
    status: str
    source_type: str
    source_video_id: Optional[int]
    original_name: str
    voice_gender: int
    tts_language: str
    error: Optional[str] = None
    voice_type: Optional[int] = None
    fast_voice_type: Optional[str] = None
    voice_source_label_zh: str = ""
    voice_type_label_zh: str = ""
    demo_audio_path: Optional[str] = None

    class Config:
        from_attributes = True


def _enrich(vp: VoicePrint) -> VoicePrintOut:
    if vp.source_type == "video":
        src = "视频原生声纹（从所选视频的音轨提取并复刻到腾讯云）"
    else:
        src = "导入音频声纹（从你上传的音频提取并复刻到腾讯云）"
    vt = vp.voice_type
    if vt is not None:
        vlab = TENCENT_VOICE_TYPE_ZH.get(int(vt), f"腾讯云标准音色编号 {vt}")
    else:
        vlab = ""
    if vp.fast_voice_type:
        vlab = (vlab + "；" if vlab else "") + f"复刻音色 FastVoiceType：{vp.fast_voice_type}"
    demo = f"/api/v1/voiceprints/{vp.id}/demo.mp3" if vp.status == "ready" and (vp.fast_voice_type or vp.voice_type) else None
    return VoicePrintOut(
        id=vp.id,
        status=vp.status,
        source_type=vp.source_type,
        source_video_id=vp.source_video_id,
        original_name=vp.original_name,
        voice_gender=vp.voice_gender,
        tts_language=vp.tts_language,
        error=vp.error,
        voice_type=vp.voice_type,
        fast_voice_type=vp.fast_voice_type,
        voice_source_label_zh=src,
        voice_type_label_zh=vlab or "（尚未生成或仅使用默认音色）",
        demo_audio_path=demo,
    )


@router.get("", response_model=list[VoicePrintOut])
async def list_voiceprints(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
):
    q = (
        select(VoicePrint)
        .where(VoicePrint.user_id == user.id)
        .order_by(VoicePrint.id.desc())
        .limit(min(limit, 200))
    )
    rows = (await db.execute(q)).scalars().all()
    return [_enrich(r) for r in rows]


class FromVideoIn(BaseModel):
    user_video_id: int
    voice_gender: int = 1
    tts_language: str = "zh-CN"


@router.post("/from-video", response_model=VoicePrintOut)
async def create_from_video(
    data: FromVideoIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    uv = await db.get(UserVideo, data.user_video_id)
    if not uv or uv.user_id != user.id:
        raise HTTPException(status_code=404, detail="视频不存在或无权使用")

    vp = VoicePrint(
        user_id=user.id,
        source_type="video",
        source_video_id=uv.id,
        stored_path=uv.stored_path,
        original_name=uv.original_name,
        status="pending",
        provider="tencent_vrs",
        voice_gender=data.voice_gender,
        tts_language=data.tts_language,
    )
    db.add(vp)
    await db.flush()
    run_voice_clone_task.delay(vp.id)
    return _enrich(vp)


@router.post("/import-audio", response_model=VoicePrintOut)
async def import_audio(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    voice_gender: int = Form(1),
    tts_language: str = Form("zh-CN"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    settings = get_settings()
    dest_dir = Path(settings.upload_dir) / f"user_{user.id}" / "voices"
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix.lower() or ".wav"
    name = f"{uuid.uuid4().hex}{ext}"
    dest = dest_dir / name

    size = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            f.write(chunk)
            if size > 200 * 1024 * 1024:
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="文件过大（>200MB）")

    rel = str(Path(f"user_{user.id}") / "voices" / name)

    vp = VoicePrint(
        user_id=user.id,
        source_type="upload",
        source_video_id=None,
        stored_path=rel,
        original_name=file.filename,
        status="pending",
        provider="tencent_vrs",
        voice_gender=voice_gender,
        tts_language=tts_language,
    )
    db.add(vp)
    await db.flush()
    run_voice_clone_task.delay(vp.id)
    return _enrich(vp)


@router.get("/{voiceprint_id}/demo.mp3")
async def voiceprint_demo_audio(
    voiceprint_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """生成短句试听 MP3（腾讯云声纹 / FastVoiceType）。"""
    vp = await db.get(VoicePrint, voiceprint_id)
    if not vp or vp.user_id != user.id:
        raise HTTPException(status_code=404, detail="声纹不存在或无权使用")
    if vp.status != "ready" or not (vp.fast_voice_type or vp.voice_type):
        raise HTTPException(status_code=400, detail="声纹未就绪，无法试听")

    settings = get_settings()
    out = Path(settings.output_dir) / f"voiceprint_demo_{vp.id}.mp3"
    if not out.is_file():
        sdb = SessionLocal()
        try:
            synthesize_speech(
                sdb,
                "这是腾讯云声纹试听示例，用于确认音色是否符合预期。",
                out,
                language="zh-CN",
                tencent_voice_type=vp.voice_type,
                tencent_fast_voice_type=vp.fast_voice_type,
            )
        finally:
            sdb.close()
    return FileResponse(out, media_type="audio/mpeg", filename=f"demo_{vp.id}.mp3")


@router.post("/{voiceprint_id}/retry", response_model=VoicePrintOut)
async def retry_voiceprint(
    voiceprint_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    vp = await db.get(VoicePrint, voiceprint_id)
    if not vp or vp.user_id != user.id:
        raise HTTPException(status_code=404, detail="声纹不存在或无权使用")
    vp.status = "pending"
    vp.error = None
    vp.tencent_vrs_task_id = None
    vp.voice_type = None
    vp.fast_voice_type = None
    await db.flush()
    run_voice_clone_task.delay(vp.id)
    return _enrich(vp)

