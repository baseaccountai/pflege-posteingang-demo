"""F10-AC5: the reset runs at 03:00 German time all year. GitHub's cron knows only UTC, so
the workflow starts at 01:00 and 02:00 UTC and this check lets only the right one through.
"""

from datetime import UTC, datetime

import pytest

from scripts.reset_demo import reset_due


@pytest.mark.parametrize(
    ("utc", "due"),
    [
        (datetime(2026, 7, 1, 1, 0, tzinfo=UTC), True),  # summer: 01:00 UTC = 03:00 CEST
        (datetime(2026, 7, 1, 2, 0, tzinfo=UTC), False),  # summer: 04:00 CEST
        (datetime(2026, 11, 5, 2, 0, tzinfo=UTC), True),  # winter: 02:00 UTC = 03:00 CET
        (datetime(2026, 11, 5, 1, 0, tzinfo=UTC), False),  # winter: 02:00 CET
        (datetime(2026, 11, 5, 2, 29, tzinfo=UTC), True),  # scheduler 29 min late
        (datetime(2026, 10, 25, 2, 0, tzinfo=UTC), True),  # day the clocks go back
        (datetime(2026, 3, 29, 1, 0, tzinfo=UTC), True),  # day the clocks go forward
    ],
)
def test_reset_is_due_only_at_three_in_berlin(utc, due):
    assert reset_due(utc) is due
