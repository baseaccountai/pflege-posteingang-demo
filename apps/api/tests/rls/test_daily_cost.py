"""F10-AC11: the quota limits in the database (F10-AC10) cost at most 0.50 EUR per day."""

import psycopg
import pytest

from app import costs
from tests.rls.conftest import ADMIN_DSN

pytestmark = pytest.mark.db


def test_the_daily_limits_cost_at_most_50_cent() -> None:
    with psycopg.connect(ADMIN_DSN) as conn:
        rows = conn.execute(
            "select kind, max_count from public.quota_limits where scope = 'global'"
        ).fetchall()
    limits = dict(rows)
    assert set(limits) == {
        "ocr_page",
        "llm_call",
        "guard_document",
        "guard_question",
        "embed_chunk",
    }
    assert costs.daily_maximum_eur(limits) <= costs.DAILY_BUDGET_EUR == 0.50
