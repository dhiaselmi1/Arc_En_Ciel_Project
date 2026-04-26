"""User Story 2 — Check eligibility for each grant against the association profile."""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.fetcher import _extract_json
from src.agent.llm import build_llm, throttle
from src.agent.prompts import ELIGIBILITY_PROMPT, SYSTEM_AGENT
from src.config import Settings, load_profile
from src.db import connect

log = logging.getLogger(__name__)


def _evaluate(llm, profile_json: str, grant: dict[str, Any]) -> dict[str, Any]:
    prompt = ELIGIBILITY_PROMPT.format(
        profile_json=profile_json,
        title=grant.get("title") or "",
        organization=grant.get("organization") or "",
        amount=grant.get("amount") or "non spécifié",
        description=grant.get("description") or "",
        eligibility=grant.get("eligibility") or "non spécifié",
        source_url=grant.get("source_url") or "",
    )
    throttle()
    resp = llm.invoke(
        [SystemMessage(content=SYSTEM_AGENT), HumanMessage(content=prompt)]
    )
    parsed = _extract_json(resp.content if isinstance(resp.content, str) else str(resp.content))
    if not parsed:
        return {"verdict": "POTENTIALLY_ELIGIBLE", "reason": "Évaluation impossible", "blockers": []}
    return parsed


def evaluate_pending(settings: Settings) -> int:
    """Run eligibility on all grants without a verdict. Returns count evaluated."""
    profile = load_profile()
    profile_json = json.dumps(profile, ensure_ascii=False, indent=2)
    llm = build_llm(settings)

    evaluated = 0
    with connect(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM grants WHERE status = 'new' OR status IS NULL"
        ).fetchall()
        for row in rows:
            grant = dict(row)
            result = _evaluate(llm, profile_json, grant)
            verdict = result.get("verdict", "POTENTIALLY_ELIGIBLE")
            reason = result.get("reason", "")
            conn.execute(
                "UPDATE grants SET eligibility = ?, status = ? WHERE id = ?",
                (f"{verdict} — {reason}", "evaluated", row["id"]),
            )
            evaluated += 1
            log.info("[%s] %s — %s", verdict, grant.get("title", "?")[:60], reason[:80])
    log.info("Evaluated %d grants", evaluated)
    return evaluated
