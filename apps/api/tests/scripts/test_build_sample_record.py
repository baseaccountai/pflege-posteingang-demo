"""F10-AC14: the static sample record is the API's record of a seeded resident, turned into
plain JSON. Times that the seed sets relative to "now" become calendar days, so the web page
can move them to today; dates printed in the documents stay as they are."""

from datetime import UTC, date, datetime

from scripts.build_sample_record import shift_days, to_static

NOW = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)


def provenance(confirmed_at: datetime) -> dict:
    return {
        "document_id": "5eed0000-0000-0000-0000-000000000002",
        "doc_type": "arztbrief",
        "document_date": date(2026, 9, 3),
        "actor_type": "human",
        "confirmed_by_name": "Pflegekraft WB1",
        "confirmed_at": confirmed_at,
    }


def api_record() -> dict:
    late_evening = datetime(2026, 10, 25, 23, 30, tzinfo=UTC)  # already 26.10. in Berlin
    return {
        "resident": {"id": "r1", "display_name": "Fr. Beispiel"},
        "medications": {
            "active": [
                {
                    "id": "m1",
                    "name": "Metamizol",
                    "marker": "new",
                    "provenance": provenance(late_evening),
                    "events": [
                        {
                            "kind": "new",
                            "created_at": late_evening,
                            "provenance": provenance(late_evening),
                        }
                    ],
                }
            ],
            "discontinued": [{"id": "m2", "discontinued_at": late_evening, "events": []}],
        },
        "diagnoses": [{"id": "random-a", "text": "Osteoporose", "provenance": provenance(NOW)}],
        "follow_ups": [
            {"id": "random-b", "title": "NRS", "due_date": date(2026, 10, 26), "done_at": None},
            {"id": "random-c", "title": "Ortho", "due_date": None, "done_at": NOW},
        ],
        "documents": [
            {"id": "d1", "document_date": date(2026, 9, 3), "approved_at": NOW},
        ],
    }


def test_points_in_time_become_their_day_in_berlin() -> None:
    record = to_static(api_record())
    medication = record["medications"]["active"][0]
    assert medication["events"][0]["created_at"] == "2026-10-26"
    assert medication["provenance"]["confirmed_at"] == "2026-10-26"
    assert record["medications"]["discontinued"][0]["discontinued_at"] == "2026-10-26"
    assert record["follow_ups"][1]["done_at"] == "2026-10-28"
    assert record["documents"][0]["approved_at"] == "2026-10-28"


def test_calendar_dates_stay_and_nothing_else_changes() -> None:
    record = to_static(api_record())
    assert record["documents"][0]["document_date"] == "2026-09-03"
    assert record["follow_ups"][0]["due_date"] == "2026-10-26"
    assert record["follow_ups"][0]["done_at"] is None
    assert record["medications"]["active"][0]["marker"] == "new"
    assert record["resident"] == {"id": "r1", "display_name": "Fr. Beispiel"}


def test_random_seed_ids_are_replaced_by_stable_ones() -> None:
    # Diagnoses and follow-ups get gen_random_uuid() in the seed; the file must not change
    # with every run. Medication and document ids are fixed in the seed and stay.
    record = to_static(api_record())
    assert [d["id"] for d in record["diagnoses"]] == ["diagnosis-1"]
    assert [f["id"] for f in record["follow_ups"]] == ["follow-up-1", "follow-up-2"]
    assert record["medications"]["active"][0]["id"] == "m1"
    assert record["documents"][0]["id"] == "d1"


def test_shift_moves_relative_days_but_not_document_dates() -> None:
    shifted = shift_days(to_static(api_record()), 3)
    assert shifted["medications"]["active"][0]["events"][0]["created_at"] == "2026-10-29"
    assert shifted["medications"]["active"][0]["provenance"]["confirmed_at"] == "2026-10-29"
    assert shifted["follow_ups"][0]["due_date"] == "2026-10-29"
    assert shifted["follow_ups"][0]["done_at"] is None
    assert shifted["documents"][0]["approved_at"] == "2026-10-31"
    assert shifted["documents"][0]["document_date"] == "2026-09-03"
    assert shifted["medications"]["active"][0]["provenance"]["document_date"] == "2026-09-03"


def test_times_inside_provenance_json_become_days_too() -> None:
    # PROVENANCE is built with jsonb in SQL, so its times arrive as ISO text, not datetime.
    record = api_record()
    record["diagnoses"][0]["provenance"]["confirmed_at"] = "2026-10-25T23:30:00.123+00:00"
    static = to_static(record)
    assert static["diagnoses"][0]["provenance"]["confirmed_at"] == "2026-10-26"


def test_diagnoses_of_the_same_day_are_ordered_by_text() -> None:
    # The seed confirms several diagnoses at the same now(); the API then orders them by
    # their random id, which would change the file with every run.
    record = api_record()
    record["diagnoses"] = [
        {"id": "x", "text": "Osteoporose", "provenance": provenance(NOW)},
        {"id": "y", "text": "Gonarthrose beidseits", "provenance": provenance(NOW)},
        {"id": "z", "text": "Älter", "provenance": provenance(datetime(2026, 9, 1, tzinfo=UTC))},
    ]
    static = to_static(record)
    assert [d["text"] for d in static["diagnoses"]] == [
        "Älter",
        "Gonarthrose beidseits",
        "Osteoporose",
    ]
