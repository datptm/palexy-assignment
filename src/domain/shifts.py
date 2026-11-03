"""Scheduling-specific shift constraints."""

from src.model.scheduling import SchedulingError


def validate_shift_range(start: object, end: object) -> tuple[int, int]:
    """Require a whole-hour shift inside the operating day."""
    if type(start) is not int or type(end) is not int or not 7 <= start < end <= 23:
        raise SchedulingError(
            "INVALID_SHIFT_RANGE",
            "shift must start and end on whole operating hours",
            {"start_hour": start, "end_hour": end},
        )
    return start, end


def overlaps(first_start: int, first_end: int, second_start: int, second_end: int) -> bool:
    """Whether two half-open shifts share operating time."""
    return first_start < second_end and second_start < first_end
