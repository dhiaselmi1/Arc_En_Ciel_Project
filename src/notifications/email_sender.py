"""Send the weekly digest by email via Gmail SMTP."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from src.config import Settings

log = logging.getLogger(__name__)


def send_email(settings: Settings, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.email_from_name} <{settings.smtp_user}>"
    msg["To"] = settings.email_to
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_app_password)
        server.send_message(msg)
    log.info("Email sent to %s", settings.email_to)
