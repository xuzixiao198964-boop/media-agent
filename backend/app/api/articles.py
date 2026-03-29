from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article

router = APIRouter(prefix="/articles", tags=["articles"])


class ArticleOut(BaseModel):
    id: int
    category_id: int
    title: str
    summary: Optional[str]
    image_url: Optional[str]
    source_url: str
    status: str
    created_at: object
    hot_score: float

    class Config:
        from_attributes = True


@router.get("", response_model=list[ArticleOut])
async def list_articles(
    db: Annotated[AsyncSession, Depends(get_db)],
    category_id: Optional[int] = None,
    status: str = Query("active"),
    sort: str = Query("hot"),
    limit: int = Query(50, ge=1, le=200),
):
    q = select(Article).where(Article.status == status)
    if category_id is not None:
        q = q.where(Article.category_id == category_id)
    q = q.order_by(Article.id.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    now = datetime.now(timezone.utc)

    def score(a: Article) -> float:
        created = a.created_at.replace(tzinfo=timezone.utc)
        hours = max((now - created).total_seconds() / 3600.0, 0.0)
        txt = f"{a.title or ''} {a.summary or ''}".lower()
        bonus = 0.0
        if any(k in txt for k in ("ai", "人工智能", "大模型", "模型", "openai", "deepseek", "gemini")):
            bonus += 15.0
        if a.image_url:
            bonus += 5.0
        freshness = max(0.0, 100.0 - min(hours, 100.0))
        return round(freshness + bonus, 2)

    payload = [
        ArticleOut(
            id=r.id,
            category_id=r.category_id,
            title=r.title,
            summary=r.summary,
            image_url=r.image_url,
            source_url=r.source_url,
            status=r.status,
            created_at=r.created_at,
            hot_score=score(r),
        )
        for r in rows
    ]
    if sort == "hot":
        payload.sort(key=lambda x: x.hot_score, reverse=True)
    return payload
