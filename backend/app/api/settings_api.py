from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import get_current_user
from app.database import get_db
from app.models import ApiSecret, FlowLog, User
from app.services.keyvault import encrypt_value

router = APIRouter(prefix="/settings", tags=["settings"])


class ApiKeysIn(BaseModel):
    deepseek: Optional[str] = None
    openai: Optional[str] = None
    tencent_tts_secret_id: Optional[str] = None
    tencent_tts_secret_key: Optional[str] = None
    trtc_sdk_app_id: Optional[str] = None
    trtc_secret_id: Optional[str] = None
    trtc_secret_key: Optional[str] = None
    trtc_region: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    fish_audio_api_key: Optional[str] = None
    siliconflow_api_key: Optional[str] = None
    seedance_access_key: Optional[str] = None
    seedance_secret_key: Optional[str] = None


class ApiKeysStatus(BaseModel):
    deepseek_configured: bool
    openai_configured: bool
    tencent_tts_configured: bool
    trtc_voice_clone_configured: bool
    dashscope_configured: bool
    fish_audio_configured: bool = False
    siliconflow_configured: bool = False
    seedance_configured: bool = False
    tencent_tts_last_error: Optional[str] = None
    dashscope_last_error: Optional[str] = None
    publish_mode: str


async def _upsert_secret(db: AsyncSession, provider: str, plain: str):
    plain = plain.strip()
    if not plain:
        return
    enc = encrypt_value(plain)
    row = await db.execute(select(ApiSecret).where(ApiSecret.provider == provider))
    existing = row.scalar_one_or_none()
    if existing:
        existing.value_enc = enc
    else:
        db.add(ApiSecret(provider=provider, value_enc=enc))


@router.get("/api-keys", response_model=ApiKeysStatus)
async def keys_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    settings = get_settings()

    async def has(provider: str) -> bool:
        env_map = {
            "deepseek": settings.deepseek_api_key,
            "gemini": settings.gemini_api_key,
            "openai": settings.openai_api_key,
            "tencent_tts_secret_id": settings.tencent_tts_secret_id,
            "tencent_tts_secret_key": settings.tencent_tts_secret_key,
            "trtc_sdk_app_id": settings.trtc_sdk_app_id,
            "trtc_secret_id": settings.trtc_secret_id or settings.tencent_tts_secret_id,
            "trtc_secret_key": settings.trtc_secret_key or settings.tencent_tts_secret_key,
            "trtc_region": settings.trtc_region or settings.tencent_tts_region,
            "dashscope_api_key": settings.dashscope_api_key,
            "fish_audio_api_key": settings.fish_audio_api_key,
            "siliconflow_api_key": settings.siliconflow_api_key,
            "seedance_access_key": settings.seedance_access_key,
            "seedance_secret_key": settings.seedance_secret_key,
        }
        if (env_map.get(provider) or "").strip():
            return True
        r = await db.execute(select(ApiSecret.id).where(ApiSecret.provider == provider))
        return r.scalar_one_or_none() is not None

    async def latest_api_error(step: str) -> Optional[str]:
        q = (
            select(FlowLog.message)
            .where(FlowLog.ref_type == "api", FlowLog.step == step, FlowLog.level == "error")
            .order_by(FlowLog.id.desc())
            .limit(1)
        )
        row = (await db.execute(q)).scalar_one_or_none()
        return row

    return ApiKeysStatus(
        deepseek_configured=await has("deepseek"),
        openai_configured=await has("openai"),
        tencent_tts_configured=(await has("tencent_tts_secret_id")) and (await has("tencent_tts_secret_key")),
        trtc_voice_clone_configured=(
            (await has("tencent_tts_secret_id"))
            and (await has("tencent_tts_secret_key"))
        )
        and (await has("trtc_sdk_app_id"))
        and (await has("trtc_region")),
        dashscope_configured=await has("dashscope_api_key"),
        fish_audio_configured=await has("fish_audio_api_key"),
        siliconflow_configured=await has("siliconflow_api_key"),
        seedance_configured=(await has("seedance_access_key")) and (await has("seedance_secret_key")),
        tencent_tts_last_error=await latest_api_error("tencent_tts"),
        dashscope_last_error=await latest_api_error("dashscope_videoretalk"),
        publish_mode=settings.publish_mode,
    )


@router.post("/api-keys", response_model=ApiKeysStatus)
async def save_keys(
    data: ApiKeysIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    if data.deepseek:
        await _upsert_secret(db, "deepseek", data.deepseek)
    if data.openai:
        await _upsert_secret(db, "openai", data.openai)
    if data.tencent_tts_secret_id:
        await _upsert_secret(db, "tencent_tts_secret_id", data.tencent_tts_secret_id)
    if data.tencent_tts_secret_key:
        await _upsert_secret(db, "tencent_tts_secret_key", data.tencent_tts_secret_key)

    if data.trtc_sdk_app_id:
        await _upsert_secret(db, "trtc_sdk_app_id", data.trtc_sdk_app_id)
    if data.trtc_secret_id:
        await _upsert_secret(db, "trtc_secret_id", data.trtc_secret_id)
    if data.trtc_secret_key:
        await _upsert_secret(db, "trtc_secret_key", data.trtc_secret_key)
    if data.trtc_region:
        await _upsert_secret(db, "trtc_region", data.trtc_region)
    if data.dashscope_api_key:
        await _upsert_secret(db, "dashscope_api_key", data.dashscope_api_key)
    if data.fish_audio_api_key:
        await _upsert_secret(db, "fish_audio_api_key", data.fish_audio_api_key)
    if data.siliconflow_api_key:
        await _upsert_secret(db, "siliconflow_api_key", data.siliconflow_api_key)
    if data.seedance_access_key:
        await _upsert_secret(db, "seedance_access_key", data.seedance_access_key)
    if data.seedance_secret_key:
        await _upsert_secret(db, "seedance_secret_key", data.seedance_secret_key)
    await db.flush()
    return await keys_status(db, _)
