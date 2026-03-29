"""硅基流动 AI 图片生成服务（可选，Phase 2）。

无 API Key 时使用 PIL 占位图（novel_compose.generate_scene_image）。
"""
import httpx
from pathlib import Path

from app.config import get_settings
from app.services.keyvault import get_provider_key_sync


def generate_image(
    db,
    prompt: str,
    out_path: Path,
    width: int = 1080,
    height: int = 1920,
    negative_prompt: str = "blurry, deformed, ugly, modern elements, text, watermark",
) -> bool:
    """调用硅基流动生图 API。成功返回 True，失败返回 False（调用方降级到占位图）。"""
    api_key = get_provider_key_sync(db, "siliconflow_api_key")
    if not api_key:
        return False

    settings = get_settings()
    url = f"{settings.siliconflow_base_url}/v1/images/generations"
    try:
        with httpx.Client(timeout=120) as c:
            r = c.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": settings.siliconflow_model,
                    "prompt": prompt[:500],
                    "negative_prompt": negative_prompt,
                    "image_size": f"{width}x{height}",
                    "num_inference_steps": 20,
                    "batch_size": 1,
                },
            )
            r.raise_for_status()
            data = r.json()
            image_url = data["images"][0]["url"]
            img_resp = c.get(image_url, timeout=60)
            img_resp.raise_for_status()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(img_resp.content)
            return True
    except Exception:
        return False
