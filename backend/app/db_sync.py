"""Celery worker 使用的同步数据库会话。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()
_sync_url = _settings.database_url.replace("+asyncpg", "")
sync_engine = create_engine(_sync_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)


def sync_session() -> Session:
    return SessionLocal()
