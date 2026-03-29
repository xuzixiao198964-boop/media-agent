import hashlib
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional


def _utcnow() -> datetime:
    """返回无时区的 UTC 当前时间（与 PostgreSQL TIMESTAMP WITHOUT TIME ZONE 兼容）。"""
    return datetime.utcnow()

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import get_current_user, get_current_user_and_token
from app.core.password_policy import validate_password_strength
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
    decode_token,
)
from app.database import get_db
from app.models import LoginHistory, User, UserSession
from app.schemas.auth import (
    CaptchaOut,
    ChangePasswordIn,
    LoginHistoryOut,
    LoginPasswordIn,
    PasswordResetIn,
    RefreshTokenIn,
    RegisterCompleteIn,
    SendCodesOut,
    SendCodesRegisterIn,
    SessionOut,
    TokenOut,
    UserOut,
)
from app.services.image_captcha import create_image_captcha, verify_image_captcha
from app.services.login_failures import (
    clear_login_failures,
    needs_captcha,
    record_login_failure,
)

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_LOGIN_HISTORY = 100


def _gravatar_url(username: str) -> str:
    username_hash = hashlib.md5(username.encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/avatar/{username_hash}?d=identicon&s=96"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _record_login(
    db: AsyncSession,
    username: str,
    success: bool,
    user_id: Optional[int],
    ip: str,
    reason: Optional[str] = None,
) -> None:
    db.add(LoginHistory(
        user_id=user_id,
        username=username,
        ip_address=ip,
        success=success,
        reason=reason,
    ))


async def _create_session(
    db: AsyncSession,
    user: User,
    request: Request,
) -> tuple[str, str]:
    """创建 access + refresh token 并管理会话数（最多 N 个，踢最早）。"""
    settings = get_settings()
    refresh_raw = create_refresh_token()
    refresh_hash = hash_refresh_token(refresh_raw)
    expires_at = _utcnow() + timedelta(days=settings.refresh_token_expire_days)

    session = UserSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:512],
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    count_q = await db.scalar(
        select(func.count()).select_from(UserSession).where(UserSession.user_id == user.id)
    )
    if count_q and count_q > settings.max_sessions_per_user:
        oldest = await db.execute(
            select(UserSession.id)
            .where(UserSession.user_id == user.id)
            .order_by(UserSession.created_at.asc())
            .limit(count_q - settings.max_sessions_per_user)
        )
        old_ids = [r[0] for r in oldest.all()]
        if old_ids:
            await db.execute(delete(UserSession).where(UserSession.id.in_(old_ids)))

    access = create_access_token(user.id)
    return access, refresh_raw


# ── GET /auth/me ──
@router.get("/me", response_model=UserOut)
async def current_user_profile(user: Annotated[User, Depends(get_current_user)]):
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url or _gravatar_url(user.username),
        bio=user.bio,
    )


# ── PUT /auth/profile ──
@router.put("/profile", response_model=UserOut)
async def update_profile(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    display_name: Optional[str] = None,
    bio: Optional[str] = None,
):
    if display_name is not None:
        user.display_name = display_name[:50]
    if bio is not None:
        user.bio = bio[:500]
    await db.flush()
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url or _gravatar_url(user.username),
        bio=user.bio,
    )


# ── GET /auth/captcha ──
@router.get("/captcha", response_model=CaptchaOut)
async def get_captcha():
    c = await create_image_captcha()
    return CaptchaOut(captcha_id=c.captcha_id, image_base64=c.image_base64)


# ── POST /auth/register/send-codes ──
@router.post("/register/send-codes", response_model=SendCodesOut)
async def register_send_codes(data: SendCodesRegisterIn, db: Annotated[AsyncSession, Depends(get_db)]):
    if await db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(status_code=400, detail="用户名已存在")
    return SendCodesOut(dev_codes=None, message="用户名可用")


