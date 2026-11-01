"""The fixed texts the backend sends to a model must not look like a resident's name.

The model gateway refuses every call whose text still contains a resident's name (F06-AC10),
and a bare surname counts when it is capitalised. Some invented surnames of the seed are
ordinary German words ("Fr. Beispiel", "Fr. Vorlage"): a system prompt saying "zum
Beispiel" made every agent call fail in the demo. So every fixed prompt is checked here
against the residents of the seed - the people of the public demo.
"""

import json
import re
from pathlib import Path

import pytest

from app.agent import runner
from app.agent.tools import tool_schemas
from app.extraction import service as extraction
from app.privacy.pseudonymizer import KnownResident, Pseudonymizer
from app.rag import answer
from app.security import classifier

SEED = Path(__file__).resolve().parents[4] / "supabase" / "seed" / "01_wards_residents.sql"


def seed_residents() -> list[KnownResident]:
    """(id, ward, 'Hr. Name', 'YYYY-MM-DD', room, 'K42') rows of the seed file."""
    row = r"\('([0-9a-f-]{36})', '\w+', '([^']+)', '(\d{4}-\d{2}-\d{2})'"
    rows = re.findall(row, SEED.read_text())
    assert len(rows) >= 6, "seed residents not found"
    return [KnownResident(rid, f"S{i:02d}", name, None) for i, (rid, name, _) in enumerate(rows)]


FIXED_TEXTS = {
    "agent system prompt": runner.SYSTEM_PROMPT,
    "agent tools": json.dumps(tool_schemas(), ensure_ascii=False),
    "answer system prompt": answer.SYSTEM_PROMPT,
    "extraction system prompt": extraction.SYSTEM_PROMPT,
    "classifier system prompt": classifier.SYSTEM_PROMPT,
}


@pytest.mark.parametrize("name", FIXED_TEXTS)
def test_a_fixed_prompt_contains_no_name_of_a_seed_resident(name):
    assert not Pseudonymizer(seed_residents()).leaks(FIXED_TEXTS[name])
