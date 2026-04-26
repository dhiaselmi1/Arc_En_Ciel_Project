"""Send the weekly digest by WhatsApp via Twilio sandbox."""
from __future__ import annotations

import logging

from twilio.rest import Client

from src.config import Settings

log = logging.getLogger(__name__)

# WhatsApp messages have a 1600 char limit. We chunk if needed.
MAX_LEN = 1500


def _chunk(text: str, max_len: int = MAX_LEN) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            parts.append(remaining)
            break
        cut = remaining.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        parts.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    return parts


def send_whatsapp(settings: Settings, body: str) -> None:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        log.warning("Twilio credentials missing — skipping WhatsApp send")
        return
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
    for i, chunk in enumerate(_chunk(body), start=1):
        client.messages.create(
            from_=settings.twilio_whatsapp_from,
            to=settings.whatsapp_to,
            body=chunk,
        )
        log.info("WhatsApp chunk %d sent to %s", i, settings.whatsapp_to)
