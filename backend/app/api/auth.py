import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.deps import get_current_user
from app.core.password_policy import validate_password_strength
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas.auth import (
    CaptchaOut,
    LoginCodeIn,
    LoginPasswordIn,
    PasswordResetIn,
    RegisterCompleteIn,
    SendCodesOut,
    SendCodesRegisterIn,
    SendLoginCodeIn,
    SendResetCodesIn,
    TokenOut,
    UserOut,
)
from app.services.auth_messages import (
    email_login_body,
    email_login_subject,
    email_register_body,
    email_register_subject,
    email_reset_body,
    email_reset_subject,
    sms_login,
    sms_register,
    sms_reset,
)
from app.services.image_captcha import create_image_captcha, verify_image_captcha
from app.services.notify import send_email, send_sms
from app.services.login_failures import (
    clear_login_failures,
    needs_captcha,
    record_login_failure,
)
from app.services.verification import (
    issue_code,
    normalize_email,
    normalize_phone,
    verify_code,
    verify_register_pair,
    verify_reset_pair,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _gravatar_url(username: str) -> str:
    """基于用户名生成头像URL"""
    username_hash = hashlib.md5(username.encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/avatar/{username_hash}?d=identicon&s=96"


@router.get("/me", response_model=UserOut)
async def current_user_profile(user: Annotated[User, Depends(get_current_user)]):
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        avatar_url=user.avatar_url or _gravatar_url(user.username),
        bio=user.bio,
    )


@router.get("/captcha", response_model=CaptchaOut)
async def get_captcha():
    c = await create_image_captcha()
    return CaptchaOut(captcha_id=c.captcha_id, image_base64=c.image_base64)


@router.post("/register/send-codes", response_model=SendCodesOut)
async def register_send_codes(data: SendCodesRegisterIn, db: Annotated[AsyncSession, Depends(get_db)]):
    settings = get_settings()
    if await db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 简化版本：不再需要发送验证码，直接返回成功
    return SendCodesOut(
        dev_codes=None,
        message="用户名可用",
    )


@router.post("/register", response_model=TokenOut)
async def register_complete(data: RegisterCompleteIn, db: Annotated[AsyncSession, Depends(get_db)]):
    ok_pw, msg_pw = validate_password_strength(data.password)
    if not ok_pw:
        raise HTTPException(status_code=400, detail=msg_pw)
    if await db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建用户（简化版本，不需要邮箱和手机）
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login/password")
async def login_password(data: LoginPasswordIn, db: Annotated[AsyncSession, Depends(get_db)]):
    login = data.login.strip()
    # 仅支持用户名登录
    q = await db.execute(select(User).where(User.username == login))
    user = q.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        return JSONResponse(
            status_code=401,
            content={"detail": "账号或密码错误"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="账号已禁用")
    return TokenOut(access_token=create_access_token(user.id))


# @router.post("/login/send-code", response_model=SendCodesOut)
# async def login_send_code(data: SendLoginCodeIn, db: Annotated[AsyncSession, Depends(get_db)]):
#     settings = get_settings()
#     if data.channel == "email":
#         em = normalize_email(data.target)
#         q = await db.execute(select(User).where(User.email == em))
#         user = q.scalar_one_or_none()
#         if not user:
#             raise HTTPException(status_code=404, detail="该邮箱未注册")
#         code = await issue_code(db, target=em, channel="email", purpose="login_email")
#         await db.commit()
#         send_email(em, email_login_subject(), email_login_body(code))
#         return SendCodesOut(dev_codes={"email": code} if settings.auth_dev_expose_codes else None)
#     ph = normalize_phone(data.target)
#     q = await db.execute(select(User).where(User.phone == ph))
#     user = q.scalar_one_or_none()
#     if not user:
#         raise HTTPException(status_code=404, detail="该手机号未注册")
#     code = await issue_code(db, target=ph, channel="phone", purpose="login_phone")
#     await db.commit()
#     send_sms(ph, sms_login(code))
#     return SendCodesOut(dev_codes={"phone": code} if settings.auth_dev_expose_codes else None)


# @router.post("/login/code", response_model=TokenOut)
# async def login_with_code(data: LoginCodeIn, db: Annotated[AsyncSession, Depends(get_db)]):
#     if data.channel == "email":
#         em = normalize_email(data.target)
#         purpose = "login_email"
#         ok = await verify_code(db, target=em, channel="email", purpose=purpose, plain=data.code)
#         if not ok:
#             raise HTTPException(status_code=400, detail="验证码错误或已过期")
#         q = await db.execute(select(User).where(User.email == em))
#     else:
#         ph = normalize_phone(data.target)
#         ok = await verify_code(db, target=ph, channel="phone", purpose="login_phone", plain=data.code)
#         if not ok:
#             raise HTTPException(status_code=400, detail="验证码错误或已过期")
#         q = await db.execute(select(User).where(User.phone == ph))
#     await db.commit()
#     user = q.scalar_one_or_none()
#     if not user or not user.is_active:
#         raise HTTPException(status_code=400, detail="用户不可用")
#     return TokenOut(access_token=create_access_token(user.id))


# @router.post("/password-reset/send-codes", response_model=SendCodesOut)
# async def password_reset_send_codes(data: SendResetCodesIn, db: Annotated[AsyncSession, Depends(get_db)]):
#     settings = get_settings()
#     em = normalize_email(str(data.email))
#     ph = normalize_phone(data.phone)
#     q = await db.execute(select(User).where(User.email == em, User.phone == ph))
#     user = q.scalar_one_or_none()
#     if not user:
#         raise HTTPException(status_code=404, detail="邮箱与手机号不匹配或账号不存在")
# 
#     ec = await issue_code(db, target=em, channel="email", purpose="reset_password")
#     pc = await issue_code(db, target=ph, channel="phone", purpose="reset_password")
#     await db.commit()
#     send_email(em, email_reset_subject(), email_reset_body(ec))
#     send_sms(ph, sms_reset(pc))
#     return SendCodesOut(dev_codes={"email": ec, "phone": pc} if settings.auth_dev_expose_codes else None)
# 
# 
# @router.post("/password-reset", response_model=TokenOut)
# async def password_reset(data: PasswordResetIn, db: Annotated[AsyncSession, Depends(get_db)]):
#     em = normalize_email(str(data.email))
#     ph = normalize_phone(data.phone)
#     q = await db.execute(select(User).where(User.email == em, User.phone == ph))
#     user = q.scalar_one_or_none()
#     if not user:
#         raise HTTPException(status_code=404, detail="邮箱与手机号不匹配或账号不存在")
# 
#     ok_pw, msg_pw = validate_password_strength(data.new_password)
#     if not ok_pw:
#         raise HTTPException(status_code=400, detail=msg_pw)
#     if verify_password(data.new_password, user.hashed_password):
#         raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
# 
#     ok = await verify_reset_pair(
#         db,
#         email=em,
#         phone=ph,
#         email_plain=data.email_code,
#         phone_plain=data.phone_code,
#     )
#     if not ok:
#         raise HTTPException(status_code=400, detail="验证码错误或已过期")
# 
#     user.hashed_password = hash_password(data.new_password)
#     await db.commit()
#     return TokenOut(access_token=create_access_token(user.id))
