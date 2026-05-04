"""Send the weekly digest by WhatsApp via CallMeBot.

CallMeBot is a free unofficial WhatsApp gateway that requires a one-time
activation by the recipient (send "I allow callmebot to send me messages"
to +34 644 51 95 23). Once activated, the recipient gets an API key.

API: GET https://api.callmebot.com/whatsapp.php
Params:
  - phone   : international number, digits only (e.g., 21693105718)
  - text    : URL-encoded message body
  - apikey  : key returned by CallMeBot after activation
"""
from __future__ import annotations

import logging
import time
import urllib.parse

import requests

from src.config import Settings

log = logging.getLogger(__name__)

CALLMEBOT_URL = "https://api.callmebot.com/whatsapp.php"
MAX_LEN = 1500            # WhatsApp soft limit per message; chunk if longer
CHUNK_DELAY_SECONDS = 8   # CallMeBot rate-limits aggressive senders


def _normalize_phone(phone: str) -> str:
    """CallMeBot wants digits only (no '+', no 'whatsapp:')."""
    if phone.startswith("whatsapp:"):
        phone = phone[len("whatsapp:"):]
    return phone.lstrip("+").replace(" ", "")


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
    if not settings.callmebot_api_key or not settings.whatsapp_to_phone:
        log.warning("CallMeBot credentials missing — skipping WhatsApp send")
        return

    phone = _normalize_phone(settings.whatsapp_to_phone)
    chunks = _chunk(body)
    for i, chunk in enumerate(chunks, start=1):
        params = {
            "phone": phone,
            "text": chunk,
            "apikey": settings.callmebot_api_key,
        }
        url = f"{CALLMEBOT_URL}?{urllib.parse.urlencode(params)}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            log.info("WhatsApp chunk %d/%d sent to %s", i, len(chunks), phone)
        except requests.RequestException as exc:
            log.error("CallMeBot send failed (chunk %d/%d): %s", i, len(chunks), exc)
            raise
        # Throttle between chunks to stay under CallMeBot rate limit
        if i < len(chunks):
            time.sleep(CHUNK_DELAY_SECONDS)
