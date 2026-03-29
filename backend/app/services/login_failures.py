"""登录失败计数（连续失败 ≥3 次需图形验证码）。Redis 不可用时回退内存。"""
from __future__ import annotations

import time

from app.config import get_settings
from app.services.kv_redis import get_async_redis
from app.services.verification import normalize_email

FAIL_KEY_PREFIX = "login_fail:"
FAIL_TTL_SEC = 30 * 60
_MEM_FAIL: dict[str, tuple[int, float]] = {}


def login_rate_key(login: str) -> str:
    """用于限流与失败计数：邮箱归一化，用户名小写。"""
    s = (login or "").strip()
    if "@" in s:
        return normalize_email(s)
    return s.lower()[:256]


def _cleanup_mem_fail() -> None:
    now = time.time()
    dead = [k for k, (_, exp) in _MEM_FAIL.items() if exp < now]
    for k in dead:
        del _MEM_FAIL[k]


async def get_fail_count(login_identifier: str) -> int:
    key = login_rate_key(login_identifier)
    r = await get_async_redis()
    if r is not None:
        v = await r.get(FAIL_KEY_PREFIX + key)
        return int(v) if v is not None else 0
    _cleanup_mem_fail()
    row = _MEM_FAIL.get(key)
    if not row:
        return 0
    cnt, exp = row
    if time.time() > exp:
        del _MEM_FAIL[key]
        return 0
    return cnt


async def record_login_failure(login_identifier: str) -> int:
    key = login_rate_key(login_identifier)
    r = await get_async_redis()
    if r is not None:
        rk = FAIL_KEY_PREFIX + key
        n = await r.incr(rk)
        if n == 1:
            await r.expire(rk, FAIL_TTL_SEC)
        return int(n)
    _cleanup_mem_fail()
    cnt, _ = _MEM_FAIL.get(key, (0, 0.0))
    cnt += 1
    _MEM_FAIL[key] = (cnt, time.time() + FAIL_TTL_SEC)
    return cnt


async def clear_login_failures(login_identifier: str) -> None:
    key = login_rate_key(login_identifier)
    r = await get_async_redis()
    if r is not None:
        await r.delete(FAIL_KEY_PREFIX + key)
        return
    _MEM_FAIL.pop(key, None)


async def needs_captcha(login_identifier: str) -> bool:
    settings = get_settings()
    n = await get_fail_count(login_identifier)
    return n >= settings.login_fail_captcha_threshold
