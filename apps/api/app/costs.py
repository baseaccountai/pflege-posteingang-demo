"""What the public demo can cost per day at most (F10-AC11, ADR 0003).

    daily maximum = OCR pages x page price
                  + LLM calls x (max. input x input price + max. output x output price)
                  + embedding chunks x 800 tokens x embedding price

The quotas (F10-AC10, table quota_limits) cap the counts; the length limits below cap
each call. A test (tests/rls/test_daily_cost.py) reads the limits from the database and
fails if the result is above 0.50 EUR.

Everything is counted on the safe side:
- prices are the highest public list prices found (ADR 0003), USD counted as EUR,
- 3 characters per token (German text needs more tokens than English) - an estimate,
  not a hard bound (accepted, ADR 0003; the monthly limit in the Mistral account is),
- every LLM call is counted as the more expensive kind (field extraction or question),
- a retry is a call of its own (it is booked against the quota, too).
"""

import json
import math
from dataclasses import dataclass

from app.extraction.schema import SCHEMA
from app.extraction.service import MAX_INPUT_CHARS, MAX_OUTPUT_TOKENS, SYSTEM_PROMPT

DAILY_BUDGET_EUR = 0.50

# Prices (ADR 0003): Mistral OCR, Mistral Small, mistral-embed.
OCR_EUR_PER_PAGE = 4.00 / 1000
CHAT_INPUT_EUR_PER_TOKEN = 0.15 / 1_000_000
CHAT_OUTPUT_EUR_PER_TOKEN = 0.60 / 1_000_000
EMBED_EUR_PER_TOKEN = 0.10 / 1_000_000

CHARS_PER_TOKEN = 3

# Questions (F05, design F10): at most 6 chunks of 800 tokens, 600 tokens answer.
QUESTION_MAX_CHUNKS = 6
CHUNK_MAX_TOKENS = 800
QUESTION_MAX_OUTPUT_TOKENS = 600
QUESTION_PROMPT_TOKENS = 1000  # system prompt, question, source markers


@dataclass(frozen=True)
class CallCost:
    input_tokens: int
    output_tokens: int

    @property
    def eur(self) -> float:
        return (
            self.input_tokens * CHAT_INPUT_EUR_PER_TOKEN
            + self.output_tokens * CHAT_OUTPUT_EUR_PER_TOKEN
        )


def extraction_call() -> CallCost:
    """Field suggestion (F03): system prompt + JSON schema + the document, cut at 20 000 chars."""
    chars = (
        len(SYSTEM_PROMPT)
        + len(json.dumps(SCHEMA, ensure_ascii=False))
        + MAX_INPUT_CHARS
        + len("<<<DOKUMENT\n\nDOKUMENT>>>")
    )
    return CallCost(math.ceil(chars / CHARS_PER_TOKEN), MAX_OUTPUT_TOKENS)


def question_call() -> CallCost:
    """Question with sources (F05)."""
    return CallCost(
        QUESTION_MAX_CHUNKS * CHUNK_MAX_TOKENS + QUESTION_PROMPT_TOKENS,
        QUESTION_MAX_OUTPUT_TOKENS,
    )


def daily_maximum_eur(limits: dict[str, int]) -> float:
    """Cost of one day with every global quota used up (`limits` from quota_limits)."""
    worst_call = max(extraction_call().eur, question_call().eur)
    return (
        limits["ocr_page"] * OCR_EUR_PER_PAGE
        + limits["llm_call"] * worst_call
        + limits["embed_chunk"] * CHUNK_MAX_TOKENS * EMBED_EUR_PER_TOKEN
    )
