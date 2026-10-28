"""F05-AC2, AC3: structure first (headings, tables whole), only oversized sections are split
recursively with overlap; a table above the maximum is split by rows with its header."""

from app.rag.chunker import (
    MAX_TOKENS,
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    Chunk,
    count_tokens,
    split_pages,
)

ARZTBRIEF = """# Entlassungsbrief
Klinikum Musterstadt, Innere Medizin, 20.10.2026
Patient: Hr. Muster-Bauer

## Diagnosen
- Herzinsuffizienz NYHA II
- Arterielle Hypertonie

## Medikation bei Entlassung
| Medikament | Stärke | Dosierung |
|---|---|---|
| Ramipril | 5 mg | 1-0-0-0 |
| Torasemid | 10 mg | 1-0-0-0 |

## Procedere
Kontrolle beim Hausarzt in zwei Wochen. Gewicht täglich messen.
"""

TABLE_HEADER = "| Medikament | Stärke | Dosierung |\n|---|---|---|"


def table(rows: int) -> str:
    lines = [f"| Medikament {i:03d} mit langem Namen | {i} mg | 1-0-1-0 |" for i in range(rows)]
    return TABLE_HEADER + "\n" + "\n".join(lines)


def sentences(count: int, start: int = 0) -> str:
    return " ".join(
        f"Satz {i} beschreibt die Pflegesituation ausführlich und nachvollziehbar."
        for i in range(start, start + count)
    )


def test_limits_are_the_start_values_of_the_spec():
    assert (TARGET_TOKENS, MAX_TOKENS) == (600, 800)
    assert OVERLAP_TOKENS == 72  # 12 % of the target
    assert count_tokens("x" * 400) == 100  # characters / 4


def test_a_letter_is_split_at_its_headings():
    chunks = split_pages([(1, ARZTBRIEF)])
    assert [c.heading for c in chunks] == [
        "Entlassungsbrief",
        "Diagnosen",
        "Medikation bei Entlassung",
        "Procedere",
    ]
    assert all(c.page == 1 for c in chunks)
    assert "Herzinsuffizienz NYHA II" in chunks[1].content
    assert "| Torasemid | 10 mg | 1-0-0-0 |" in chunks[2].content
    assert chunks[2].content.startswith("## Medikation bei Entlassung")


def test_a_table_up_to_the_maximum_stays_whole_in_a_section_above_the_target():
    medication_table = table(50)
    assert TARGET_TOKENS < count_tokens(medication_table) <= MAX_TOKENS
    page = f"## Medikationsplan\n{sentences(5)}\n\n{medication_table}\n\n{sentences(5, 100)}\n"
    chunks = split_pages([(1, page)])
    with_table = [c for c in chunks if "Medikament 000" in c.content]
    assert len(with_table) == 1
    assert medication_table in with_table[0].content
    assert all(c.heading == "Medikationsplan" for c in chunks)


def test_a_long_section_is_split_with_overlap_and_nothing_is_lost():
    text = sentences(200)
    chunks = split_pages([(2, f"## Pflegebericht\n{text}\n")])
    assert len(chunks) > 1
    assert all(count_tokens(c.content) <= MAX_TOKENS for c in chunks)
    for i in range(200):
        assert any(f"Satz {i} " in c.content for c in chunks), i
    for before, after in zip(chunks, chunks[1:], strict=False):
        # The next chunk starts with the end of the previous one (about 12 %).
        tail = before.content[-(OVERLAP_TOKENS * 4) // 2 :]
        assert tail in after.content
    assert {c.heading for c in chunks} == {"Pflegebericht"}
    assert {c.page for c in chunks} == {2}


def test_a_table_above_the_maximum_is_split_by_rows_with_the_header_in_every_part():
    big = table(120)
    assert count_tokens(big) > MAX_TOKENS
    chunks = split_pages([(1, f"## Medikationsplan\n{big}\n")])
    assert len(chunks) > 1
    rows = big.splitlines()[2:]
    seen = []
    for chunk in chunks:
        assert TABLE_HEADER in chunk.content
        assert count_tokens(chunk.content) <= MAX_TOKENS
        seen += [line for line in chunk.content.splitlines() if line in rows]
    assert seen == rows  # every row exactly once, in order


def test_long_lines_without_blank_lines_and_one_huge_line_are_split_too():
    lines = "\n".join(sentences(3, i * 3) for i in range(60))  # one paragraph, many lines
    huge_line = sentences(150, 1000)  # one line, many sentences
    chunks = split_pages([(1, f"## A\n{lines}\n\n## B\n{huge_line}\n")])
    assert all(count_tokens(c.content) <= MAX_TOKENS for c in chunks)
    assert sum(c.heading == "A" for c in chunks) > 1
    assert sum(c.heading == "B" for c in chunks) > 1


def test_a_single_endless_word_is_cut_hard_rather_than_kept_too_large():
    chunks = split_pages([(1, "## X\n" + "A" * 10_000 + "\n")])
    assert all(count_tokens(c.content) <= MAX_TOKENS for c in chunks)
    assert sum(c.content.count("A") for c in chunks) >= 10_000


def test_the_heading_continues_on_the_next_page():
    pages = [(1, "## Verlauf\nErster Teil des Verlaufs."), (2, "Zweiter Teil des Verlaufs.")]
    chunks = split_pages(pages)
    assert [(c.page, c.heading) for c in chunks] == [(1, "Verlauf"), (2, "Verlauf")]


def test_empty_pages_and_text_before_any_heading():
    chunks = split_pages([(1, "  \n\n"), (2, "Ohne Überschrift.\n\n# Titel\nText")])
    assert [(c.page, c.heading, c.content) for c in chunks] == [
        (2, None, "Ohne Überschrift."),
        (2, "Titel", "# Titel\nText"),
    ]


def test_the_token_count_can_be_replaced():
    words = " ".join(["Wort"] * 50)
    one_per_word = lambda text: len(text.split())  # noqa: E731
    chunks = split_pages([(1, f"## A\n{words}")], count=one_per_word, target=20, maximum=30)
    assert len(chunks) > 1
    assert all(one_per_word(c.content) <= 30 for c in chunks)


def test_chunks_are_plain_values():
    assert Chunk(page=1, heading=None, content="x") == Chunk(1, None, "x")


def test_a_small_section_with_text_and_table_stays_one_chunk():
    section = f"## Medikation\nStand: 20.10.2026\n\n{table(3)}\n\nBei Fragen Hausarzt anrufen."
    chunks = split_pages([(1, section)])
    assert [c.content for c in chunks] == [section]
