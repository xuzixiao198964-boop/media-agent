"""Fish Audio TTS 服务 — 多角色语音合成。

无 API Key 时自动降级到 Edge TTS。
"""
import asyncio
from pathlib import Path

import edge_tts
import httpx

from app.config import get_settings
from app.services.keyvault import get_provider_key_sync

EDGE_VOICE_MAP = {
    "narrator_male": "zh-CN-YunxiNeural",
    "narrator_female": "zh-CN-XiaoxiaoNeural",
    "male": "zh-CN-YunjianNeural",
    "female": "zh-CN-XiaohanNeural",
}

FISH_DEFAULT_VOICES = {
    "narrator_female": "54a5170264694bfc8e9ad98df7bd89c3",
    "narrator_male": "7f92f8afb8ec43bf81429cc1c9199cb1",
    "female": "e4642e5edccd4d9ab61a69e82d4f8a14",
    "male": "7f92f8afb8ec43bf81429cc1c9199cb1",
}


def synthesize_fish(
    api_key: str,
    text: str,
    out_path: Path,
    model_id: str = "54a5170264694bfc8e9ad98df7bd89c3",
    *,
    format: str = "mp3",
) -> None:
    """调用 Fish Audio TTS REST API。"""
    settings = get_settings()
    url = f"{settings.fish_audio_base_url}/v1/tts"
    payload = {
        "text": text,
        "reference_id": model_id,
        "format": format,
    }
    with httpx.Client(timeout=120) as c:
        r = c.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(r.content)


def synthesize_edge_fallback(text: str, out_path: Path, voice_hint: str = "narrator_female") -> None:
    """Edge TTS 降级方案。"""
    voice = EDGE_VOICE_MAP.get(voice_hint, EDGE_VOICE_MAP["narrator_female"])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    async def _do():
        comm = edge_tts.Communicate(text, voice)
        await comm.save(str(out_path))

    asyncio.run(_do())


def synthesize_scene(
    db,
    text: str,
    out_path: Path,
    voice_id: str | None = None,
    gender: str = "female",
    is_narrator: bool = False,
) -> None:
    """为单个 scene 合成语音。优先 Fish Audio，无 key 则 Edge TTS。"""
    api_key = get_provider_key_sync(db, "fish_audio_api_key")

    if api_key:
        mid = voice_id
        if not mid:
            hint = f"narrator_{gender}" if is_narrator else gender
            mid = FISH_DEFAULT_VOICES.get(hint, FISH_DEFAULT_VOICES["narrator_female"])
        try:
            synthesize_fish(api_key, text, out_path, model_id=mid)
            return
        except Exception:
            pass

    hint = f"narrator_{gender}" if is_narrator else gender
    synthesize_edge_fallback(text, out_path, voice_hint=hint)
