"""注册/重置密码强度校验。"""
from __future__ import annotations

import re

_SPECIAL = set("!@#$%^&*()_+-=[]{}|;:,.<>?/~`")


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 10:
        return False, "密码至少 10 位"
    if len(password) > 128:
        return False, "密码过长"
    if not re.search(r"[A-Z]", password):
        return False, "需包含至少一个大写字母"
    if not re.search(r"[a-z]", password):
        return False, "需包含至少一个小写字母"
    if not re.search(r"\d", password):
        return False, "需包含至少一个数字"
    if not any(c in _SPECIAL for c in password):
        return False, "需包含至少一个特殊符号（如 !@#$%^&* 等）"
    low = password.lower()
    if low in {"password123!", "qwerty123!"}:
        return False, "密码过于简单，请更换"
    return True, ""
