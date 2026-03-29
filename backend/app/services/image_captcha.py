"""PNG 图形验证码（干扰线/噪点）；答案存 Redis 或内存。"""
from __future__ import annotations

import base64
import io
import random
import secrets
import time
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.services.kv_redis import get_async_redis

CAPTCHA_TTL_SEC = 300
_MEM_CAPTCHA: dict[str, tuple[str, float]] = {}

# 排除易混淆字符
_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _cleanup_mem() -> None:
    now = time.time()
    dead = [k for k, (_, exp) in _MEM_CAPTCHA.items() if exp < now]
    for k in dead:
        del _MEM_CAPTCHA[k]


def _pick_font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _random_chars(n: int = 5) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def _render_png(text: str) -> bytes:
    w, h = 180, 64
    img = Image.new("RGB", (w, h), (18, 22, 32))
    draw = ImageDraw.Draw(img)
    font = _pick_font(34)
    # 干扰线
    for _ in range(8):
        x1, y1 = random.randint(0, w), random.randint(0, h)
        x2, y2 = random.randint(0, w), random.randint(0, h)
        draw.line([(x1, y1), (x2, y2)], fill=(60, 80, 120), width=1)
    # 噪点
    for _ in range(120):
        x, y = random.randint(0, w - 1), random.randint(0, h - 1)
        img.putpixel((x, y), (random.randint(80, 180),) * 3)
    # 文字（轻微旋转由逐字偏移模拟）
    x = 14
    for ch in text:
        y = random.randint(10, 18)
        color = (random.randint(160, 230), random.randint(160, 230), random.randint(200, 255))
        draw.text((x, y), ch, font=font, fill=color)
        x += 28 + random.randint(-2, 3)
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@dataclass
class CaptchaCreated:
    captcha_id: str
    image_base64: str


async def create_image_captcha() -> CaptchaCreated:
    plain = _random_chars(5)
    answer = plain.lower()
    cid = secrets.token_urlsafe(16)
    exp = time.time() + CAPTCHA_TTL_SEC
    png = _render_png(plain)
    b64 = base64.b64encode(png).decode("ascii")
    r = await get_async_redis()
    if r is not None:
        await r.setex(f"captcha:{cid}", CAPTCHA_TTL_SEC, answer)
    else:
        _cleanup_mem()
        _MEM_CAPTCHA[cid] = (answer, exp)
    return CaptchaCreated(captcha_id=cid, image_base64=b64)


async def verify_image_captcha(captcha_id: str | None, plain: str | None) -> bool:
    if not captcha_id or plain is None:
        return False
    cid = captcha_id.strip()
    guess = "".join(c for c in (plain or "").strip().lower() if c.isalnum())
    if len(guess) < 4 or len(guess) > 8:
        return False
    r = await get_async_redis()
    if r is not None:
        key = f"captcha:{cid}"
        stored = await r.get(key)
        if stored is None:
            return False
        await r.delete(key)
        return stored == guess
    _cleanup_mem()
    row = _MEM_CAPTCHA.pop(cid, None)
    if not row:
        return False
    ans, exp = row
    if time.time() > exp:
        return False
    return ans == guess
