"""F02-AC7: unreadable scans and non-care documents get no field suggestion."""

import pytest

from app.documents.readability import check_readability

ARZTBRIEF = """# Entlassungsbrief

Sehr geehrte Kollegin, wir berichten über Ihre Patientin Fr. Testfeld.

**Diagnose:** Herzinsuffizienz NYHA II

| Medikament | Stärke | Dosierung |
|---|---|---|
| Torasemid | 10 mg | 1-0-0-0 |
"""

REZEPT = """# Omas Apfelkuchen

Zutaten: 500 g Mehl, 250 g Butter, 200 g Zucker, 4 Eier, 1 kg Äpfel.
Den Teig kneten, die Äpfel schälen und in Spalten schneiden. Bei 180 Grad 45 Minuten backen.
"""

RECHNUNG = """# Rechnung Nr. 2026-1043

Malerbetrieb Pinsel GmbH, Musterstraße 1. Leistung: Streichen Flur und Treppenhaus.
Arbeitszeit 12 Stunden, Material pauschal. Gesamtbetrag 1.240,00 EUR, zahlbar in 14 Tagen.
"""


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("", "unreadable_text"),
        ("   \n\n  \t ", "unreadable_text"),
        ("x" * 50, "unreadable_text"),
        # 79 visible characters spread over whitespace still count as too short.
        (" ".join(["Diagnose mg"] * 7)[:90], "unreadable_text"),
        (REZEPT, "not_care_document"),
        (RECHNUNG, "not_care_document"),
    ],
    ids=["empty", "whitespace", "50-chars", "short-with-words", "recipe", "invoice"],
)
def test_unreadable_or_foreign_text_is_rejected_with_a_reason(text, code):
    result = check_readability(text)
    assert (result.readable, result.error_code) == (False, code)


def test_a_discharge_letter_is_readable():
    result = check_readability(ARZTBRIEF)
    assert (result.readable, result.error_code) == (True, None)


def test_one_care_word_alone_is_not_enough():
    text = "Diagnose: " + "Dies ist ein langer Text ohne weiteren fachlichen Bezug zum Thema. " * 3
    assert check_readability(text).error_code == "not_care_document"


def test_words_are_matched_case_insensitively_and_inside_compounds():
    text = "HAUSARZT schreibt: DOSIERUNGSPLAN angepasst. " + "Weiterer Text ohne Bezug. " * 4
    assert check_readability(text).readable
