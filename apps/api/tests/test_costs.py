"""F10-AC11: input and output of every paid call are limited, so the daily quotas cost at
most 0.50 EUR. The calculation is code, so raising a limit makes this test fail."""

import json
import math

import pytest

from app import costs
from app.extraction.schema import SCHEMA
from app.extraction.service import MAX_INPUT_CHARS, MAX_OUTPUT_TOKENS, SYSTEM_PROMPT


def test_an_extraction_call_is_counted_with_prompt_schema_and_the_cut_document() -> None:
    chars = len(SYSTEM_PROMPT) + len(json.dumps(SCHEMA, ensure_ascii=False)) + MAX_INPUT_CHARS
    assert costs.extraction_call().input_tokens >= math.ceil(chars / costs.CHARS_PER_TOKEN)
    assert costs.extraction_call().output_tokens == MAX_OUTPUT_TOKENS == 1500


def test_a_question_call_is_counted_with_six_chunks_of_800_tokens() -> None:
    call = costs.question_call()
    assert call.input_tokens >= 6 * 800
    assert call.output_tokens == 600


def test_guard_calls_are_counted_with_prompt_schema_and_their_input_limit() -> None:
    # F07-AC4: a document check covers at most 20 000 characters (longer documents: more
    # calls), a question at most 500; counted at the prices of the more expensive chat model.
    from app.security import classifier as c

    document = len(c.SYSTEM_PROMPT) + len(json.dumps(c.SCHEMA)) + c.DOCUMENT_MAX_CHARS
    question = len(c.SYSTEM_PROMPT) + len(json.dumps(c.SCHEMA)) + c.QUESTION_MAX_CHARS
    assert (c.DOCUMENT_MAX_CHARS, c.QUESTION_MAX_CHARS) == (20_000, 500)
    assert costs.guard_document_call().input_tokens >= math.ceil(document / costs.CHARS_PER_TOKEN)
    assert costs.guard_question_call().input_tokens >= math.ceil(question / costs.CHARS_PER_TOKEN)
    assert costs.guard_document_call().output_tokens == c.DOCUMENT_MAX_TOKENS
    assert costs.guard_question_call().output_tokens == c.QUESTION_MAX_TOKENS


def test_the_daily_maximum_adds_ocr_llm_guard_and_embeddings() -> None:
    limits = {
        "ocr_page": 10,
        "llm_call": 10,
        "guard_document": 10,
        "guard_question": 10,
        "embed_chunk": 10,
    }
    worst = max(costs.extraction_call().eur, costs.question_call().eur)
    expected = (
        10 * costs.OCR_EUR_PER_PAGE
        + 10 * worst
        + 10 * costs.guard_document_call().eur
        + 10 * costs.guard_question_call().eur
        + 10 * costs.CHUNK_MAX_TOKENS * costs.EMBED_EUR_PER_TOKEN
    )
    assert costs.daily_maximum_eur(limits) == pytest.approx(expected)


def test_prices_are_the_conservative_upper_values_of_adr_0003() -> None:
    # USD prices counted as EUR (1 USD < 1 EUR), see ADR 0003.
    assert costs.OCR_EUR_PER_PAGE == pytest.approx(4.00 / 1000)
    assert costs.CHAT_INPUT_EUR_PER_TOKEN == pytest.approx(0.15 / 1_000_000)
    assert costs.CHAT_OUTPUT_EUR_PER_TOKEN == pytest.approx(0.60 / 1_000_000)
    assert costs.EMBED_EUR_PER_TOKEN == pytest.approx(0.10 / 1_000_000)
