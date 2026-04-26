"""SQLite storage for grant opportunities."""
from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS grants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash        TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    organization    TEXT,
    amount          TEXT,
    deadline        TEXT,
    source_url      TEXT NOT NULL,
    description     TEXT,
    language        TEXT,
    eligibility     TEXT,
    score           REAL,
    score_reason    TEXT,
    status          TEXT DEFAULT 'new',
    fetched_at      TEXT NOT NULL,
    notified_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_grants_status   ON grants(status);
CREATE INDEX IF NOT EXISTS idx_grants_score    ON grants(score DESC);
CREATE INDEX IF NOT EXISTS idx_grants_deadline ON grants(deadline);
"""


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode("utf-8")).hexdigest()


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_grant(conn: sqlite3.Connection, grant: dict[str, Any]) -> bool:
    """Insert a grant if its source_url is new. Return True if inserted."""
    h = url_hash(grant["source_url"])
    existing = conn.execute("SELECT 1 FROM grants WHERE url_hash = ?", (h,)).fetchone()
    if existing:
        return False
    conn.execute(
        """
        INSERT INTO grants (
            url_hash, title, organization, amount, deadline,
            source_url, description, language, eligibility, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            h,
            grant.get("title", "").strip(),
            grant.get("organization"),
            grant.get("amount"),
            grant.get("deadline"),
            grant["source_url"],
            grant.get("description"),
            grant.get("language"),
            grant.get("eligibility"),
            datetime.utcnow().isoformat(timespec="seconds"),
        ),
    )
    return True


def list_recent(conn: sqlite3.Connection, limit: int = 20) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM grants ORDER BY fetched_at DESC LIMIT ?", (limit,)
    ).fetchall()
