"""验证码生成与校验。"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import VerificationCode


def _hash_code(plain: str) -> str:
    s = get_settings().secret_key.encode("utf-8")
    return hashlib.sha256(s + plain.encode("utf-8")).hexdigest()


def generate_six_digit() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


async def issue_code(
    db: AsyncSession,
    *,
    target: str,
    channel: str,
    purpose: str,
    ttl_minutes: int = 10,
) -> str:
    """生成并保存验证码，返回明文（仅用于发送）。"""
    plain = generate_six_digit()
    expires = datetime.utcnow() + timedelta(minutes=ttl_minutes)
    # 同目标同用途的旧未用码作废
    await db.execute(
        delete(VerificationCode).where(
            VerificationCode.target == target,
            VerificationCode.channel == channel,
            VerificationCode.purpose == purpose,
            VerificationCode.used.is_(False),
        )
    )
    row = VerificationCode(
        target=target,
        channel=channel,
        purpose=purpose,
        code_hash=_hash_code(plain),
        expires_at=expires,
        used=False,
    )
    db.add(row)
    await db.flush()
    return plain


async def verify_code(
    db: AsyncSession,
    *,
    target: str,
    channel: str,
    purpose: str,
    plain: str,
) -> bool:
    """校验成功后标记已使用。"""
    q = (
        select(VerificationCode)
        .where(
            VerificationCode.target == target,
            VerificationCode.channel == channel,
            VerificationCode.purpose == purpose,
            VerificationCode.used.is_(False),
        )
        .order_by(VerificationCode.id.desc())
        .limit(1)
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if not row:
        return False
    if row.expires_at < datetime.utcnow():
        return False
    if row.code_hash != _hash_code(plain.strip()):
        return False
    row.used = True
    await db.flush()
    return True


def normalize_phone(phone: str) -> str:
    p = "".join(c for c in (phone or "").strip() if c.isdigit())
    if len(p) != 11 or not p.startswith("1"):
        raise ValueError("手机号需为 11 位中国大陆号码")
    return p


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


async def verify_register_pair(
    db: AsyncSession,
    *,
    email: str,
    phone: str,
    email_plain: str,
    phone_plain: str,
) -> bool:
    """同时校验注册用的邮箱+手机验证码，全部正确后一次性标记已用。"""
    qe = (
        select(VerificationCode)
        .where(
            VerificationCode.target == email,
            VerificationCode.channel == "email",
            VerificationCode.purpose == "register",
            VerificationCode.used.is_(False),
        )
        .order_by(VerificationCode.id.desc())
        .limit(1)
    )
    qp = (
        select(VerificationCode)
        .where(
            VerificationCode.target == phone,
            VerificationCode.channel == "phone",
            VerificationCode.purpose == "register",
            VerificationCode.used.is_(False),
        )
        .order_by(VerificationCode.id.desc())
        .limit(1)
    )
    re = (await db.execute(qe)).scalar_one_or_none()
    rp = (await db.execute(qp)).scalar_one_or_none()
    if not re or not rp:
        return False
    now = datetime.utcnow()
    if re.expires_at < now or rp.expires_at < now:
        return False
    if re.code_hash != _hash_code(email_plain.strip()) or rp.code_hash != _hash_code(phone_plain.strip()):
        return False
    re.used = True
    rp.used = True
    await db.flush()
    return True


async def verify_reset_pair(
    db: AsyncSession,
    *,
    email: str,
    phone: str,
    email_plain: str,
    phone_plain: str,
) -> bool:
    """找回密码：同时校验邮箱+手机验证码。"""
    qe = (
        select(VerificationCode)
        .where(
            VerificationCode.target == email,
            VerificationCode.channel == "email",
            VerificationCode.purpose == "reset_password",
            VerificationCode.used.is_(False),
        )
        .order_by(VerificationCode.id.desc())
        .limit(1)
    )
    qp = (
        select(VerificationCode)
        .where(
            VerificationCode.target == phone,
            VerificationCode.channel == "phone",
            VerificationCode.purpose == "reset_password",
            VerificationCode.used.is_(False),
        )
        .order_by(VerificationCode.id.desc())
        .limit(1)
    )
    re = (await db.execute(qe)).scalar_one_or_none()
    rp = (await db.execute(qp)).scalar_one_or_none()
    if not re or not rp:
        return False
    now = datetime.utcnow()
    if re.expires_at < now or rp.expires_at < now:
        return False
    if re.code_hash != _hash_code(email_plain.strip()) or rp.code_hash != _hash_code(phone_plain.strip()):
        return False
    re.used = True
    rp.used = True
    await db.flush()
    return True
