"""邮件/短信文案：统一带项目名称。"""
from __future__ import annotations

from app.config import get_settings


def _name() -> str:
    return (get_settings().app_name or "Media Agent").strip()


def _email_footer() -> str:
    """邮件末尾统一品牌与致谢（纯文本）。"""
    n = _name()
    return (
        f"\n---\n"
        f"本邮件由 {n}（MediaAgent 媒体自动化项目）系统自动发送。\n"
        f"感谢您使用本服务。如有疑问，请勿回复本邮件，请通过站内渠道联系管理员。\n"
        f"祝您使用愉快。\n"
    )


def sms_register(phone_code: str) -> str:
    n = _name()
    return f"【{n}】注册验证码：{phone_code}，10分钟内有效，请勿告知他人。如非本人操作请忽略。"


def email_register_subject() -> str:
    return f"【{_name()}】注册验证码"


def email_register_body(email_code: str) -> str:
    n = _name()
    return (
        f"【{n}】\n\n"
        f"您正在使用 {n}（MediaAgent 项目）进行账号注册。\n"
        f"邮箱验证码：{email_code}\n"
        f"有效时间：10 分钟。\n\n"
        f"请勿向他人泄露验证码。如非本人操作，请忽略本邮件。\n"
        f"{_email_footer()}"
    )


def sms_login(phone_code: str) -> str:
    n = _name()
    return f"【{n}】登录验证码：{phone_code}，10分钟内有效，请勿告知他人。"


def email_login_subject() -> str:
    return f"【{_name()}】登录验证码"


def email_login_body(code: str) -> str:
    n = _name()
    return (
        f"【{n}】\n\n"
        f"您正在使用 {n}（MediaAgent 项目）登录账号。\n"
        f"邮箱验证码：{code}\n"
        f"有效时间：10 分钟。\n\n"
        f"如非本人操作，请忽略本邮件。\n"
        f"{_email_footer()}"
    )


def sms_reset(phone_code: str) -> str:
    n = _name()
    return f"【{n}】重置密码验证码：{phone_code}，10分钟内有效，请勿告知他人。"


def email_reset_subject() -> str:
    return f"【{_name()}】重置密码验证码"


def email_reset_body(email_code: str) -> str:
    n = _name()
    return (
        f"【{n}】\n\n"
        f"您正在使用 {n}（MediaAgent 项目）重置登录密码。\n"
        f"邮箱验证码：{email_code}\n"
        f"有效时间：10 分钟。\n\n"
        f"如非本人操作，请立即修改密码并联系管理员。\n"
        f"{_email_footer()}"
    )
