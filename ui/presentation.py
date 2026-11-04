"""Text formatting for committed scheduling records."""

from src.domain.limits import MAX_INTEGER
from src.domain.periods import WEEKDAYS
from src.model.scheduling import SchedulingError, Violation


def hour_range(start: int, end: int) -> str:
    """Format a whole-hour shift in local 24-hour time."""
    return f"{start:02d}:00–{end:02d}:00"


def person_label(name: str, person_id: int) -> str:
    """Keep duplicate names distinguishable by a stable identifier."""
    return f"{name} #{person_id}"


def whole_number(value: object, field: str, *, minimum: int = 0) -> int:
    """Reject noninteger browser values before a service write."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise SchedulingError("INVALID_INTEGER", f"{field} must be a whole number")
    raw = str(value)
    if not raw.isdecimal() or len(raw) > 10:
        raise SchedulingError(
            "INVALID_INTEGER", f"{field} must be a whole number from {minimum} to {MAX_INTEGER}"
        )
    number = int(raw)
    if number < minimum or number > MAX_INTEGER:
        raise SchedulingError(
            "INVALID_INTEGER", f"{field} must be a whole number from {minimum} to {MAX_INTEGER}"
        )
    return number


def ratio(value: float | None) -> str:
    """Format an available ratio without rounding the service calculation early."""
    return "–" if value is None else f"{value:.2f}".rstrip("0").rstrip(".")


def finding_text(finding: Violation) -> str:
    """Show a structured finding with its available source location."""
    parts = [finding.severity, finding.code, finding.message]
    if finding.row is not None:
        parts.append(f"row {finding.row}")
    if finding.column is not None:
        parts.append(f"column {finding.column}")
    if finding.day is not None:
        parts.append(WEEKDAYS[finding.day])
    if finding.hour is not None:
        parts.append(f"{finding.hour:02d}:00")
    if finding.details:
        parts.append(", ".join(f"{key}: {value}" for key, value in finding.details.items()))
    return " · ".join(parts)
