from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import Article, GenerationJob, PublishJob, User, UserVideo

router = APIRouter(prefix="/status", tags=["status"])


@router.get("/summary")
async def summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    a = await db.scalar(select(func.count()).select_from(Article).where(Article.status == "active"))
    v = await db.scalar(select(func.count()).select_from(UserVideo).where(UserVideo.user_id == user.id))
    g_pending = await db.scalar(
        select(func.count()).select_from(GenerationJob).where(GenerationJob.user_id == user.id, GenerationJob.status == "pending")
    )
    g_proc = await db.scalar(
        select(func.count()).select_from(GenerationJob).where(GenerationJob.user_id == user.id, GenerationJob.status == "processing")
    )
    g_done = await db.scalar(
        select(func.count()).select_from(GenerationJob).where(GenerationJob.user_id == user.id, GenerationJob.status == "done")
    )
    g_fail = await db.scalar(
        select(func.count()).select_from(GenerationJob).where(GenerationJob.user_id == user.id, GenerationJob.status == "failed")
    )
    p_ok = await db.scalar(
        select(func.count())
        .select_from(PublishJob)
        .join(GenerationJob, PublishJob.generation_job_id == GenerationJob.id)
        .where(GenerationJob.user_id == user.id, PublishJob.status == "success")
    )
    p_fail = await db.scalar(
        select(func.count())
        .select_from(PublishJob)
        .join(GenerationJob, PublishJob.generation_job_id == GenerationJob.id)
        .where(GenerationJob.user_id == user.id, PublishJob.status == "failed")
    )
    return {
        "articles_active": int(a or 0),
        "my_videos": int(v or 0),
        "generation": {
            "pending": int(g_pending or 0),
            "processing": int(g_proc or 0),
            "done": int(g_done or 0),
            "failed": int(g_fail or 0),
        },
        "publish": {"success": int(p_ok or 0), "failed": int(p_fail or 0)},
    }
