import base64
import hashlib

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ApiSecret


def _fernet() -> Fernet:
    s = get_settings()
    key = base64.urlsafe_b64encode(hashlib.sha256(s.secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_value(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_value(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def get_provider_key_sync(db: Session, provider: str) -> str:
    settings = get_settings()
    # 兼容合并输入：当请求 TRTC SecretId/SecretKey 时，
    # 如果服务端没有单独存 TRTC 字段，则回退到腾讯云 TTS 的字段。
    alias_map = {
        "trtc_secret_id": "tencent_tts_secret_id",
        "trtc_secret_key": "tencent_tts_secret_key",
        "trtc_region": "tencent_tts_region",
    }
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
        "kling_access_key": settings.kling_access_key,
        "kling_secret_key": settings.kling_secret_key,
    }
    v = env_map.get(provider, "") or ""
    if v.strip():
        return v.strip()
    row = db.execute(select(ApiSecret).where(ApiSecret.provider == provider)).scalar_one_or_none()
    if row:
        return decrypt_value(row.value_enc)
    # DB 内没有独立 TRTC 配置时，回退到腾讯云 TTS 对应字段。
    alias = alias_map.get(provider)
    if alias and alias != provider:
        return get_provider_key_sync(db, alias)
    return ""
