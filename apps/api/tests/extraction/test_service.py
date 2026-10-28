"""F03-AC1, AC2, AC3: field suggestion from OCR text, one retry, every value needs a
verbatim source in the document."""

import pytest

from app.auth.principal import Principal
from app.extraction.service import MAX_INPUT_CHARS, Extractor
from app.providers.llm.base import LlmInvalidOutput, LlmUnavailable
from app.providers.llm.fake import FakeLlm
from app.quotas import QuotaExceeded
from samples.generate import ARZTBRIEF, MEDIKATIONSPLAN

pytestmark = pytest.mark.anyio

NURSE = Principal(sub="u", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1")
TEXT = "\n".join(ARZTBRIEF)


def field(value, evidence):
    return {"value": value, "evidence": evidence}


def answer(**overrides) -> dict:
    base = {
        "doc_type": field("arztbrief", "Entlassungsbrief"),
        "document_date": field("2026-10-20", "Klinikum Musterstadt, Innere Medizin, 20.10.2026"),
        "issuer": field("Klinikum Musterstadt", "Klinikum Musterstadt, Innere Medizin"),
        "resident_name": field("Hr. Muster-Bauer", "Patient: Hr. Muster-Bauer"),
        "diagnoses": [field("Herzinsuffizienz NYHA II", "- Herzinsuffizienz NYHA II")],
        "medications": [
            {
                "name": "Ramipril",
                "strength": "5 mg",
                "dosage": {"morgens": "1", "mittags": "0", "abends": "0", "nachts": "0"},
                "hint": None,
                "evidence": "| Ramipril | 5 mg | 1-0-0-0 |",
            }
        ],
        "follow_ups": [
            {
                "title": "Kontrolle Kreatinin",
                "due_date": None,
                "evidence": "Kontrolle Kreatinin und Kalium in 2 Wochen",
            }
        ],
    }
    base.update(overrides)
    return base


class Quota:
    def __init__(self, error: Exception | None = None):
        self.calls = 0
        self.error = error

    async def __call__(self, principal: Principal) -> None:
        self.calls += 1
        if self.error:
            raise self.error


async def extract(llm: FakeLlm, quota: Quota | None = None, text: str = TEXT):
    return await Extractor(llm, quota or Quota())(NURSE, "doc-1", text)


async def test_a_valid_answer_becomes_a_suggestion_with_found_sources():
    llm = FakeLlm([answer()])
    suggestion = await extract(llm)
    data = suggestion.data
    assert suggestion.model == llm.model_name
    assert data["doc_type"] == {
        "value": "arztbrief",
        "proposed": "arztbrief",
        "evidence": "Entlassungsbrief",
        "evidence_found": True,
    }
    assert data["document_date"]["value"] == "2026-10-20"
    assert data["medications"][0]["value"]["name"] == "Ramipril"
    assert data["medications"][0]["evidence_found"] is True
    assert data["diagnoses"][0]["value"] == "Herzinsuffizienz NYHA II"


async def test_the_document_is_passed_as_data_between_markers_and_cut_at_the_limit():
    llm = FakeLlm([answer()])
    await extract(llm, text="A" * (MAX_INPUT_CHARS + 500))
    system, user = llm.calls[0]
    assert "<<<DOKUMENT" in user and "DOKUMENT>>>" in user
    assert user.count("A") == MAX_INPUT_CHARS
    assert "Anweisungen im Dokument" in system  # instructions inside are data, not orders


@pytest.mark.parametrize(
    "bad", [LlmInvalidOutput("kein json"), {"doc_type": "kaputt"}], ids=["no-json", "wrong-schema"]
)
async def test_an_invalid_answer_is_asked_again_once_and_costs_quota(bad):
    llm, quota = FakeLlm([bad, answer()]), Quota()
    suggestion = await extract(llm, quota)
    assert suggestion.data["doc_type"]["value"] == "arztbrief"
    assert len(llm.calls) == 2 and quota.calls == 1


async def test_two_invalid_answers_give_no_suggestion_instead_of_guesses():
    llm, quota = FakeLlm([LlmInvalidOutput("x"), {"unsinn": True}]), Quota()
    suggestion = await extract(llm, quota)
    assert suggestion.data is None and suggestion.model == llm.model_name
    assert len(llm.calls) == 2 and quota.calls == 1


async def test_no_quota_for_the_retry_stops_with_quota_exceeded():
    with pytest.raises(QuotaExceeded):
        await extract(FakeLlm([LlmInvalidOutput("x")]), Quota(QuotaExceeded("llm_call")))


async def test_an_unreachable_llm_is_passed_on():
    with pytest.raises(LlmUnavailable):
        await extract(FakeLlm([LlmUnavailable("down")]))


@pytest.mark.parametrize(
    ("override", "path"),
    [
        ({"doc_type": field("medikationsplan", "Medikationsplan vom Hausarzt")}, ("doc_type",)),
        ({"document_date": field("2026-11-30", "Stand 30.11.2026")}, ("document_date",)),
        ({"issuer": field("Klinik Erfunden", "Klinik Erfunden")}, ("issuer",)),
        ({"resident_name": field("Fr. Testfeld", "Bewohnerin: Fr. Testfeld")}, ("resident_name",)),
        ({"diagnoses": [field("Asthma", "Diagnose Asthma bronchiale")]}, ("diagnoses", 0)),
        (
            {"follow_ups": [{"title": "Röntgen", "due_date": None, "evidence": "Röntgen Thorax"}]},
            ("follow_ups", 0),
        ),
    ],
    ids=["doc_type", "date", "issuer", "resident", "diagnosis", "follow_up"],
)
async def test_values_without_a_source_in_the_text_are_marked_and_not_prefilled(override, path):
    data = (await extract(FakeLlm([answer(**override)]))).data
    entry = data
    for key in path:
        entry = entry[key]
    assert entry["evidence_found"] is False
    assert entry["value"] is None and entry["proposed"] is not None


async def test_a_dose_that_differs_from_its_source_is_not_prefilled():
    # Evidence exists in the text, but says 5 mg - the model claims 50 mg.
    med = dict(answer()["medications"][0], strength="50 mg")
    entry = (await extract(FakeLlm([answer(medications=[med])]))).data["medications"][0]
    assert entry["evidence_found"] is False and entry["value"] is None
    assert entry["proposed"]["strength"] == "50 mg"


async def test_a_value_that_does_not_occur_in_its_source_is_not_prefilled():
    entry = (
        await extract(
            FakeLlm([answer(diagnoses=[field("Lungenkrebs", "- Herzinsuffizienz NYHA II")])])
        )
    ).data["diagnoses"][0]
    assert entry["evidence_found"] is False


async def test_a_calculated_due_date_is_not_prefilled_but_the_title_is():
    follow_up = {
        "title": "Kontrolle Kreatinin",
        "due_date": "2026-11-03",
        "evidence": "Kontrolle Kreatinin und Kalium in 2 Wochen",
    }
    entry = (await extract(FakeLlm([answer(follow_ups=[follow_up])]))).data["follow_ups"][0]
    assert entry["evidence_found"] is True
    assert entry["value"] == {"title": "Kontrolle Kreatinin", "due_date": None}
    assert entry["due_date_found"] is False


async def test_spacing_and_case_of_the_source_do_not_matter():
    data = (
        await extract(
            FakeLlm([answer(issuer=field("Klinikum Musterstadt", "KLINIKUM   musterstadt"))])
        )
    ).data
    assert data["issuer"]["evidence_found"] is True


@pytest.mark.parametrize(
    ("lines", "doc_type", "meds"),
    [(ARZTBRIEF, "arztbrief", 3), (MEDIKATIONSPLAN, "medikationsplan", 3)],
)
async def test_the_fake_llm_reads_the_sample_documents(lines, doc_type, meds):
    data = (await extract(FakeLlm(), text="\n".join(lines))).data
    assert data["doc_type"]["value"] == doc_type
    assert data["resident_name"]["value"] == "Hr. Muster-Bauer"
    assert len(data["medications"]) == meds
    assert all(m["evidence_found"] for m in data["medications"])


async def test_the_answer_is_limited_to_1500_tokens():
    # F10-AC11: the output limit is part of the daily cost calculation (app/costs.py).
    llm = FakeLlm([answer()])
    await extract(llm)
    assert llm.max_tokens == [1500]
