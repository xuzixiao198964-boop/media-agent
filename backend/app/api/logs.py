from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import FlowLog, User

router = APIRouter(prefix="/logs", tags=["logs"])


class FlowLogOut(BaseModel):
    id: int
    ref_type: str
    ref_id: int | None
    step: str
    message: str
    level: str
    created_at: object

    class Config:
        from_attributes = True


@router.get("/flow", response_model=list[FlowLogOut])
async def list_flow_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    limit: int = 200,
):
    q = select(FlowLog).order_by(FlowLog.id.desc()).limit(min(limit, 500))
    rows = (await db.execute(q)).scalars().all()
    return rows
