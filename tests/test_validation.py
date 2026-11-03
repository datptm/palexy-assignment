"""Scheduling-specific shift validation without changing the generic time helper."""

import pytest

from src.domain.periods import shift_hours
from tests.scheduling_support import require_symbol


def test_scheduling_shift_accepts_operating_bounds_and_adjacent_hours() -> None:
    validate_shift_range = require_symbol("src.domain.shifts", "validate_shift_range")

    assert validate_shift_range(7, 15) == (7, 15)
    assert validate_shift_range(15, 23) == (15, 23)
    assert shift_hours(0, 1) == (0,)


@pytest.mark.parametrize("start,end", [(6, 15), (7, 24), (7, 7), (True, 15), (7.5, 15)])
def test_scheduling_shift_rejects_outside_or_noninteger_hours(start, end) -> None:
    validate_shift_range = require_symbol("src.domain.shifts", "validate_shift_range")
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        validate_shift_range(start, end)

    assert failure.value.code == "INVALID_SHIFT_RANGE"
