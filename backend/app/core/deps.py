from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.config import get_settings
from app.database import get_db
from app.models import User, UserVideo

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    settings = get_settings()
    if (cred is None or not cred.credentials) and settings.single_user_mode:
        latest_video_user = await db.execute(select(UserVideo.user_id).order_by(UserVideo.id.desc()).limit(1))
        uid = latest_video_user.scalar_one_or_none()
        user = None
        if uid is not None:
            q = await db.execute(select(User).where(User.id == uid, User.is_active.is_(True)))
            user = q.scalar_one_or_none()
        if user is None:
            fallback = await db.execute(select(User).where(User.is_active.is_(True)).order_by(User.id.asc()).limit(1))
            user = fallback.scalar_one_or_none()
        if user:
            return user

    if cred is None or not cred.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    sub = decode_token(cred.credentials)
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期")
    result = await db.execute(select(User).where(User.id == int(sub)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不可用")
    return user


async def get_current_user_and_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> tuple[User, str]:
    """返回 (user, raw_token)，用于 logout 等需要知道原始 token 的场景。"""
    user = await get_current_user(db, cred)
    token = cred.credentials if cred else ""
    return user, token
