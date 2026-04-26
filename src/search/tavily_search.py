"""Tavily search wrapper. Falls back to DuckDuckGo on failure."""
from __future__ import annotations

import logging
from typing import Any

from tavily import TavilyClient

log = logging.getLogger(__name__)


def search_tavily(api_key: str, query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Return a list of {title, url, content} dicts."""
    client = TavilyClient(api_key=api_key)
    try:
        resp = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
        )
    except Exception as exc:
        log.warning("Tavily search failed for %r: %s", query, exc)
        return []
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        }
        for r in resp.get("results", [])
        if r.get("url")
    ]
