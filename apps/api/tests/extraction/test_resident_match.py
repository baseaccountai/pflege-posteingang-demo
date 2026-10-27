"""F03-AC5, F03-AC6: a resident is suggested only if exactly one of the own residents fits."""

import pytest

from app.extraction.resident_match import Candidate, match_resident

OWN = [
    Candidate("r1", "Hr. Muster-Bauer"),
    Candidate("r2", "Fr. Anna Testfeld"),
    Candidate("r3", "Hr. Jürgen Müller"),
    Candidate("r4", "Fr. Beispiel"),
]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Hr. Muster-Bauer", "r1"),
        ("Herr Muster-Bauer", "r1"),
        ("MUSTER-BAUER", "r1"),
        ("Muster-Bauer, Hans", "r1"),  # the record has no first name: the surname decides
        ("Fr. A. Testfeld", "r2"),
        ("Anna Testfeld", "r2"),
        ("Testfeld, Anna", "r2"),
        ("Hr. Juergen Mueller", "r3"),
        ("Frau Beispiel", "r4"),
    ],
)
def test_one_fitting_resident_is_suggested(name, expected):
    assert match_resident(name, OWN) == expected


@pytest.mark.parametrize(
    "name",
    [
        "Fr. Berta Testfeld",  # first name contradicts
        "Fr. B. Testfeld",  # initial contradicts
        "Hr. Unbekannt",
        "",
        None,
        "Dr. med. Lorem",  # the doctor, not a resident
    ],
)
def test_no_suggestion_without_a_clear_match(name):
    assert match_resident(name, OWN) is None


def test_two_residents_with_the_same_surname_give_no_suggestion():
    twins = [Candidate("a", "Hr. Probe"), Candidate("b", "Fr. Probe")]
    assert match_resident("Probe", twins) is None
    assert match_resident("Hr. Probe", twins) is None  # titles do not decide
