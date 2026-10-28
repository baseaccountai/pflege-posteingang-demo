"""F03-AC7: the medication comparison is computed, not guessed by the LLM."""

import pytest

from app.extraction.medication_diff import Med, diff, diff_hash

RAMIPRIL = Med(name="Ramipril", strength="5 mg", dosage={"morgens": "1"})
METFORMIN = Med(name="Metformin", strength="500 mg", dosage={"morgens": "1", "abends": "1"})


def kinds(current, proposed) -> list[tuple[str, str]]:
    return [(change.kind, change.name) for change in diff(current, proposed)]


@pytest.mark.parametrize(
    ("current", "proposed", "expected"),
    [
        ([], [RAMIPRIL], [("new", "Ramipril")]),
        ([RAMIPRIL], [RAMIPRIL], [("unchanged", "Ramipril")]),
        ([RAMIPRIL], [], [("discontinued", "Ramipril")]),
        (
            [RAMIPRIL],
            [Med(name="Ramipril", strength="10 mg", dosage={"morgens": "1"})],
            [("changed", "Ramipril")],
        ),
        (
            [RAMIPRIL],
            [Med(name="Ramipril", strength="5 mg", dosage={"morgens": "1", "abends": "1"})],
            [("changed", "Ramipril")],
        ),
        (
            [RAMIPRIL, METFORMIN],
            [Med(name="Torasemid", strength="10 mg", dosage={"morgens": "1"}), RAMIPRIL],
            [("new", "Torasemid"), ("unchanged", "Ramipril"), ("discontinued", "Metformin")],
        ),
    ],
    ids=["new", "unchanged", "discontinued", "strength", "dosage", "mixed"],
)
def test_each_kind_of_change(current, proposed, expected):
    assert kinds(current, proposed) == expected


@pytest.mark.parametrize(
    "variant",
    [
        Med(name="RAMIPRIL", strength="5 mg", dosage={"morgens": "1"}),
        Med(name="  ramipril ", strength="5mg", dosage={"morgens": "1"}),
        Med(name="Ramipril", strength="5 MG", dosage={"morgens": "1", "mittags": "0"}),
        Med(name="Ramipril", strength="5,0 mg", dosage={"morgens": "1.0", "nachts": ""}),
    ],
    ids=["upper", "spaces", "zero-dose", "decimal"],
)
def test_spelling_differences_do_not_count_as_changes(variant):
    assert [change.kind for change in diff([RAMIPRIL], [variant])] == ["unchanged"]


def test_a_change_carries_before_and_after():
    proposed = Med(name="Ramipril", strength="10 mg", dosage={"morgens": "1"})
    current = Med(name="Ramipril", strength="5 mg", dosage={"morgens": "1"}, id="m-1")
    (change,) = diff([current], [proposed])
    assert (change.before, change.after, change.medication_id) == (current, proposed, "m-1")


def test_the_hash_changes_with_the_result_but_not_with_spelling():
    first = diff_hash(diff([RAMIPRIL], [RAMIPRIL]))
    assert first == diff_hash(
        diff([RAMIPRIL], [Med(name="ramipril", strength="5mg", dosage={"morgens": "1"})])
    )
    assert first != diff_hash(diff([RAMIPRIL], []))
    assert first != diff_hash(diff([RAMIPRIL, METFORMIN], [RAMIPRIL, METFORMIN]))


@pytest.mark.parametrize(
    ("a", "b"), [("0,50 mg", "0.5 mg"), ("2,5 mg", "2.50mg"), ("10 mg", "10.0 mg")]
)
def test_trailing_zeros_of_numbers_do_not_count(a, b):
    assert [c.kind for c in diff([Med("X", a)], [Med("X", b)])] == ["unchanged"]


def test_different_numbers_stay_different():
    assert [c.kind for c in diff([Med("X", "0,5 mg")], [Med("X", "5 mg")])] == ["changed"]


# Codex review Phase 3 #5 / decision 2A: the hint ("bei Bedarf") is part of the medication.
def test_a_changed_hint_alone_is_a_change() -> None:
    before = Med(name="Metamizol", strength="500 mg", dosage={"morgens": "1"})
    after = Med(name="Metamizol", strength="500 mg", dosage={"morgens": "1"}, hint="bei Bedarf")
    assert kinds([before], [after]) == [("changed", "Metamizol")]
    assert diff_hash(diff([before], [after])) != diff_hash(diff([before], [before]))


def test_a_hint_in_another_spelling_is_no_change() -> None:
    before = Med(name="Metamizol", strength="500 mg", dosage={"morgens": "1"}, hint="bei Bedarf")
    after = Med(name="Metamizol", strength="500 mg", dosage={"morgens": "1"}, hint=" Bei  bedarf ")
    assert kinds([before], [after]) == [("unchanged", "Metamizol")]
