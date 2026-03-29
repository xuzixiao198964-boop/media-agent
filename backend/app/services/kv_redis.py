"""Async Redis 单例；不可用时为 None（由调用方回退内存）。"""
from __future__ import annotations

import redis.asyncio as redis

from app.config import get_settings

_client: redis.Redis | None = None


async def get_async_redis() -> redis.Redis | None:
    global _client
    if _client is not None:
        return _client
    try:
        r = redis.from_url(get_settings().redis_url, decode_responses=True)
        await r.ping()
        _client = r
        return _client
    except Exception:
        return None
