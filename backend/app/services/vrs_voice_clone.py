import base64
import hashlib
import hmac
import json
import tempfile
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.keyvault import get_provider_key_sync
from app.services.tts_audio import ffprobe_duration


VRS_VERSION = "2020-08-24"
VRS_HOST = "vrs.tencentcloudapi.com"
VRS_SERVICE = "vrs"
VRS_SAMPLE_RATE = 48000

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _tc3_request(
    *,
    secret_id: str,
    secret_key: str,
    region: str,
    action: str,
    payload: dict[str, Any],
    service: str,
    host: str,
    version: str,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))

    payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    hashed_request_payload = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    canonical_headers = (
        f"content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
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

    endpoint = f"https://{host}"
    with httpx.Client(timeout=timeout_s) as client:
        r = client.post(endpoint, headers=headers, content=payload_json.encode("utf-8"))
        r.raise_for_status()
        data = r.json()
        resp = data.get("Response") or {}
        if "Error" in resp:
            raise RuntimeError(f"VRS 错误: {resp['Error']}")
        # 大部分接口返回结构是 Response.Data.<xxx>
        return resp.get("Data") or resp


def _extract_wav_mono_snippet(
    in_path: Path,
    out_wav: Path,
    *,
    clip_seconds: float = 10.0,
    start_seconds: float = 1.0,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("未找到 ffmpeg")

    # VRS 一句话复刻：音频长度需 >5s 且 <15s（建议在 5~15 秒内取样）
    dur = ffprobe_duration(in_path)
    if dur is None:
        raise RuntimeError("无法获取音频时长")
    if dur < 5.0:
        raise RuntimeError(f"音频时长过短：{dur:.2f}s（需 >5s）")

    start = min(float(start_seconds), float(dur - 0.1))
    remaining = float(dur) - start
    if remaining <= 5.0:
        raise RuntimeError(f"裁剪起点后剩余时长过短：{remaining:.2f}s（需 >5s）")

    final_clip = min(float(clip_seconds), remaining)
    if final_clip >= 15.0:
        final_clip = 10.0

    if final_clip <= 5.0:
        raise RuntimeError(f"裁剪后音频时长过短：{final_clip:.2f}s（需 >5s）")

    # 将源音频/视频抽取为 wav(16k/单声道)
    # 从起点抽取 [-t 控制时长] 的音频流，-vn 丢弃视频流
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        str(start),
        "-i",
        str(in_path),
        "-t",
        str(final_clip),
        "-vn",
        "-af",
        "highpass=f=80,lowpass=f=6500,volume=2.0",
        "-ac",
        "1",
        "-ar",
        str(VRS_SAMPLE_RATE),
        "-sample_fmt",
        "s16",
        str(out_wav),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _get_vrs_training_text_list(
    *,
    secret_id: str,
    secret_key: str,
    region: str,
    task_type: int = 5,
    domain: int = 0,
    text_language: int = 1,
) -> list[dict[str, Any]]:
    resp = _tc3_request(
        secret_id=secret_id,
        secret_key=secret_key,
        region=region,
        # 腾讯云 VRS：接口取值 Action=GetTrainingText
        action="GetTrainingText",
        payload={"TaskType": task_type, "Domain": domain, "TextLanguage": text_language},
        service=VRS_SERVICE,
        host=VRS_HOST,
        version=VRS_VERSION,
    )
    lst = resp.get("TrainingTextList") or []
    if not lst:
        raise RuntimeError("VRS 获取训练文本失败：空 TrainingTextList")
    return list(lst)


def _detect_env_and_sound_quality(
    *,
    secret_id: str,
    secret_key: str,
    region: str,
    text_id: str,
    audio_wav_path: Path,
    type_id: int = 2,
    task_type: int = 5,
) -> tuple[Optional[str], Optional[int], str]:
    b = audio_wav_path.read_bytes()
    audio_b64 = base64.b64encode(b).decode("utf-8")
    resp = _tc3_request(
        secret_id=secret_id,
        secret_key=secret_key,
        region=region,
        action="DetectEnvAndSoundQuality",
        payload={
            "TextId": text_id,
            "AudioData": audio_b64,
            "TypeId": type_id,
            "Codec": "wav",
            "SampleRate": VRS_SAMPLE_RATE,
            "TaskType": task_type,
        },
        service=VRS_SERVICE,
        host=VRS_HOST,
        version=VRS_VERSION,
    )
    audio_id = resp.get("AudioId") or None
    detection_code_raw = resp.get("DetectionCode")
    detection_code = int(detection_code_raw) if detection_code_raw is not None else None
    detection_msg = str(resp.get("DetectionMsg") or "")
    return (str(audio_id) if audio_id else None, detection_code, detection_msg)


def _create_vrs_task(
    *,
    secret_id: str,
    secret_key: str,
    region: str,
    audio_id: str,
    voice_name: str,
    voice_gender: int = 1,
    voice_language: int = 1,
    task_type: int = 5,
) -> str:
    session_id = uuid.uuid4().hex
    resp = _tc3_request(
        secret_id=secret_id,
        secret_key=secret_key,
        region=region,
        action="CreateVRSTask",
        payload={
            "SessionId": session_id,
            "VoiceName": voice_name,
            "VoiceGender": voice_gender,
            "VoiceLanguage": voice_language,
            "AudioIdList": [audio_id],
            "TaskType": task_type,
        },
        service=VRS_SERVICE,
        host=VRS_HOST,
        version=VRS_VERSION,
    )
    task_id = resp.get("TaskId")
    if not task_id:
        raise RuntimeError(f"VRS 创建任务失败：{resp}")
    return str(task_id)


def _describe_vrs_task_status(
    *,
    secret_id: str,
    secret_key: str,
    region: str,
    task_id: str,
) -> dict[str, Any]:
    resp = _tc3_request(
        secret_id=secret_id,
        secret_key=secret_key,
        region=region,
        action="DescribeVRSTaskStatus",
        payload={"TaskId": task_id},
        service=VRS_SERVICE,
        host=VRS_HOST,
        version=VRS_VERSION,
    )
    return resp


def clone_voiceprint_vrs_one_sentence(
    db: Session,
    *,
    input_path: Path,
    voice_name: str,
    voice_gender: int = 1,
    voice_language: int = 1,
    region: Optional[str] = None,
    timeout_s: int = 600,
) -> tuple[Optional[int], Optional[str]]:
    """
    腾讯云 VRS 一句话声音复刻（TaskType=5）。

    返回：
    - voice_type：用于 TTS 的 VoiceType（通常为固定 200000000）
    - fast_voice_type：用于 TTS 的 FastVoiceType（推荐用于一句话复刻）
    """

    settings = get_settings()
    region = region or settings.tencent_tts_region

    secret_id = get_provider_key_sync(db, "tencent_tts_secret_id")
    secret_key = get_provider_key_sync(db, "tencent_tts_secret_key")
    if not secret_id or not secret_key:
        raise RuntimeError("腾讯云 SecretId/SecretKey 未配置，无法进行 VRS 声音复刻")

    with tempfile.TemporaryDirectory() as td:
        # NOTE: 这里临时目录用于生成 wav，避免污染最终文件
        td_path = Path(td)
        wav_path = td_path / "sample.wav"
        training_list = _get_vrs_training_text_list(
            secret_id=secret_id,
            secret_key=secret_key,
            region=region,
        )

        audio_id: Optional[str] = None
        last_detection_code: Optional[int] = None
        last_detection_msg = ""

        # 多起点裁剪：避免截到静音/转场导致语音检测失败
        start_candidates = [0.0, 1.0, 2.0]
        for start_seconds in start_candidates:
            _extract_wav_mono_snippet(input_path, wav_path, start_seconds=start_seconds)

            # 尝试多个候选 TextId，提升通过率（控制接口调用次数）
            for item in training_list[:12]:
                text_id = str(item.get("TextId") or "")
                if not text_id:
                    continue

                # 先环境检测（TypeId=1），再音质检测（TypeId=2）
                _, env_code, env_msg = _detect_env_and_sound_quality(
                    secret_id=secret_id,
                    secret_key=secret_key,
                    region=region,
                    text_id=text_id,
                    audio_wav_path=wav_path,
                    type_id=1,
                )
                # TypeId=1 的响应里有时不返回 DetectionCode；仅当它存在且明确非 0 才认为失败
                if env_code is not None and env_code != 0:
                    last_detection_code = env_code
                    last_detection_msg = env_msg
                    continue

                a_id, d_code, d_msg = _detect_env_and_sound_quality(
                    secret_id=secret_id,
                    secret_key=secret_key,
                    region=region,
                    text_id=text_id,
                    audio_wav_path=wav_path,
                    type_id=2,
                )
                last_detection_code = d_code
                last_detection_msg = d_msg
                if a_id:
                    audio_id = a_id
                    break

            if audio_id:
                break

        if not audio_id:
            raise RuntimeError(f"VRS 音质检测失败：code={last_detection_code}, msg={last_detection_msg}")
        task_id = _create_vrs_task(
            secret_id=secret_id,
            secret_key=secret_key,
            region=region,
            audio_id=audio_id,
            voice_name=voice_name,
            voice_gender=voice_gender,
            voice_language=voice_language,
        )

        deadline = time.time() + timeout_s
        while time.time() < deadline:
            status_resp = _describe_vrs_task_status(
                secret_id=secret_id,
                secret_key=secret_key,
                region=region,
                task_id=task_id,
            )
            status = status_resp.get("Status")
            if status == 2:
                voice_type = status_resp.get("VoiceType")
                fast_voice_type = status_resp.get("FastVoiceType")
                return voice_type, fast_voice_type
            if status == 3:
                err = status_resp.get("ErrorMsg") or "unknown error"
                raise RuntimeError(f"VRS 声音复刻失败：{err}")
            time.sleep(5)

        raise RuntimeError("VRS 声音复刻超时")

