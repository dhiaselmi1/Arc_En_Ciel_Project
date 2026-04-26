"""DuckDuckGo fallback search (no API key required)."""
from __future__ import annotations

import logging
from typing import Any

from duckduckgo_search import DDGS

log = logging.getLogger(__name__)


def search_ddg(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as exc:
        log.warning("DuckDuckGo search failed for %r: %s", query, exc)
        return []
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "content": r.get("body", ""),
        }
        for r in results
        if r.get("href")
    ]
