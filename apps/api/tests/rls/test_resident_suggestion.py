"""F03-AC5: the resident suggestion only looks at residents the caller may see (RLS)."""

import pytest

from app.auth.principal import Principal
from app.extraction.resident_match import suggest_resident
from tests.rls.conftest import WB1_RESIDENT

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(sub="a", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1")
NURSE_WB2 = Principal(sub="b", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2")


async def test_own_resident_is_found(db):
    async with db.as_principal(NURSE_WB1) as conn:
        assert await suggest_resident(conn, "Hr. Muster-Bauer") == WB1_RESIDENT


async def test_a_resident_of_another_ward_is_never_suggested(db):
    async with db.as_principal(NURSE_WB2) as conn:
        assert await suggest_resident(conn, "Hr. Muster-Bauer") is None