# ── POST /auth/register ──
@router.post("/register", response_model=TokenOut)
async def register_complete(
    data: RegisterCompleteIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    ok_pw, msg_pw = validate_password_strength(data.password)
    if not ok_pw:
        raise HTTPException(status_code=400, detail=msg_pw)
    if await db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        password_changed_at=_utcnow(),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access, refresh = await _create_session(db, user, request)
    settings = get_settings()
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── POST /auth/login/password ──
@router.post("/login/password")
async def login_password(
    data: LoginPasswordIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    login = data.login.strip()
    ip = _client_ip(request)

    require_captcha = await needs_captcha(login)
    if require_captcha:
        if not data.captcha_id or not data.captcha_answer:
            return JSONResponse(
                status_code=400,
                content={"detail": "连续登录失败，请完成图形验证码", "requires_captcha": True},
            )
        captcha_ok = await verify_image_captcha(data.captcha_id, data.captcha_answer)
        if not captcha_ok:
            return JSONResponse(
                status_code=400,
                content={"detail": "验证码错误", "requires_captcha": True},
            )

    q = await db.execute(select(User).where(User.username == login))
    user = q.scalar_one_or_none()

    if not user:
        await record_login_failure(login)
        await _record_login(db, login, False, None, ip, "用户不存在")
        return JSONResponse(status_code=401, content={"detail": "账号或密码错误"})

    now = _utcnow()
    if user.lock_until and user.lock_until > now:
        remaining = int((user.lock_until - now).total_seconds())
        await _record_login(db, login, False, user.id, ip, "账号锁定中")
        return JSONResponse(
            status_code=403,
            content={"detail": f"账号已锁定，请 {remaining} 秒后再试"},
        )

    if not verify_password(data.password, user.hashed_password):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        await record_login_failure(login)
        if user.failed_login_attempts >= 5:
            user.lock_until = now + timedelta(minutes=30)
            await _record_login(db, login, False, user.id, ip, "密码错误次数过多，账号锁定30分钟")
        else:
            await _record_login(db, login, False, user.id, ip, "密码错误")
        await db.flush()
        new_needs_captcha = await needs_captcha(login)
        resp: dict = {"detail": "账号或密码错误"}
        if new_needs_captcha:
            resp["requires_captcha"] = True
        return JSONResponse(status_code=401, content=resp)

    if not user.is_active:
        await _record_login(db, login, False, user.id, ip, "账号已禁用")
        raise HTTPException(status_code=400, detail="账号已禁用")

    user.failed_login_attempts = 0
    user.lock_until = None
    user.last_login_at = now
    await clear_login_failures(login)
    await _record_login(db, login, True, user.id, ip)

    access, refresh = await _create_session(db, user, request)
    settings = get_settings()
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── POST /auth/refresh ──
@router.post("/refresh", response_model=TokenOut)
async def refresh_token(
    data: RefreshTokenIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    rh = hash_refresh_token(data.refresh_token)
    q = await db.execute(select(UserSession).where(UserSession.refresh_token_hash == rh))
    session = q.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=401, detail="刷新令牌无效")

    now = _utcnow()
    if session.expires_at < now:
        await db.delete(session)
        await db.flush()
        raise HTTPException(status_code=401, detail="刷新令牌已过期")

    user = await db.get(User, session.user_id)
    if not user or not user.is_active:
        await db.delete(session)
        await db.flush()
        raise HTTPException(status_code=401, detail="用户不可用")

    await db.delete(session)
    await db.flush()

    access, new_refresh = await _create_session(db, user, request)
    settings = get_settings()
    return TokenOut(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── POST /auth/logout ──
@router.post("/logout")
async def logout(
    user_and_token: Annotated[tuple[User, str], Depends(get_current_user_and_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _, token = user_and_token
    sub = decode_token(token) if token else None
    if sub:
        user_id = int(sub)
        await db.execute(
            delete(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.expires_at < _utcnow(),
            )
        )
    return {"ok": True}


# ── POST /auth/password ──
@router.post("/password")
async def change_password(
    data: ChangePasswordIn,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(data.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码错误")
    ok_pw, msg_pw = validate_password_strength(data.new_password)
    if not ok_pw:
        raise HTTPException(status_code=400, detail=msg_pw)
    if verify_password(data.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
    user.hashed_password = hash_password(data.new_password)
    user.password_changed_at = _utcnow()
    await db.flush()
    return {"ok": True, "message": "密码修改成功"}


# ── POST /auth/password-reset ──
@router.post("/password-reset", response_model=TokenOut)
async def password_reset(
    data: PasswordResetIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    request: Request,
):
    q = await db.execute(select(User).where(User.username == data.username))
    user = q.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户名不存在")

    ok_pw, msg_pw = validate_password_strength(data.new_password)
    if not ok_pw:
        raise HTTPException(status_code=400, detail=msg_pw)
    if verify_password(data.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    user.hashed_password = hash_password(data.new_password)
    user.password_changed_at = _utcnow()
    user.failed_login_attempts = 0
    user.lock_until = None

    access, refresh = await _create_session(db, user, request)
    settings = get_settings()
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ── GET /auth/sessions ──
@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    q = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user.id)
        .order_by(UserSession.created_at.desc())
    )
    sessions = q.scalars().all()
    return [
        SessionOut(
            id=s.id,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            created_at=s.created_at.isoformat(),
        )
        for s in sessions
    ]


# ── DELETE /auth/sessions/{session_id} ──
@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    q = await db.execute(
        select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user.id)
    )
    session = q.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.delete(session)
    await db.flush()
    return {"ok": True}


# ── GET /auth/history ──
@router.get("/history", response_model=list[LoginHistoryOut])
async def login_history(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
):
    q = await db.execute(
        select(LoginHistory)
        .where(LoginHistory.user_id == user.id)
        .order_by(LoginHistory.created_at.desc())
        .limit(min(limit, MAX_LOGIN_HISTORY))
    )
    rows = q.scalars().all()
    return [
        LoginHistoryOut(
            id=r.id,
            username=r.username,
            ip_address=r.ip_address,
            success=r.success,
            reason=r.reason,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
