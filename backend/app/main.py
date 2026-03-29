from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import articles, auth, categories, logs, novel, pipeline, publish, settings_api, status, videos, voiceprints
from app.config import get_settings
from sqlalchemy import func, select, text

from app.database import AsyncSessionLocal, Base, engine
from app.models import (  # noqa: F401
    Category, UserSession, LoginHistory,
    NovelProject, NovelCharacter, NovelChapter, ChapterReview, BgmLibrary,
)

DEFAULT_CATEGORIES = [
    {
        "name": "AI科技",
        "slug": "ai",
        "rss_urls": [
            "https://feeds.arstechnica.com/arstechnica/technology-lab",
            "https://www.technologyreview.com/feed/",
        ],
    },
    {
        "name": "国际新闻",
        "slug": "world",
        "rss_urls": [
            "http://feeds.bbci.co.uk/news/world/rss.xml",
        ],
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.novel_assets_dir).mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 已有库表结构增量补丁（create_all 不会自动加列）
        try:
            await conn.execute(
                text("ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS output_description TEXT")
            )
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE generation_jobs ALTER COLUMN article_id DROP NOT NULL"))
        except Exception:
            pass
        for stmt in (
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(50)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS lock_until TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            "ALTER TABLE users ALTER COLUMN email DROP NOT NULL",
            "ALTER TABLE users ALTER COLUMN phone DROP NOT NULL",
            "ALTER TABLE users ALTER COLUMN email_verified DROP NOT NULL",
            "ALTER TABLE users ALTER COLUMN phone_verified DROP NOT NULL",
        ):
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass
        try:
            await conn.execute(
                text(
                    "UPDATE users SET username = 'user_' || CAST(id AS TEXT) "
                    "WHERE username IS NULL OR TRIM(username) = ''"
                )
            )
        except Exception:
            pass

    async with AsyncSessionLocal() as session:
        n = await session.scalar(select(func.count()).select_from(Category))
        if not n:
            for c in DEFAULT_CATEGORIES:
                session.add(
                    Category(
                        name=c["name"],
                        slug=c["slug"],
                        rss_urls=c["rss_urls"],
                        fetch_interval_minutes=30,
                        is_active=True,
                    )
                )
            await session.commit()
    yield
    await engine.dispose()


def _cors_origins() -> list[str]:
    s = get_settings().cors_origins.strip()
    if s == "*":
        return ["*"]
    return [x.strip() for x in s.split(",") if x.strip()]


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

prefix = get_settings().api_v1_prefix
app.include_router(auth.router, prefix=prefix)
app.include_router(categories.router, prefix=prefix)
app.include_router(articles.router, prefix=prefix)
app.include_router(videos.router, prefix=prefix)
app.include_router(pipeline.router, prefix=prefix)
app.include_router(publish.router, prefix=prefix)
app.include_router(status.router, prefix=prefix)
app.include_router(logs.router, prefix=prefix)
app.include_router(settings_api.router, prefix=prefix)
app.include_router(voiceprints.router, prefix=prefix)
app.include_router(novel.router, prefix=prefix)

uploads = Path(get_settings().upload_dir)
outputs = Path(get_settings().output_dir)
uploads.mkdir(parents=True, exist_ok=True)
outputs.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads)), name="uploads")
app.mount("/media", StaticFiles(directory=str(outputs)), name="media")


@app.get("/health")
async def health():
    return {"status": "ok"}


def _resolve_frontend_dist() -> Path | None:
    settings = get_settings()
    if settings.frontend_dist_dir.strip():
        p = Path(settings.frontend_dist_dir).expanduser().resolve()
    else:
        p = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if p.is_dir() and (p / "index.html").is_file():
        return p
    return None


# 必须最后注册：9090 上直接提供 SPA。仅用 StaticFiles(html=True) 挂载 / 时，部分路径（如 /register）
# 在 FastAPI 下会得到 JSON 404，故改为 /assets 静态资源 + 其余路径统一回 index.html。
_frontend = _resolve_frontend_dist()
if _frontend is not None:
    _index_html = _frontend / "index.html"
    _assets_dir = _frontend / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    if _index_html.is_file():

        @app.get("/")
        async def spa_index_root():
            return FileResponse(_index_html)

        @app.get("/{full_path:path}")
        async def spa_index_nested(full_path: str):
            del full_path  # 任意前端路由均返回 index.html
            return FileResponse(_index_html)
