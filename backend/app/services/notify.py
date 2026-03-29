"""邮件 / 短信发送（未配置 SMTP 时仅记录日志，便于开发）。"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from app.config import get_settings
from app.db_sync import SessionLocal
from app.services.flow_log import log_sync

log = logging.getLogger("media_agent.notify")


def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        log.warning("SMTP 未配置，邮件仅记录日志: to=%s subject=%s", to, subject)
        db = SessionLocal()
        try:
            log_sync(db, "api", None, "email_stub", f"to={to}\n{body}", "info")
            db.commit()
        finally:
            db.close()
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(settings.smtp_from, [to], msg.as_string())


def send_sms(phone: str, body: str) -> None:
    settings = get_settings()
    if not settings.sms_provider:
        log.warning("SMS 未配置，短信仅记录日志: phone=%s", phone)
        db = SessionLocal()
        try:
            log_sync(db, "api", None, "sms_stub", f"phone={phone}\n{body}", "info")
            db.commit()
        finally:
            db.close()
        return
    log.warning("sms_provider=%s 尚未对接具体网关，请自行接入阿里云/腾讯云短信", settings.sms_provider)
