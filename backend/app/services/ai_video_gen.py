"""AI 图生视频服务。

优先级：SiliconFlow Wan2.2-I2V → Seedance (SDK) → FFmpeg Ken Burns 兜底。
支持单场景和批量场景（并行提交 + 并行轮询）两种模式。
"""
import base64
import logging
import time
from pathlib import Path

import httpx

from app.config import get_settings
from app.services.keyvault import get_provider_key_sync
from app.services.tts_audio import run_ffmpeg

log = logging.getLogger(__name__)

SF_I2V_MODEL = "Wan-AI/Wan2.2-I2V-A14B"


def ai_image_to_video(
    db,
    image_path: Path,
    out_path: Path,
    duration: float = 5.0,
    prompt: str = "",
    aspect_ratio: str = "9:16",
) -> str:
    """单场景 AI 图生视频，返回使用的引擎名称。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sf_key = get_provider_key_sync(db, "siliconflow_api_key")
    if sf_key:
        rid = _submit_siliconflow_i2v(sf_key, image_path, prompt)
        if rid:
            settings = get_settings()
            base = settings.siliconflow_base_url.rstrip("/")
            video_url = _poll_siliconflow(base, sf_key, rid, max_wait=300)
            if video_url and _download_video(video_url, out_path):
                return "siliconflow"

    sd_ak = get_provider_key_sync(db, "seedance_access_key")
    sd_sk = get_provider_key_sync(db, "seedance_secret_key") or ""
    if sd_ak:
        ok = _seedance_i2v(sd_ak, sd_sk, image_path, out_path, duration, prompt, aspect_ratio)
        if ok:
            return "seedance"

    _kenburns_fallback(image_path, duration, out_path)
    return "kenburns"


# ── Batch I2V ────────────────────────────────────────────────────────


def batch_ai_image_to_video(
    db,
    tasks: list[dict],
    max_wait: int = 600,
) -> dict[int, str]:
    """批量 I2V：一次提交所有场景，并行轮询，Ken Burns 兜底。

    tasks: [{"scene_id": int, "image_path": Path, "out_path": Path,
             "duration": float, "prompt": str}]
    Returns: {scene_id: engine_name}
    """
    results: dict[int, str] = {}
    if not tasks:
        return results

    sf_key = get_provider_key_sync(db, "siliconflow_api_key")
    settings = get_settings()
    base = settings.siliconflow_base_url.rstrip("/")

    if not sf_key:
        for t in tasks:
            t["out_path"].parent.mkdir(parents=True, exist_ok=True)
            _kenburns_fallback(t["image_path"], t["duration"], t["out_path"])
            results[t["scene_id"]] = "kenburns"
        return results

    # Phase 1: Submit all
    pending: dict[str, dict] = {}
    t0 = time.time()
    for t in tasks:
        t["out_path"].parent.mkdir(parents=True, exist_ok=True)
        rid = _submit_siliconflow_i2v(sf_key, t["image_path"], t["prompt"])
        if rid:
            pending[rid] = t
            log.info("I2V submit scene %d → %s", t["scene_id"], rid)
        else:
            _kenburns_fallback(t["image_path"], t["duration"], t["out_path"])
            results[t["scene_id"]] = "kenburns"
        time.sleep(0.5)

    submit_elapsed = time.time() - t0
    log.info("I2V batch submitted %d/%d in %.1fs", len(pending), len(tasks), submit_elapsed)

    if not pending:
        return results

    # Phase 2: Poll all concurrently
    headers = {"Authorization": f"Bearer {sf_key}", "Content-Type": "application/json"}
    deadline = time.time() + max_wait
    interval = 5

    with httpx.Client(timeout=30) as c:
        while pending and time.time() < deadline:
            time.sleep(interval)
            done_rids: list[str] = []

            for rid, task in list(pending.items()):
                try:
                    r = c.post(
                        f"{base}/v1/video/status",
                        headers=headers,
                        json={"requestId": rid},
                    )
                    r.raise_for_status()
                    data = r.json()
                    status = data.get("status", "")

                    if status == "Succeed":
                        videos = data.get("results", {}).get("videos", [])
                        url = videos[0].get("url") if videos else None
                        if url and _download_video(url, task["out_path"]):
                            results[task["scene_id"]] = "siliconflow"
                            log.info("I2V done scene %d (%.0fs)", task["scene_id"], time.time() - t0)
                        else:
                            _kenburns_fallback(task["image_path"], task["duration"], task["out_path"])
                            results[task["scene_id"]] = "kenburns"
                        done_rids.append(rid)

                    elif status == "Failed":
                        reason = data.get("reason", "unknown")
                        log.warning("I2V failed scene %d: %s", task["scene_id"], reason)
                        _kenburns_fallback(task["image_path"], task["duration"], task["out_path"])
                        results[task["scene_id"]] = "kenburns"
                        done_rids.append(rid)

                except Exception as e:
                    log.debug("I2V poll error for %s: %s", rid, e)

                time.sleep(0.3)

            for rid in done_rids:
                del pending[rid]

            if pending:
                n_done = len(tasks) - len(pending) - sum(1 for v in results.values() if v == "kenburns" and v)
                log.info("I2V progress: %d/%d done, %d pending", len(results), len(tasks), len(pending))

            if interval < 15:
                interval = min(interval + 1, 15)

    # Phase 3: Timeout → Ken Burns fallback
    for rid, task in pending.items():
        log.warning("I2V timeout scene %d after %ds, Ken Burns fallback", task["scene_id"], max_wait)
        _kenburns_fallback(task["image_path"], task["duration"], task["out_path"])
        results[task["scene_id"]] = "kenburns"

    elapsed = time.time() - t0
    sf_count = sum(1 for v in results.values() if v == "siliconflow")
    kb_count = sum(1 for v in results.values() if v == "kenburns")
    log.info("I2V batch done in %.1fs: %d siliconflow, %d kenburns", elapsed, sf_count, kb_count)
    return results


# ── SiliconFlow I2V ──────────────────────────────────────────────────


def _submit_siliconflow_i2v(api_key: str, image_path: Path, prompt: str) -> str | None:
    """提交单个 I2V 任务，返回 requestId。"""
    settings = get_settings()
    base = settings.siliconflow_base_url.rstrip("/")

    img_b64 = base64.b64encode(image_path.read_bytes()).decode()
    suffix = image_path.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(suffix, "image/png")
    image_url = f"data:{mime};base64,{img_b64}"

    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                f"{base}/v1/video/submit",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": SF_I2V_MODEL,
                    "prompt": (prompt or "gentle camera movement, cinematic")[:500],
                    "image": image_url,
                },
            )
            if r.status_code != 200:
                log.warning("I2V submit failed: %s %s", r.status_code, r.text[:200])
                return None
            return r.json().get("requestId")
    except Exception as e:
        log.warning("I2V submit error: %s", e)
        return None


def _download_video(url: str, out_path: Path) -> bool:
    """下载视频文件，成功返回 True。"""
    try:
        with httpx.Client(timeout=120) as c:
            resp = c.get(url)
            resp.raise_for_status()
            out_path.write_bytes(resp.content)
        return out_path.is_file() and out_path.stat().st_size > 1000
    except Exception as e:
        log.warning("Video download failed: %s", e)
        return False


def _poll_siliconflow(base: str, api_key: str, request_id: str, max_wait: int = 300) -> str | None:
    """轮询单个 SiliconFlow 视频任务直到完成。"""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    deadline = time.time() + max_wait
    interval = 5

    with httpx.Client(timeout=30) as c:
        while time.time() < deadline:
            time.sleep(interval)
            try:
                r = c.post(
                    f"{base}/v1/video/status",
                    headers=headers,
                    json={"requestId": request_id},
                )
                r.raise_for_status()
                data = r.json()
                status = data.get("status", "")

                if status == "Succeed":
                    videos = data.get("results", {}).get("videos", [])
                    if videos:
                        return videos[0].get("url")
                    return None
                elif status == "Failed":
                    log.warning("SiliconFlow I2V task %s failed", request_id)
                    return None

                if interval < 15:
                    interval += 2
            except Exception:
                pass

    return None


def _seedance_i2v(
    access_key: str,
    secret_key: str,
    image_path: Path,
    out_path: Path,
    duration: float,
    prompt: str,
    aspect_ratio: str = "9:16",
) -> bool:
    """Seedance 图生视频（火山引擎方舟 SDK）。

    认证方式（按优先级）：
    1. secret_key 为空 → access_key 整体作为 API Key（支持 ark-xxx 或 UUID 格式）
    2. 两者都有 → AK/SK 模式
    """
    try:
        from volcenginesdkarkruntime import Ark
    except ImportError:
        log.warning("volcenginesdkarkruntime not installed, skip Seedance")
        return False

    try:
        if not secret_key:
            client = Ark(api_key=access_key, base_url="https://ark.cn-beijing.volces.com/api/v3")
        else:
            client = Ark(ak=access_key, sk=secret_key, base_url="https://ark.cn-beijing.volces.com/api/v3")

        img_b64 = base64.b64encode(image_path.read_bytes()).decode()
        suffix = image_path.suffix.lower().lstrip(".")
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(suffix, "image/png")

        task = client.content_generation.tasks.create(
            model="seedance-1-lite-i2v-t1",
            content=[
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                {"type": "text", "text": (prompt or "gentle natural movement, cinematic")[:500]},
            ],
        )
        task_id = task.id if hasattr(task, "id") else None
        if not task_id:
            log.warning("Seedance: no task ID returned")
            return False

        deadline = time.time() + 300
        interval = 8
        while time.time() < deadline:
            time.sleep(interval)
            result = client.content_generation.tasks.get(task_id=task_id)
            status = result.status if hasattr(result, "status") else ""
            if status in ("succeeded", "Succeed", "COMPLETED"):
                video_url = None
                if hasattr(result, "content") and result.content:
                    content = result.content
                    if hasattr(content, "video_url"):
                        video_url = content.video_url
                    elif isinstance(content, dict):
                        video_url = content.get("video_url")
                        if not video_url:
                            for item in content.get("items", []):
                                if item.get("type") == "video_url":
                                    video_url = item.get("video_url", {}).get("url")
                                    break
                if video_url:
                    with httpx.Client(timeout=120) as c:
                        resp = c.get(video_url)
                        resp.raise_for_status()
                        out_path.write_bytes(resp.content)
                    return out_path.is_file() and out_path.stat().st_size > 1000
                return False
            elif status in ("failed", "Failed", "FAILED"):
                log.warning("Seedance task %s failed", task_id)
                return False
            if interval < 15:
                interval += 2

        return False
    except Exception as e:
        log.warning("Seedance I2V error: %s", e)
        return False


def _kenburns_fallback(image_path: Path, duration: float, out_path: Path) -> None:
    """FFmpeg Ken Burns 缓动效果作为兜底。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dur = max(duration, 1.0)
    run_ffmpeg([
        "-y", "-loop", "1", "-i", str(image_path),
        "-vf", f"zoompan=z='min(zoom+0.0008,1.15)':d={int(dur * 25)}:s=1080x1920:fps=25",
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(out_path),
    ])
