"""Shared LLM builder + throttling helper.

Mistral free tier allows 1 RPS (60 RPM). We pace at 12 RPM (5 sec between
calls) to stay well within limits and leave headroom for retries.
"""
from __future__ import annotations

import time

from langchain_mistralai import ChatMistralAI

from src.config import Settings

CALL_DELAY_SECONDS = 5.0
_last_call_at: float = 0.0


def build_llm(settings: Settings) -> ChatMistralAI:
    return ChatMistralAI(
        model=settings.mistral_model,
        api_key=settings.mistral_api_key,
        temperature=0.1,
    )


def throttle() -> None:
    """Block until enough time has passed since the previous LLM call."""
    global _last_call_at
    now = time.monotonic()
    wait = CALL_DELAY_SECONDS - (now - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.monotonic()
