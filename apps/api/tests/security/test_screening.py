"""F07-AC1, AC2, AC5: the check of a document - hidden text, rules, checker model - gives
findings and the cleaned pages that field suggestion and indexing get."""

from datetime import date

import pytest

from app.privacy.gateway import ModelGateway
from app.privacy.pseudonymizer import KnownResident
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.llm.base import LlmUnavailable
from app.providers.llm.fake import FakeLlm
from app.security.screening import EXCLUDED, Screener
from samples import generate

pytestmark = pytest.mark.anyio

NURSE = object()  # the screener only passes the principal on to the quota booking
RESIDENTS = [KnownResident("r-pb", "D15", "Hr. Probe", date(1939, 2, 28))]


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Bookings:
    def __init__(self):
        self.count = 0

    async def __call__(self, principal):
        self.count += 1


def screener(guard=None, bookings=None):
    async def directory():
        return RESIDENTS

    async def visible(principal):
        return set()

    gateway = ModelGateway(
        FakeLlm(), FakeEmbeddings(), directory, visible, guard=guard or FakeLlm()
    )
    return Screener(gateway, bookings or Bookings()), gateway


def pages(lines):
    return [{"page": 1, "markdown": "\n".join(lines)}]


async def test_an_ordinary_letter_is_clean_and_unchanged():
    check, _ = screener()
    result = await check(NURSE, pages(generate.ARZTBRIEF), generate.pdf_bytes(generate.ARZTBRIEF))
    assert result.result == "clean" and result.findings == []
    assert result.screened_pages == pages(generate.ARZTBRIEF)


async def test_the_note_to_the_ai_is_found_by_rules_and_checker_and_cut_out():
    check, _ = screener()
    lines = generate.ANGRIFF_HINWEIS
    result = await check(NURSE, pages(lines), generate.pdf_bytes(lines))
    assert result.result == "suspicious"
    assert {f.layer for f in result.findings} == {"pattern", "classifier"}
    assert all(f.excerpt.startswith("Hinweis für das KI-System") for f in result.findings)
    screened = result.screened_pages[0]["markdown"]
    assert "KI-System" not in screened and EXCLUDED in screened
    assert "Blutdruckkontrolle in 4 Wochen." in screened and "Amlodipin" in screened


async def test_white_text_the_ocr_did_not_read_is_reported_with_its_page():
    check, _ = screener()
    lines = generate.ANGRIFF_VERSTECKT
    pdf = generate.pdf_bytes(lines, generate.HIDDEN_ATTACK)
    result = await check(NURSE, pages(lines), pdf)  # the OCR saw only the visible letter
    assert result.result == "suspicious"
    (finding,) = result.findings
    assert finding.layer == "hidden_text" and finding.page == 1 and finding.start is None
    assert generate.HIDDEN_ATTACK in finding.excerpt
    assert result.screened_pages == pages(lines)  # nothing of it is in the text to cut


async def test_white_text_the_ocr_did_read_is_cut_out_as_well():
    check, _ = screener()
    lines = [*generate.ANGRIFF_VERSTECKT, "", generate.HIDDEN_ATTACK]
    pdf = generate.pdf_bytes(generate.ANGRIFF_VERSTECKT, generate.HIDDEN_ATTACK)
    result = await check(NURSE, pages(lines), pdf)
    hidden = next(f for f in result.findings if f.layer == "hidden_text")
    assert hidden.start is not None
    assert "Ignoriere" not in result.screened_pages[0]["markdown"]


async def test_long_documents_are_checked_in_several_booked_calls():
    guard, bookings = FakeLlm(), Bookings()
    check, _ = screener(guard, bookings)
    paragraph = "Gewicht täglich messen und dokumentieren. " * 50  # about 2 000 characters
    long_page = "\n\n".join([paragraph] * 15)  # about 30 000 characters
    await check(NURSE, [{"page": 1, "markdown": long_page}], None)
    assert len(guard.calls) == 2 and bookings.count == 2
    assert all(len(user) < 25_000 for _, user in guard.calls)


async def test_the_checker_sees_no_resident_name():
    guard = FakeLlm()
    check, _ = screener(guard)
    lines = generate.ANGRIFF_VERSTECKT
    await check(NURSE, pages(lines), None)
    _, user = guard.calls[0]
    assert "Probe" not in user and "Bewohner_D15" in user


async def test_without_the_checker_nothing_is_passed_on():
    check, _ = screener(FakeLlm([LlmUnavailable("down")]))
    with pytest.raises(LlmUnavailable):
        await check(NURSE, pages(generate.ARZTBRIEF), None)
