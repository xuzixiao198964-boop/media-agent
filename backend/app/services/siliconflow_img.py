"""硅基流动 AI 图片生成服务（可选，Phase 2）。

无 API Key 时使用 PIL 占位图（novel_compose.generate_scene_image）。
"""
import logging
import time

import httpx
from pathlib import Path

from app.config import get_settings
from app.services.keyvault import get_provider_key_sync

log = logging.getLogger(__name__)

MAX_RETRIES = 3


def generate_image(
    db,
    prompt: str,
    out_path: Path,
    width: int = 1080,
    height: int = 1920,
    negative_prompt: str = "blurry, deformed, ugly, modern elements, text, watermark",
) -> bool:
    """调用硅基流动生图 API，含 429 限流退避重试。"""
    api_key = get_provider_key_sync(db, "siliconflow_api_key")
    if not api_key:
        return False

    settings = get_settings()
    url = f"{settings.siliconflow_base_url}/v1/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": settings.siliconflow_model,
        "prompt": prompt[:500],
        "negative_prompt": negative_prompt,
        "image_size": f"{width}x{height}",
        "num_inference_steps": 20,
        "batch_size": 1,
    }

    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=120) as c:
                r = c.post(url, headers=headers, json=body)
                if r.status_code == 429:
                    wait = 3 * (attempt + 1)
                    log.info("Image gen 429 rate limited, retry in %ds (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                data = r.json()
                image_url = data["images"][0]["url"]
                img_resp = c.get(image_url, timeout=60)
                img_resp.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(img_resp.content)
                return True
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                log.debug("Image gen error (attempt %d): %s", attempt + 1, e)
                time.sleep(2)
            else:
                log.warning("Image gen failed after %d attempts: %s", MAX_RETRIES, e)
    return False
