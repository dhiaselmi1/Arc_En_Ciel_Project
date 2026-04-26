"""User Story 4 — Build the weekly digest from top-ranked grants and dispatch."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Template

from src.agent.ranker import mark_notified, top_n
from src.config import Settings
from src.notifications.email_sender import send_email
from src.notifications.whatsapp_sender import send_whatsapp

log = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "weekly_email.txt"
MEDALS = ["🥇", "🥈", "🥉", "🏅", "🏅"]


def _last_monday() -> str:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%d/%m/%Y")


def _enrich(grants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for i, g in enumerate(grants):
        g["medal"] = MEDALS[i] if i < len(MEDALS) else "•"
        enriched.append(g)
    return enriched


def _build_email(grants: list[dict[str, Any]]) -> tuple[str, str]:
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    rendered = template.render(monday_date=_last_monday(), grants=_enrich(grants))
    # First line is "Objet : ...", the rest is body
    lines = rendered.split("\n", 1)
    subject = lines[0].replace("Objet :", "").strip() if lines[0].startswith("Objet") else f"Arc En Ciel — Subventions de la semaine du {_last_monday()}"
    body = lines[1].lstrip("\n") if len(lines) > 1 else rendered
    return subject, body


def _build_whatsapp(grants: list[dict[str, Any]]) -> str:
    """A more compact version for WhatsApp."""
    if not grants:
        return f"Arc En Ciel 🌈\nAucune nouvelle opportunité cette semaine ({_last_monday()})."
    lines = [f"*Arc En Ciel — Subventions de la semaine du {_last_monday()}* 🌈", ""]
    for i, g in enumerate(_enrich(grants)):
        lines.append(f"{g['medal']} *{g.get('title', '?')}*")
        if g.get("organization"):
            lines.append(f"Organisme : {g['organization']}")
        if g.get("amount"):
            lines.append(f"Montant : {g['amount']}")
        if g.get("deadline"):
            lines.append(f"Deadline : {g['deadline']}")
        if g.get("score_reason"):
            lines.append(f"_{g['score_reason']}_")
        lines.append(g.get("source_url", ""))
        lines.append("")
    lines.append("Bonne chance pour vos candidatures !")
    return "\n".join(lines)


def send_weekly_digest(settings: Settings, limit: int = 5) -> int:
    grants = top_n(settings, limit=limit)
    if not grants:
        log.info("No grants to send this week.")
        # Still notify by email to confirm the agent ran
        body = (
            f"Bonjour,\n\nAucune nouvelle opportunité de subvention pertinente "
            f"trouvée cette semaine ({_last_monday()}).\n\n"
            "L'agent continuera de chercher la semaine prochaine.\n\n"
            "L'agent Arc En Ciel 🌈"
        )
        send_email(
            settings,
            f"Arc En Ciel — Aucune subvention cette semaine ({_last_monday()})",
            body,
        )
        send_whatsapp(settings, _build_whatsapp([]))
        return 0

    subject, body = _build_email(grants)
    send_email(settings, subject, body)
    send_whatsapp(settings, _build_whatsapp(grants))

    mark_notified(settings, [g["id"] for g in grants])
    log.info("Digest sent with %d grants", len(grants))
    return len(grants)
