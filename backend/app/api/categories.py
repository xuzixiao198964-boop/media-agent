from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import Category, User
from app.tasks import fetch_category_task

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    rss_urls: list
    fetch_interval_minutes: int
    is_active: bool

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9\-]+$")
    rss_urls: List[str] = []
    fetch_interval_minutes: int = 30


class CategoryPatch(BaseModel):
    name: Optional[str] = None
    rss_urls: Optional[List[str]] = None
    fetch_interval_minutes: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("", response_model=list[CategoryOut])
async def list_categories(db: Annotated[AsyncSession, Depends(get_db)]):
    rows = (await db.execute(select(Category).order_by(Category.id))).scalars().all()
    return rows


@router.post("", response_model=CategoryOut)
async def create_category(
    data: CategoryCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    exists = await db.execute(select(Category.id).where(Category.slug == data.slug))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="slug 已存在")
    c = Category(
        name=data.name,
        slug=data.slug,
        rss_urls=data.rss_urls,
        fetch_interval_minutes=data.fetch_interval_minutes,
    )
    db.add(c)
    await db.flush()
    return c


@router.patch("/{category_id}", response_model=CategoryOut)
async def patch_category(
    category_id: int,
    data: CategoryPatch,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    c = await db.get(Category, category_id)
    if not c:
        raise HTTPException(status_code=404, detail="栏目不存在")
    if data.name is not None:
        c.name = data.name
    if data.rss_urls is not None:
        c.rss_urls = data.rss_urls
    if data.fetch_interval_minutes is not None:
        c.fetch_interval_minutes = data.fetch_interval_minutes
    if data.is_active is not None:
        c.is_active = data.is_active
    await db.flush()
    return c


@router.post("/{category_id}/fetch")
async def trigger_fetch(
    category_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    c = await db.get(Category, category_id)
    if not c:
        raise HTTPException(status_code=404, detail="栏目不存在")
    fetch_category_task.delay(category_id)
    return {"queued": True, "category_id": category_id}
