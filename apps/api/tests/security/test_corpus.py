"""F13-AC1, AC2, AC2a: the test corpus that measures the protection - its form, its size,
its sources - and the key figures computed from it."""

from collections import Counter

from app.security.evaluation import (
    ATTACK_CATEGORIES,
    CORPUS_DIR,
    Entry,
    Rate,
    evaluate,
    load_corpus,
)

CORPUS = load_corpus()


def test_every_entry_has_id_text_language_category_source_and_license():
    assert CORPUS, f"no corpus in {CORPUS_DIR}"
    for entry in CORPUS:
        assert entry.id and entry.text.strip(), entry
        assert entry.lang in {"de", "en"}, entry.id
        assert entry.category in ATTACK_CATEGORIES | {"benign"}, entry.id
        assert entry.source and entry.license, entry.id
    ids = [entry.id for entry in CORPUS]
    assert len(ids) == len(set(ids)), [i for i, n in Counter(ids).items() if n > 1]


def test_at_least_120_attacks_and_60_harmless_care_texts():
    attacks = [e for e in CORPUS if e.is_attack]
    harmless = [e for e in CORPUS if not e.is_attack]
    assert len(attacks) >= 120 and len(harmless) >= 60, (len(attacks), len(harmless))


def test_attacks_come_from_at_least_three_sources_and_mostly_german():
    by_file = Counter(entry.file for entry in CORPUS if entry.is_attack)
    assert {"deepset.jsonl", "bipia_style.jsonl", "pflege.jsonl"} <= set(by_file), by_file
    assert all(count >= 20 for count in by_file.values()), by_file
    assert sum(entry.lang == "de" for entry in CORPUS) > len(CORPUS) / 2


def test_the_public_dataset_keeps_its_license():
    for entry in CORPUS:
        if entry.file == "deepset.jsonl":
            assert entry.license == "Apache-2.0" and "deepset/prompt-injections" in entry.source


def test_the_key_figures_are_computed_as_defined():
    # F13-AC2a at a small example: detected = at least one checked layer flags it.
    def entry(n, category):
        return Entry(f"e{n}", "x", "de", category, "s", "l", "f.jsonl")

    entries = [
        entry(1, "ignore_instructions"),
        entry(2, "ignore_instructions"),
        entry(3, "exfiltration"),
        entry(4, "benign"),
        entry(5, "benign"),
    ]
    flagged = {"e1", "e3", "e4"}
    result = evaluate(entries, lambda e: e.id in flagged)
    assert result.detection == Rate(2, 3)
    assert result.false_alarms == Rate(1, 2)
    assert result.by_category == {
        "ignore_instructions": Rate(1, 2),
        "exfiltration": Rate(1, 1),
        "benign": Rate(1, 2),
    }
    assert result.missed == ["e2"] and result.false_alarm_ids == ["e4"]
    assert Rate(2, 3).percent == "66,7 %" and Rate(0, 0).percent == "–"
