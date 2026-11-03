"""Tests for the weekly scheduling time boundary."""

import pytest

from src.domain.periods import shift_hours


def test_shift_covers_start_hour_but_not_end_hour() -> None:
    assert shift_hours(7, 15) == tuple(range(7, 15))


@pytest.mark.parametrize("start, end", [(7, 7), (15, 7), (-1, 8), (7, 25), (True, 8)])
def test_invalid_shift_hours_are_rejected(start: int, end: int) -> None:
    with pytest.raises(ValueError, match="shift hours"):
        shift_hours(start, end)
