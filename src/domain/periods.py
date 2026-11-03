"""Time conventions shared by scheduling logic and the UI."""

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
DEFAULT_SHIFTS = ((7, 15), (15, 23))


def shift_hours(start_hour: int, end_hour: int) -> tuple[int, ...]:
    """Return the clock hours covered by a same-day shift.

    The end hour is exclusive. Hours use the 24-hour clock and may end at 24.

    Raises:
        ValueError: If the hours are outside one day or do not form a shift.
    """
    if (
        isinstance(start_hour, bool)
        or isinstance(end_hour, bool)
        or not isinstance(start_hour, int)
        or not isinstance(end_hour, int)
        or not 0 <= start_hour < end_hour <= 24
    ):
        raise ValueError("shift hours must be integers within one day, start before end")
    return tuple(range(start_hour, end_hour))
