"""User Story 1 — Fetch grant opportunities from the web.

Pipeline:
  1. Run a list of search queries (Tavily, with DDG fallback).
  2. For each result, ask the LLM to extract a structured grant record.
  3. Persist new records to SQLite (dedup by source URL).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.llm import build_llm, throttle
from src.agent.prompts import EXTRACT_GRANT_FROM_RESULT, SEARCH_QUERIES, SYSTEM_AGENT
from src.config import Settings
from src.db import connect, init_db, upsert_grant
from src.search.ddg_fallback import search_ddg
from src.search.tavily_search import search_tavily

log = logging.getLogger(__name__)

JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

MISSING_VALUES = {
    "", "non spécifié", "non specifié", "non specified", "non précisé",
    "non precise", "unknown", "inconnu", "n/a", "na", "none", "null",
    "tbd", "à définir", "a definir",
}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip().lower() in MISSING_VALUES

# Skip results whose URL or title clearly aren't grant-specific.
# Saves LLM calls (and tokens) on obvious noise.
NON_GRANT_HINTS = (
    "wikipedia.org",
    "facebook.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "/blog/",
    "/news/",
    "/about",
    "/contact",
)


def _looks_like_grant(result: dict[str, Any]) -> bool:
    url = (result.get("url") or "").lower()
    if any(hint in url for hint in NON_GRANT_HINTS):
        return False
    blob = f"{result.get('title', '')} {result.get('content', '')}".lower()
    keywords = (
        "grant", "subvention", "appel à projet", "appel à projets",
        "funding", "financement", "fund", "bourse", "call for proposals",
        "appel à candidatures", "deadline", "date limite",
    )
    return any(k in blob for k in keywords)


def _extract_json(text: str) -> dict[str, Any] | None:
    match = JSON_BLOCK.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _extract_grant(llm, result: dict[str, Any]) -> dict[str, Any] | None:
    prompt = EXTRACT_GRANT_FROM_RESULT.format(
        url=result["url"],
        title=result["title"],
        content=result["content"][:1500],
    )
    throttle()
    resp = llm.invoke(
        [SystemMessage(content=SYSTEM_AGENT), HumanMessage(content=prompt)]
    )
    parsed = _extract_json(resp.content if isinstance(resp.content, str) else str(resp.content))
    if not parsed or not parsed.get("is_grant"):
        return None
    parsed["source_url"] = result["url"]
    return parsed


def _gather_search_results(settings: Settings) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    results: list[dict[str, Any]] = []
    for query in SEARCH_QUERIES:
        log.info("Searching: %s", query)
        batch = search_tavily(settings.tavily_api_key, query)
        if not batch:
            log.info("Tavily empty — falling back to DuckDuckGo")
            batch = search_ddg(query)
        for r in batch:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                results.append(r)
    log.info("Total unique search results: %d", len(results))
    return results


def fetch_and_store(settings: Settings) -> int:
    """Fetch new grants and store them in DB. Returns count of newly inserted."""
    init_db(settings.db_path)
    llm = build_llm(settings)

    raw_results = _gather_search_results(settings)
    filtered = [r for r in raw_results if _looks_like_grant(r)]
    log.info("Pre-filtered %d → %d results worth sending to LLM", len(raw_results), len(filtered))

    inserted = 0
    with connect(settings.db_path) as conn:
        for r in filtered:
            grant = _extract_grant(llm, r)
            if not grant:
                continue
            if upsert_grant(conn, grant):
                inserted += 1
                log.info("Stored: %s", grant.get("title", "?"))
    log.info("Inserted %d new grants", inserted)
    return inserted
