"""User Story 3 — Score and rank grants by best match for the association."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.fetcher import _extract_json, _is_missing
from src.agent.llm import build_llm, throttle
from src.agent.prompts import RANKING_PROMPT, SYSTEM_AGENT
from src.config import Settings, load_profile
from src.db import connect

log = logging.getLogger(__name__)


def _deadline_passed(deadline: str | None) -> bool:
    if not deadline:
        return False
    try:
        d = datetime.fromisoformat(deadline).date()
    except (ValueError, TypeError):
        return False
    return d < date.today()


def _eligibility_verdict(eligibility: str | None) -> str:
    if not eligibility:
        return "POTENTIALLY_ELIGIBLE"
    if eligibility.startswith("NOT_ELIGIBLE"):
        return "NOT_ELIGIBLE"
    if eligibility.startswith("ELIGIBLE"):
        return "ELIGIBLE"
    return "POTENTIALLY_ELIGIBLE"


def _score_one(llm, profile_json: str, grant: dict[str, Any]) -> dict[str, Any]:
    prompt = RANKING_PROMPT.format(
        profile_json=profile_json,
        title=grant.get("title") or "",
        organization=grant.get("organization") or "",
        amount=grant.get("amount") or "non spécifié",
        deadline=grant.get("deadline") or "non spécifié",
        description=grant.get("description") or "",
        eligibility_verdict=_eligibility_verdict(grant.get("eligibility")),
    )
    throttle()
    resp = llm.invoke(
        [SystemMessage(content=SYSTEM_AGENT), HumanMessage(content=prompt)]
    )
    parsed = _extract_json(resp.content if isinstance(resp.content, str) else str(resp.content))
    if not parsed:
        return {"score": 0, "reason": "Score impossible"}
    return parsed


def rank_all(settings: Settings) -> int:
    """Score every evaluated grant. Skip grants with passed deadlines or NOT_ELIGIBLE."""
    profile = load_profile()
    profile_json = json.dumps(profile, ensure_ascii=False, indent=2)
    llm = build_llm(settings)

    scored = 0
    with connect(settings.db_path) as conn:
        rows = conn.execute("SELECT * FROM grants WHERE status = 'evaluated'").fetchall()
        for row in rows:
            grant = dict(row)
            if _deadline_passed(grant.get("deadline")):
                conn.execute(
                    "UPDATE grants SET score = 0, score_reason = ?, status = 'expired' WHERE id = ?",
                    ("Deadline dépassée", row["id"]),
                )
                continue
            if _eligibility_verdict(grant.get("eligibility")) == "NOT_ELIGIBLE":
                conn.execute(
                    "UPDATE grants SET score = 0, score_reason = ?, status = 'rejected' WHERE id = ?",
                    ("Non éligible", row["id"]),
                )
                continue
            result = _score_one(llm, profile_json, grant)
            score = float(result.get("score", 0))
            reason = result.get("reason", "")
            conn.execute(
                "UPDATE grants SET score = ?, score_reason = ?, status = 'scored' WHERE id = ?",
                (score, reason, row["id"]),
            )
            scored += 1
            log.info("[%5.1f] %s — %s", score, grant.get("title", "?")[:60], reason[:80])
    log.info("Scored %d grants", scored)
    return scored


def top_n(settings: Settings, limit: int = 5) -> list[dict[str, Any]]:
    """Return up to `limit` best grants for the digest.

    Selection: 'scored' (new) and 'notified' (already sent) are both eligible.
    Excluded: 'rejected' (NOT_ELIGIBLE), 'expired' (deadline passed).

    Ordering — strict 4-level hierarchy:
      1. ELIGIBLE  >  POTENTIALLY_ELIGIBLE   (geography is critère N°1)
      2. Complete (amount + deadline both filled)  >  Incomplete
      3. Never-sent ('scored')  >  already-sent ('notified')
      4. Score desc
    """
    with connect(settings.db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM grants
            WHERE status IN ('scored', 'notified') AND score > 0
            ORDER BY score DESC
            """
        ).fetchall()
    grants = [dict(r) for r in rows]

    # 8 buckets: 2 (eligibility tier) × 2 (complete) × 2 (new)
    buckets: dict[tuple[str, bool, bool], list[dict[str, Any]]] = {
        (tier, complete, new): []
        for tier in ("ELIGIBLE", "POTENTIALLY_ELIGIBLE")
        for complete in (True, False)
        for new in (True, False)
    }
    for g in grants:
        verdict = _eligibility_verdict(g.get("eligibility"))
        if verdict == "NOT_ELIGIBLE":
            continue  # safety net — should already be filtered by status='rejected'
        is_complete = not (_is_missing(g.get("amount")) or _is_missing(g.get("deadline")))
        is_new = g.get("status") != "notified"
        buckets[(verdict, is_complete, is_new)].append(g)

    # Strict order: eligibility tier → completeness → freshness
    bucket_order = [
        ("ELIGIBLE", True, True),
        ("ELIGIBLE", True, False),
        ("ELIGIBLE", False, True),
        ("ELIGIBLE", False, False),
        ("POTENTIALLY_ELIGIBLE", True, True),
        ("POTENTIALLY_ELIGIBLE", True, False),
        ("POTENTIALLY_ELIGIBLE", False, True),
        ("POTENTIALLY_ELIGIBLE", False, False),
    ]

    log.info(
        "top_n pool — ELIGIBLE: complete[new=%d old=%d] incomplete[new=%d old=%d] | "
        "POTENTIALLY: complete[new=%d old=%d] incomplete[new=%d old=%d] → top %d",
        len(buckets[("ELIGIBLE", True, True)]),
        len(buckets[("ELIGIBLE", True, False)]),
        len(buckets[("ELIGIBLE", False, True)]),
        len(buckets[("ELIGIBLE", False, False)]),
        len(buckets[("POTENTIALLY_ELIGIBLE", True, True)]),
        len(buckets[("POTENTIALLY_ELIGIBLE", True, False)]),
        len(buckets[("POTENTIALLY_ELIGIBLE", False, True)]),
        len(buckets[("POTENTIALLY_ELIGIBLE", False, False)]),
        limit,
    )

    ordered: list[dict[str, Any]] = []
    for key in bucket_order:
        ordered.extend(buckets[key])
    return ordered[:limit]


def mark_notified(settings: Settings, ids: list[int]) -> None:
    if not ids:
        return
    placeholders = ",".join("?" * len(ids))
    now = datetime.utcnow().isoformat(timespec="seconds")
    with connect(settings.db_path) as conn:
        conn.execute(
            f"UPDATE grants SET notified_at = ?, status = 'notified' WHERE id IN ({placeholders})",
            (now, *ids),
        )
