"""F06-AC2, AC3, AC6, AC10: names, birth dates and contact data become placeholders."""

from datetime import date

import pytest

from app.privacy.pseudonymizer import KnownResident, Pseudonymizer

RESIDENTS = [
    KnownResident("r1", "A17", "Hr. Muster-Bauer", date(1941, 4, 3)),
    KnownResident("r2", "K42", "Fr. Testfeld", date(1938, 9, 12)),
    KnownResident("r3", "P08", "Hr. Probe", date(1939, 2, 28)),
]


@pytest.fixture
def p():
    return Pseudonymizer(RESIDENTS)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Patient: Hr. Muster-Bauer, Zimmer 104", "Patient: Bewohner_A17, Zimmer 104"),
        ("bei Herrn Muster-Bauer und Frau Testfeld", "bei Bewohner_A17 und Bewohner_K42"),
        ("Fr.Testfeld bekommt Ramipril", "Bewohner_K42 bekommt Ramipril"),
        ("Muster-Bauer klagt über Schwindel", "Bewohner_A17 klagt über Schwindel"),
        ("HR. MUSTER-BAUER", "Bewohner_A17"),
        # Lower case "probe" is the ordinary word, not the resident.
        (
            "Blutprobe, eine probe Aufnahme, Hr. Probe",
            "Blutprobe, eine probe Aufnahme, Bewohner_P08",
        ),
    ],
)
def test_resident_names_become_their_stable_code(p, text, expected):
    assert p.pseudonymize(text).text == expected


@pytest.mark.parametrize(
    "written",
    ["03.04.1941", "3.4.1941", "03.04.41", "1941-04-03", "3. April 1941", "03. April 1941"],
)
def test_birth_dates_of_residents_become_a_placeholder_of_that_resident(p, written):
    result = p.pseudonymize(f"geb. {written}, Aufnahme 03.04.2026")
    assert result.text == "geb. Geburtsdatum_A17, Aufnahme 03.04.2026"  # other dates stay


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Behandelnder Arzt: Dr. med. Lorem", "Behandelnder Arzt: Person_1"),
        ("Hausarztpraxis Dr. Ipsum, Prof. Dr. Dolor", "Hausarztpraxis Person_1, Person_2"),
        ("Rückruf an Frau Lindner-Sommer", "Rückruf an Person_1"),
        ("Termin bei Frau Dr. med. Lorem", "Termin bei Person_1"),
        ("Herrn Prof. Dr. Ipsum anrufen", "Person_1 anrufen"),
        ("Tel. 0345 123456-7, Fax +49 (345) 765 4321", "Tel. [TELEFON_1], Fax [TELEFON_2]"),
        ("Mail: praxis.ipsum@example.org", "Mail: [E-MAIL_1]"),
        ("Versichertennr. A123456789", "Versichertennr. [VERSICHERTENNR_1]"),
        ("Wohnt Lindenstraße 12a, Musterstadt", "Wohnt [ADRESSE_1], Musterstadt"),
    ],
)
def test_other_people_and_contact_data_get_numbered_placeholders(p, text, expected):
    assert p.pseudonymize(text).text == expected


def test_the_same_value_keeps_its_placeholder_within_one_call(p):
    first = p.pseudonymize("Dr. Lorem schreibt an Dr. Ipsum.")
    second = p.pseudonymize("Antwort von Dr. Lorem", first.mapping)
    assert first.text == "Person_1 schreibt an Person_2."
    assert second.text == "Antwort von Person_1"


def test_placeholders_go_back_to_the_original_for_visible_residents(p):
    sent = p.pseudonymize("Hr. Muster-Bauer, geb. 03.04.1941, Dr. med. Lorem, Tel. 0345 123456")
    answer = "Bewohner_A17 (Geburtsdatum_A17) wird von Person_1 betreut, [TELEFON_1]. Bewohner_K42?"
    restored = p.restore(answer, sent.mapping, visible={"r1"})
    # K42 lives in a ward the caller cannot see: the code stays (F06-AC8).
    assert restored == (
        "Hr. Muster-Bauer (03.04.1941) wird von Dr. med. Lorem betreut, 0345 123456. Bewohner_K42?"
    )


def test_unknown_placeholders_stay_visible(p):
    assert p.restore("Person_9 und [TELEFON_3]", {}, visible=set()) == "Person_9 und [TELEFON_3]"


@pytest.mark.parametrize(
    ("text", "leak"),
    [
        ("Bewohner_A17 bekommt Ramipril", False),
        ("Rückfrage zu Testfeld", True),
        ("geboren 12.09.1938", True),
        ("eine Blutprobe", False),
    ],
)
def test_finds_names_or_birth_dates_left_in_outgoing_text(p, text, leak):
    assert p.leaks(text) is leak


@pytest.mark.parametrize(
    "token",
    ["A" * 20_000, "a" * 20_000, "1" * 20_000, "Aa-" * 7_000],
    ids=["upper", "lower", "digits", "hyphens"],
)
def test_a_long_word_without_spaces_is_handled_in_linear_time(p, token):
    # A document could carry such a word to slow the API down (regex backtracking).
    import time

    start = time.perf_counter()
    p.pseudonymize(token)
    assert time.perf_counter() - start < 0.5
