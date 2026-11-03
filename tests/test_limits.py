"""Strict numeric boundary tests for scheduling values."""

import pytest

from tests.scheduling_support import require_symbol


def test_nonnegative_integer_accepts_zero_and_ceiling_exactly() -> None:
    bounded_int = require_symbol("src.domain.limits", "bounded_int")

    assert bounded_int(0, field="weekly_max_hours", minimum=0) == 0
    assert bounded_int(2**31 - 1, field="weekly_max_hours", minimum=0) == 2**31 - 1


@pytest.mark.parametrize("value", [True, 1.5, "1", -1, float("nan"), float("inf"), 2**31])
def test_nonnegative_integer_rejects_invalid_types_and_range(value: object) -> None:
    bounded_int = require_symbol("src.domain.limits", "bounded_int")
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        bounded_int(value, field="weekly_max_hours", minimum=0)

    assert failure.value.code == "INVALID_INTEGER"
    assert failure.value.details["field"] == "weekly_max_hours"


def test_positive_threshold_rejects_zero_without_float_rounding() -> None:
    required_staff = require_symbol("src.domain.demand", "required_staff")
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    assert [required_staff(count, 20) for count in (0, 20, 21, 48, 64)] == [1, 1, 2, 3, 4]
    assert required_staff(2**31 - 1, 2**31 - 1) == 1
    with pytest.raises(SchedulingError) as failure:
        required_staff(1, 0)
    assert failure.value.code == "INVALID_INTEGER"
