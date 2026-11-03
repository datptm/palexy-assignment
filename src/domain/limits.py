"""Strict bounded values at scheduling boundaries."""

from src.model.scheduling import SchedulingError

MAX_INTEGER = 2**31 - 1


def bounded_int(value: object, *, field: str, minimum: int = 0) -> int:
    """Return a bounded whole number, rejecting coercion and booleans."""
    if type(value) is not int or not minimum <= value <= MAX_INTEGER:
        raise SchedulingError(
            "INVALID_INTEGER",
            f"{field} must be a whole number from {minimum} to {MAX_INTEGER}",
            {"field": field, "minimum": minimum, "maximum": MAX_INTEGER},
        )
    return value


def checked_total(value: int, *, field: str) -> int:
    """Reject an integer aggregate that cannot fit the public contract."""
    if not 0 <= value <= MAX_INTEGER:
        raise SchedulingError(
            "INTEGER_OVERFLOW", f"{field} exceeds the integer limit", {"field": field}
        )
    return value


def bounded_name(value: object, *, field: str) -> str:
    """Trim a nonblank human name of at most 100 characters."""
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 100:
        raise SchedulingError(
            "INVALID_NAME", f"{field} must contain 1 to 100 characters", {"field": field}
        )
    return value.strip()
