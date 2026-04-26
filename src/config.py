"""Centralized configuration: env vars + association profile."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "config" / "association_profile.json"


@dataclass(frozen=True)
class Settings:
    mistral_api_key: str
    mistral_model: str
    tavily_api_key: str
    db_path: str

    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_app_password: str
    email_from_name: str
    email_to: str

    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    whatsapp_to: str


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def load_settings() -> Settings:
    return Settings(
        mistral_api_key=_required("MISTRAL_API_KEY"),
        mistral_model=_optional("MISTRAL_MODEL", "mistral-small-latest"),
        tavily_api_key=_required("TAVILY_API_KEY"),
        db_path=_optional("DB_PATH", str(ROOT / "data" / "grants.db")),
        smtp_host=_optional("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(_optional("SMTP_PORT", "587")),
        smtp_user=_required("SMTP_USER"),
        smtp_app_password=_required("SMTP_APP_PASSWORD"),
        email_from_name=_optional("EMAIL_FROM_NAME", "Agent Arc En Ciel"),
        email_to=_required("EMAIL_TO"),
        twilio_account_sid=_optional("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=_optional("TWILIO_AUTH_TOKEN"),
        twilio_whatsapp_from=_optional("TWILIO_WHATSAPP_FROM"),
        whatsapp_to=_optional("WHATSAPP_TO"),
    )


def load_profile() -> dict:
    with PROFILE_PATH.open(encoding="utf-8") as f:
        return json.load(f)
