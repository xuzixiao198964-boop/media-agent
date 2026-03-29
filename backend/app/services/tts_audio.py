import asyncio
import base64
import hashlib
import hmac
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import edge_tts
import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.keyvault import get_provider_key_sync
from app.services.flow_log import log_sync


VOICE_MAP = {
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "en-US": "en-US-EmmaNeural",
    "ja-JP": "ja-JP-NanamiNeural",
}


def synthesize_speech(
    db: Session,
    text: str,
    out_mp3: Path,
    language: str = "zh-CN",
    *,
    tencent_voice_type: int | None = None,
    tencent_fast_voice_type: str | None = None,
) -> None:
    settings = get_settings()

    # 1) 声纹/音色克隆优先：腾讯云 VRS 输出可用于 TextToVoice 的 FastVoiceType
    if tencent_fast_voice_type or tencent_voice_type:
        sid = get_provider_key_sync(db, "tencent_tts_secret_id")
        skey = get_provider_key_sync(db, "tencent_tts_secret_key")
        if sid and skey:
            try:
                _tencent_tts(
                    secret_id=sid,
                    secret_key=skey,
                    region=settings.tencent_tts_region,
                    text=text,
                    out_mp3=out_mp3,
                    voice_type=(
                        tencent_voice_type
                        if tencent_voice_type is not None
                        else (200000000 if tencent_fast_voice_type else settings.tencent_tts_voice_type)
                    ),
                    fast_voice_type=tencent_fast_voice_type,
                )
                d = ffprobe_duration(out_mp3)
                if d is not None and d > 0.5:
                    return
            except Exception as e:
                # 声纹失败不阻塞流水线：继续走 Edge/默认腾讯兜底
                log_sync(db, "api", None, "tencent_tts", str(e), "error")

    # 2) 主力：Edge TTS（默认音色）
    voice = VOICE_MAP.get(language, VOICE_MAP["zh-CN"])
    try:
        asyncio.run(_edge_tts(text, out_mp3, voice))
        d = ffprobe_duration(out_mp3)
        if d is not None and d > 0.5:
            return
    except Exception:
        pass

    # 3) 兜底：腾讯云 TTS（默认 VoiceType）
    sid = get_provider_key_sync(db, "tencent_tts_secret_id")
    skey = get_provider_key_sync(db, "tencent_tts_secret_key")
    if sid and skey:
        try:
            _tencent_tts(
                secret_id=sid,
                secret_key=skey,
                region=settings.tencent_tts_region,
                text=text,
                out_mp3=out_mp3,
                voice_type=settings.tencent_tts_voice_type,
            )
            d = ffprobe_duration(out_mp3)
            if d is not None and d > 0.5:
                return
        except Exception as e:
            log_sync(db, "api", None, "tencent_tts", str(e), "error")

    # 兼容保留：OpenAI（即使前端隐藏，也可能通过环境变量注入）
    key = get_provider_key_sync(db, "openai")
    if key:
        _openai_tts(key, settings.openai_tts_model, settings.openai_tts_voice, text, out_mp3)
        d = ffprobe_duration(out_mp3)
        if d is not None and d > 0.5:
            return

    raise RuntimeError("TTS 全部通道失败：Edge/Tencent/OpenAI 均不可用")


async def _edge_tts(text: str, out_mp3: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_mp3))


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _tencent_tts(
    secret_id: str,
    secret_key: str,
    region: str,
    text: str,
    out_mp3: Path,
    voice_type: int = 101001,
    fast_voice_type: str | None = None,
) -> None:
    service = "tts"
    host = "tts.tencentcloudapi.com"
    endpoint = f"https://{host}"
    action = "TextToVoice"
    version = "2019-08-23"
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))

    payload = {
        "Text": text[:150],
        "SessionId": uuid.uuid4().hex,
        "VoiceType": voice_type,
        "Codec": "mp3",
    }
    if fast_voice_type:
        # VRS 一句话声音复刻建议走 FastVoiceType（TTS 文档支持该字段）
        payload["FastVoiceType"] = fast_voice_type
    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    canonical_headers = "content-type:application/json; charset=utf-8\nhost:{}\nx-tc-action:{}\n".format(
        host, action.lower()
    )
    signed_headers = "content-type;host;x-tc-action"
    hashed_request_payload = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    canonical_request = (
        f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n"
        f"{canonical_headers}\n{signed_headers}\n{hashed_request_payload}"
    )

    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = (
        f"{algorithm}\n{timestamp}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )
    secret_date = _sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _sign(secret_date, service)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
        "X-TC-Region": region,
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(endpoint, headers=headers, content=payload_json.encode("utf-8"))
        r.raise_for_status()
        data = r.json()
        resp = data.get("Response", {})
        if "Error" in resp:
            raise RuntimeError(f"Tencent TTS 错误: {resp['Error']}")
        audio_b64 = resp.get("Audio") or ""
        if not audio_b64:
            raise RuntimeError("Tencent TTS 无音频返回")
        out_mp3.write_bytes(base64.b64decode(audio_b64))


def _openai_tts(api_key: str, model: str, voice: str, text: str, out_mp3: Path) -> None:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "voice": voice, "input": text[:4000], "format": "mp3"},
        )
        r.raise_for_status()
        out_mp3.write_bytes(r.content)


def ffprobe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        p = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(p.stdout.strip())
    except Exception:
        return None


def run_ffmpeg(args: list[str]) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg，请安装后再试")
    subprocess.run([ffmpeg, *args], check=True, capture_output=True, text=True)


def has_audio_stream(path: Path) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False
    try:
        p = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(p.stdout.strip())
    except Exception:
        return False
