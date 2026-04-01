"""共享测试 fixtures。"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# 必须在导入 app 之前设置环境变量
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Mock database module to avoid actual DB connection at import time
import importlib
from unittest.mock import MagicMock as _MM

_mock_engine = _MM()
_mock_session = _MM()

# Pre-create a fake database module
import types
_db_mod = types.ModuleType("app.database")
from sqlalchemy.orm import DeclarativeBase

class _FakeBase(DeclarativeBase):
    __abstract__ = True

_db_mod.Base = _FakeBase
_db_mod.engine = _mock_engine
_db_mod.AsyncSessionLocal = _mock_session
_db_mod.get_db = _MM()
sys.modules["app.database"] = _db_mod

# Also mock db_sync to avoid import issues
_db_sync_mod = types.ModuleType("app.db_sync")
_db_sync_mod.SessionLocal = _MM
sys.modules["app.db_sync"] = _db_sync_mod

import pytest


@pytest.fixture
def mock_db():
    """模拟数据库 session。"""
    db = MagicMock()
    db.get = MagicMock(return_value=None)
    db.execute = MagicMock()
    db.commit = MagicMock()
    db.close = MagicMock()
    return db


@pytest.fixture
def sample_scenes():
    return [
        {
            "scene_id": 1,
            "type": "narration",
            "speaker": "narrator",
            "text": "话说贾雨村在扬州城中寄居",
            "visual_prompt": "古代扬州城街景，黄昏时分，落魄书生独自饮酒",
            "mood": "melancholy",
            "duration_hint": 8,
        },
        {
            "scene_id": 2,
            "type": "dialogue",
            "speaker": "贾雨村",
            "text": "玉在匮中求善价",
            "visual_prompt": "书生窗前仰望明月，衣衫微旧眼神坚定",
            "mood": "ambitious",
            "duration_hint": 6,
        },
    ]


@pytest.fixture
def sample_raw_text():
    return "话说贾雨村在扬州城中寄居，日日以诗酒自遣。甄士隐在隔壁花园散步，忽然听到此联。"
