from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import GenerationJob, PublishJob, User
from app.tasks import run_publish_job_task

router = APIRouter(prefix="/publish", tags=["publish"])


class PublishCreate(BaseModel):
    generation_job_id: int
    platform: str = Field(min_length=2, max_length=64, description="如 douyin / tiktok / mock")


class PublishOut(BaseModel):
    id: int
    generation_job_id: int
    platform: str
    status: str
    error: Optional[str]
    meta: Optional[dict]

    class Config:
        from_attributes = True


@router.post("/jobs", response_model=PublishOut)
async def create_publish_job(
    data: PublishCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    gj = await db.get(GenerationJob, data.generation_job_id)
    if not gj or gj.user_id != user.id:
        raise HTTPException(status_code=404, detail="生成任务不存在")
    if gj.status != "done" or not gj.output_path:
        raise HTTPException(status_code=400, detail="生成未完成，无法发布")
    pj = PublishJob(generation_job_id=gj.id, platform=data.platform, status="queued")
    db.add(pj)
    await db.flush()
    # 关键：显式提交，避免 celery worker 在事务未可见时读取不到记录
    await db.commit()
    run_publish_job_task.delay(pj.id)
    return pj


@router.get("/jobs", response_model=list[PublishOut])
async def list_publish_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
):
    q = (
        select(PublishJob)
        .join(GenerationJob, PublishJob.generation_job_id == GenerationJob.id)
        .where(GenerationJob.user_id == user.id)
        .order_by(PublishJob.id.desc())
        .limit(min(limit, 200))
    )
    rows = (await db.execute(q)).scalars().all()
    return rows
