from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

import asyncio
import httpx

from app.config import get_settings


VIDEO_SYNTH_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis/"
TASK_STATUS_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"


def _public_video_url(web_base: str, relative_path: str) -> str:
    # relative_path example: "user_3/xxxx.mp4" (uploaded) or "outputs/xxx"
    # Nginx exposes:
    # - /uploads/* -> upload_dir
    # - /media/* -> output_dir
    if relative_path.startswith("/"):
        relative_path = relative_path[1:]
    return web_base.rstrip("/") + "/" + relative_path


async def create_videoretalk_task(
    *,
    api_key: str,
    web_base_url: str,
    input_video_path: Path,
    input_audio_path: Path,
    video_extension: bool = False,
) -> str:
    """
    创建 VideoRetalk 异步任务，并返回 task_id。

    说明：dashscope 只能抓取公网 URL，所以调用前需要把本地文件映射到 Nginx 暴露的 /uploads 或 /media。
    """

    # 本项目约定：上传视频走 /uploads；生成音频走 /media
    # input_video_path/input_audio_path 在我们后端文件系统内，外部抓取需要对应 web URL
    # 这里通过路径后缀构造 URL（基于 mounted paths）
    # 为了可控，我们要求外部传入的 path 是 upload_dir 或 output_dir 子路径。
    input_video_rel = input_video_path.as_posix()
    input_audio_rel = input_audio_path.as_posix()

    # 将绝对路径拆成 /uploads/.. 或 /media/.. 的相对段
    # 这里假设 input_video_path 形如 /data/uploads/<...>/xxx.mp4
    # 假设 input_audio_path 形如 /data/outputs/<...>/voice_xxx.mp3
    if "/uploads/" in input_video_rel:
        rel = input_video_rel.split("/uploads/", 1)[1]
        video_url = _public_video_url(web_base_url, "uploads/" + rel)
    else:
        # 降级：直接当成 /uploads/<relative>
        video_url = _public_video_url(web_base_url, "uploads/" + input_video_path.name)

    if "/outputs/" in input_audio_rel:
        rel = input_audio_rel.split("/outputs/", 1)[1]
        audio_url = _public_video_url(web_base_url, "media/" + rel)
    else:
        audio_url = _public_video_url(web_base_url, "media/" + input_audio_path.name)

    payload: dict[str, Any] = {
        "model": "videoretalk",
        "input": {
            "video_url": video_url,
            "audio_url": audio_url,
        },
        "parameters": {
            "video_extension": video_extension,
        },
    }

    headers = {
        "X-DashScope-Async": "enable",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            r = await client.post(VIDEO_SYNTH_URL, headers=headers, json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            # 403 这类问题通常有更明确的 response body，直接拼出来方便你在 UI 查看原因
            status = e.response.status_code
            text = ""
            try:
                text = e.response.text or ""
            except Exception:
                text = ""
            snippet = text[:2000]
            raise RuntimeError(f"VideoRetalk HTTP {status}: {snippet}")

        data = r.json()
        task_id = (data.get("output") or {}).get("task_id")
        if not task_id:
            # 兼容非标准返回
            raise RuntimeError(f"VideoRetalk 创建任务失败：{data}")
        return str(task_id)


async def wait_videoretalk_task(
    *,
    api_key: str,
    task_id: str,
    timeout_s: int = 20 * 60,
    poll_interval_s: int = 15,
) -> str:
    deadline = time.time() + timeout_s
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        while time.time() < deadline:
            url = TASK_STATUS_URL.format(task_id=task_id)
            try:
                r = await client.get(url, headers=headers)
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                text = ""
                try:
                    text = e.response.text or ""
                except Exception:
                    text = ""
                snippet = text[:2000]
                raise RuntimeError(f"VideoRetalk HTTP {status}: {snippet}")
            data = r.json()
            output = data.get("output") or {}
            status = output.get("task_status")
            if status == "SUCCEEDED":
                video_url = output.get("video_url") or ""
                if not video_url:
                    raise RuntimeError(f"VideoRetalk 成功但无 video_url：{data}")
                return str(video_url)
            if status == "FAILED":
                code = output.get("code") or "FAILED"
                msg = output.get("message") or ""
                raise RuntimeError(f"VideoRetalk 失败：{code} {msg}")
            # PENDING / RUNNING / POST-PROCESSING
            await asyncio.sleep(poll_interval_s)

    raise RuntimeError("VideoRetalk 超时等待任务完成")


async def download_file(url: str, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream("GET", url, follow_redirects=True) as resp:
            resp.raise_for_status()
            with dest_path.open("wb") as f:
                async for chunk in resp.aiter_bytes(1024 * 256):
                    if not chunk:
                        continue
                    f.write(chunk)

