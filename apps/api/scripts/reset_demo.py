"""Nightly reset of the public demo (F10-AC5 to AC8).

Deletes everything visitors left behind (uploads with their files, record entries,
sessions) and loads the seed again (supabase/seed/*.sql). Runs as the GitHub Action
`nightly-reset` - the only place with the database admin URL - or locally:

    make reset                                   (local Supabase)
    uv run python -m scripts.reset_demo --check-hour     (prints due=true|false)
    cd apps/api && uv run python -m scripts.reset_demo   (reads SUPABASE_DB_ADMIN_URL)

How it stays safe:
1. Maintenance on (own, committed statement): the API answers writes with 503 (AC7).
2. One transaction for the whole database part. TRUNCATE waits for running transactions
   and blocks new ones until the commit, so nobody sees a half-reset demo. Processing
   that started before the reset finds its document gone afterwards and writes nothing.
   If anything fails, everything is rolled back (AC8).
3. Maintenance off - also after an error (finally). The error still ends the script with
   a non-zero exit code, so the GitHub Action fails and notifies the applicant.

The quota counters (usage_counters) are not touched: the daily limit keeps counting (AC6).
No LLM or OCR calls are made (the seed brings everything with it).
"""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

SEED_DIR = Path(__file__).parents[3] / "supabase" / "seed"

# Everything a visitor can create. CASCADE also empties tables that hang on these (FKs).
VISITOR_TABLES = [
    "public.document_files",
    "public.medication_events",
    "public.medications",
    "public.diagnoses",
    "public.follow_ups",
    "public.agent_proposals",  # F08
    "public.documents",
    "public.residents",
    "public.wards",
    "bff.sessions",
    "public.audit_events",  # F12: the log of the demo day goes with the data it describes
]
LOCAL_ADMIN_DSN = "postgresql://postgres:postgres@127.0.0.1:56322/postgres"


def set_maintenance(conn: psycopg.Connection, on: bool) -> None:
    conn.execute("update public.system_state set maintenance = %s, updated_at = now()", [on])


def reset(admin_dsn: str, seed_files: list[Path]) -> None:
    """Empties the visitor tables and loads `seed_files` in the given order, atomically."""
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        set_maintenance(conn, True)
        try:
            with conn.transaction():
                # Do not wait forever for a hanging request; the Action then fails (AC8).
                conn.execute("set local lock_timeout = '30s'")
                conn.execute(f"truncate {', '.join(VISITOR_TABLES)} cascade")
                for path in seed_files:
                    conn.execute(path.read_text(encoding="utf-8"))
        finally:
            set_maintenance(conn, False)


def reset_due(now: datetime) -> bool:
    """True at 03:xx German time (F10-AC5). GitHub's cron knows only UTC, so the workflow
    starts at 01:00 and 02:00 UTC; summer or winter time, exactly one of them is 03:xx."""
    return now.astimezone(ZoneInfo("Europe/Berlin")).hour == 3


def main() -> None:
    if "--check-hour" in sys.argv:
        # Used by the scheduled workflow: prints due=true|false for $GITHUB_OUTPUT.
        print(f"due={str(reset_due(datetime.now(UTC))).lower()}")
        return
    dsn = os.environ.get("SUPABASE_DB_ADMIN_URL") or (
        LOCAL_ADMIN_DSN if "--local" in sys.argv else None
    )
    if not dsn:
        sys.exit("SUPABASE_DB_ADMIN_URL fehlt (oder --local für das lokale Supabase).")
    reset(dsn, sorted(SEED_DIR.glob("*.sql")))
    print("Demo zurückgesetzt.")


if __name__ == "__main__":
    main()
