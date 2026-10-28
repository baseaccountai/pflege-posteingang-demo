"""F05-AC6: names after a form of address are recognised in a question."""

import pytest

from app.rag.retrieval import surname, titled_names


@pytest.mark.parametrize(
    ("question", "names"),
    [
        ("Welche Medikamente bekommt Hr. Muster-Bauer?", ["muster-bauer"]),
        ("Was steht bei Herrn Probe zur Kontrolle?", ["probe"]),
        ("Wie geht es Frau Beispiel und Herr Exempel?", ["beispiel", "exempel"]),
        ("Hat Fr.Vorlage eine Wiedervorlage?", ["vorlage"]),
        ("Welche Diagnosen gibt es im Wohnbereich?", []),
        ("Was empfiehlt die Frauenärztin?", []),  # "Frau" only as a whole word
    ],
)
def test_names_after_a_form_of_address(question, names):
    assert titled_names(question) == names


@pytest.mark.parametrize(
    ("display_name", "expected"),
    [("Hr. Muster-Bauer", "muster-bauer"), ("Fr. Beispiel", "beispiel"), ("Probe", "probe")],
)
def test_the_surname_of_a_display_name(display_name, expected):
    assert surname(display_name) == expected
