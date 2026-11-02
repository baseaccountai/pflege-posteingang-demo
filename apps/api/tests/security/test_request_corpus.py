"""F13-AC9: the corpus of questions and agent tasks - harmless requests of every kind the app
offers, wishes outside its scope, and attacks in the form of a task (F07-AC15)."""

from collections import Counter

from app.security.classifier import REQUEST_PROMPT, SYSTEM_PROMPT
from app.security.evaluation import ATTACK_CATEGORIES, REQUESTS_DIR, load_corpus

REQUESTS = load_corpus(REQUESTS_DIR)


def test_every_request_has_id_text_language_category_source_and_license():
    assert REQUESTS, f"no requests in {REQUESTS_DIR}"
    for entry in REQUESTS:
        assert entry.id and entry.text.strip(), entry
        assert entry.lang in {"de", "en"}, entry.id
        assert entry.category in ATTACK_CATEGORIES | {"benign"}, entry.id
        assert entry.source and entry.license, entry.id
        assert len(entry.text) <= 500, entry.id  # a question or task has at most 500 chars
    ids = [entry.id for entry in REQUESTS]
    assert len(ids) == len(set(ids)), [i for i, n in Counter(ids).items() if n > 1]


def test_at_least_25_harmless_requests_and_20_attacks():
    harmless = [e for e in REQUESTS if not e.is_attack]
    attacks = [e for e in REQUESTS if e.is_attack]
    assert len(harmless) >= 25 and len(attacks) >= 20, (len(harmless), len(attacks))


def test_every_tool_of_the_agent_is_asked_for_in_a_harmless_task():
    harmless = " ".join(e.text for e in REQUESTS if not e.is_attack)
    # suchen, Akte lesen, Medikation abgleichen, Wiedervorlagen auflisten, vorschlagen (F08)
    for asks in (
        "Suche",
        "Lies die Akte",
        "Gleiche die Medikation",
        "Wiedervorlagen sind",
        "Plane",
    ):
        assert asks in harmless, asks


def test_wishes_outside_the_scope_are_harmless_requests():
    # Changing a dose or deleting is no attack on the AI: the agent has no tool for it (F07-AC15).
    harmless = [e.text for e in REQUESTS if not e.is_attack]
    assert any(text.startswith("Ändere die Dosis") for text in harmless)
    assert any(text.startswith("Lösche") for text in harmless)


def test_no_request_is_copied_into_the_checker_instructions():
    # Like F07-AC13 for the rules: the measurement must not be written into what it measures.
    for entry in REQUESTS:
        for start in range(0, max(1, len(entry.text) - 29)):
            piece = entry.text[start : start + 30]
            assert piece not in REQUEST_PROMPT and piece not in SYSTEM_PROMPT, entry.id
