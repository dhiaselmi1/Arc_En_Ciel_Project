"""Weekly entry point: fetch → eligibility → rank → send digest."""
from __future__ import annotations

import argparse
import logging
import sys

from src.agent.eligibility import evaluate_pending
from src.agent.fetcher import fetch_and_store
from src.agent.ranker import rank_all
from src.config import load_settings
from src.db import connect
from src.notifications.digest import send_weekly_digest


def reset_rejected() -> None:
    """Reset NOT_ELIGIBLE grants back to 'new' so they get re-evaluated.

    Useful after softening the eligibility prompt.
    """
    settings = load_settings()
    with connect(settings.db_path) as conn:
        cursor = conn.execute(
            "UPDATE grants SET status = 'new', eligibility = NULL, "
            "score = NULL, score_reason = NULL "
            "WHERE status = 'rejected'"
        )
        print(f"Reset {cursor.rowcount} rejected grant(s) to 'new' for re-evaluation.")


def print_stats() -> None:
    settings = load_settings()
    with connect(settings.db_path) as conn:
        total = conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0]
        print(f"\nTotal grants in DB: {total}\n")

        print("By status:")
        for status, count in conn.execute(
            "SELECT COALESCE(status, '(null)'), COUNT(*) FROM grants GROUP BY status"
        ):
            print(f"  {status:12s} {count}")

        print("\nAll grants (id | status | score | amount | deadline | title):")
        for row in conn.execute(
            "SELECT id, status, score, amount, deadline, title FROM grants ORDER BY status, score DESC"
        ):
            amount = (row["amount"] or "")[:25]
            deadline = (row["deadline"] or "")[:15]
            title = (row["title"] or "")[:60]
            print(f"  {row['id']:3} | {row['status'] or '(null)':12s} | {row['score'] or 0:5} | {amount:25s} | {deadline:15s} | {title}")
        print()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def run_pipeline(skip_send: bool = False) -> None:
    settings = load_settings()

    print("\n=== STEP 1: Fetch grants ===")
    inserted = fetch_and_store(settings)
    print(f"  → {inserted} new grants stored")

    print("\n=== STEP 2: Evaluate eligibility ===")
    evaluated = evaluate_pending(settings)
    print(f"  → {evaluated} grants evaluated")

    print("\n=== STEP 3: Rank grants ===")
    scored = rank_all(settings)
    print(f"  → {scored} grants scored")

    if skip_send:
        print("\n=== STEP 4: SKIPPED (dry run) ===")
        return

    print("\n=== STEP 4: Send weekly digest ===")
    sent = send_weekly_digest(settings, limit=5)
    print(f"  → digest sent with {sent} opportunities\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Arc En Ciel grant finder agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run fetch + eligibility + rank but skip sending notifications",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print DB stats and exit (no pipeline run)",
    )
    parser.add_argument(
        "--reset-rejected",
        action="store_true",
        help="Reset NOT_ELIGIBLE grants back to 'new' so they get re-evaluated",
    )
    args = parser.parse_args()

    setup_logging()
    if args.stats:
        print_stats()
        return 0
    if args.reset_rejected:
        reset_rejected()
        return 0
    try:
        run_pipeline(skip_send=args.dry_run)
        return 0
    except Exception as exc:
        logging.exception("Pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
