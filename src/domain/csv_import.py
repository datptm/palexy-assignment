"""Bounded, positioned transaction report parsing."""

import csv
import io
import re

from src.domain.demand import validate_demand
from src.domain.limits import MAX_INTEGER
from src.domain.periods import WEEKDAYS
from src.model.scheduling import DemandCell, ParsedDemand, SchedulingError, Violation

_TOTALS = {"total", "sum", "grand total", "all"}
_DAY_NAMES = {name.lower(): index for index, name in enumerate(WEEKDAYS)}
_DAY_NAMES.update({name[:3].lower(): index for index, name in enumerate(WEEKDAYS)})


def _weekday(label: str) -> int | None:
    match = re.match(r"^\s*([a-z]+)(?:\s*,.*)?\s*$", label.lower())
    return _DAY_NAMES.get(match.group(1)) if match else None


def _hour(label: str) -> int | None:
    label = label.strip().lower().replace(" ", "")
    match = re.fullmatch(r"(\d{1,2})(am|pm)", label)
    if match:
        value = int(match.group(1))
        if not 1 <= value <= 12:
            return None
        return value % 12 + (12 if match.group(2) == "pm" else 0)
    match = re.fullmatch(r"(\d{1,2}):00", label)
    return int(match.group(1)) if match else None


def _finding(
    code: str,
    severity: str,
    message: str,
    row: int,
    column: int,
    day: int | None = None,
    hour: int | None = None,
) -> Violation:
    return Violation(code, severity, message, {}, row, column, day, hour)


def parse_transactions_csv(report: bytes) -> ParsedDemand:
    """Normalize a complete seven-day hourly report or raise with all findings."""
    if not isinstance(report, bytes):
        raise SchedulingError("INVALID_CSV", "CSV input must be bytes")
    if len(report) > 1024 * 1024:
        raise SchedulingError("RESOURCE_LIMIT", "CSV exceeds 1 MiB")
    try:
        decoded = report.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise SchedulingError("INVALID_ENCODING", "CSV must be UTF-8") from error
    try:
        rows = list(csv.reader(io.StringIO(decoded, newline=""), strict=True))
    except csv.Error as error:
        raise SchedulingError("INVALID_CSV", "CSV is malformed") from error
    if not rows:
        raise SchedulingError("INVALID_CSV", "CSV is empty")
    if len(rows) > 256 or any(
        len(row) > 32 or any(len(cell) > 4096 for cell in row) for row in rows
    ):
        raise SchedulingError("RESOURCE_LIMIT", "CSV shape exceeds accepted limits")

    findings: list[Violation] = []
    header_index = None
    for row_index, row in enumerate(rows):
        days = [_weekday(cell) for cell in row[1:]]
        if len(row) >= 2 and any(day is not None for day in days):
            header_index = row_index
            break
        findings.append(
            _finding("IGNORED_TITLE", "warning", "ignored title or empty row", row_index + 1, 1)
        )
    if header_index is None:
        raise SchedulingError("INVALID_CSV", "weekday header is missing", findings=tuple(findings))

    columns: dict[int, int] = {}
    seen_days: set[int] = set()
    header = rows[header_index]
    for column, label in enumerate(header[1:], start=2):
        day = _weekday(label)
        if day is not None:
            if day in seen_days:
                findings.append(
                    _finding(
                        "DUPLICATE_WEEKDAY",
                        "error",
                        "repeated weekday",
                        header_index + 1,
                        column,
                        day,
                    )
                )
            else:
                seen_days.add(day)
                columns[column - 1] = day
        elif label.strip().lower() in _TOTALS or not label.strip():
            findings.append(
                _finding(
                    "IGNORED_COLUMN",
                    "warning",
                    "ignored total or empty column",
                    header_index + 1,
                    column,
                )
            )
        else:
            findings.append(
                _finding("INVALID_WEEKDAY", "error", "unknown weekday", header_index + 1, column)
            )
    if seen_days != set(range(7)):
        findings.append(
            _finding("MISSING_WEEKDAY", "error", "seven weekdays required", header_index + 1, 1)
        )

    cells: dict[tuple[int, int], DemandCell] = {}
    seen_hours: set[int] = set()
    for row_index, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(cell.strip() for cell in row):
            findings.append(_finding("IGNORED_ROW", "warning", "ignored empty row", row_index, 1))
            continue
        label = row[0].strip().lower() if row else ""
        if label in _TOTALS:
            findings.append(_finding("IGNORED_ROW", "warning", "ignored total row", row_index, 1))
            continue
        hour = _hour(label)
        if hour is None or not 7 <= hour <= 22:
            findings.append(_finding("INVALID_HOUR", "error", "invalid hour", row_index, 1))
            continue
        if hour in seen_hours:
            findings.append(
                _finding("DUPLICATE_HOUR", "error", "repeated hour", row_index, 1, hour=hour)
            )
            continue
        seen_hours.add(hour)
        for column_index, day in columns.items():
            raw = row[column_index].strip() if column_index < len(row) else ""
            if not re.fullmatch(r"\d+", raw):
                findings.append(
                    _finding(
                        "INVALID_COUNT",
                        "error",
                        "invalid transaction count",
                        row_index,
                        column_index + 1,
                        day,
                        hour,
                    )
                )
                continue
            count = int(raw)
            if count > MAX_INTEGER:
                findings.append(
                    _finding(
                        "INVALID_COUNT",
                        "error",
                        "transaction count exceeds limit",
                        row_index,
                        column_index + 1,
                        day,
                        hour,
                    )
                )
                continue
            cells[(day, hour)] = DemandCell(day, hour, count)
        for column_index in range(1, len(row)):
            if (
                column_index not in columns
                and column_index >= len(header)
                and row[column_index].strip()
            ):
                findings.append(
                    _finding(
                        "UNEXPECTED_COLUMN", "error", "unexpected data", row_index, column_index + 1
                    )
                )
    missing = {(day, hour) for day in range(7) for hour in range(7, 23)} - cells.keys()
    if missing and not any(item.code == "INVALID_COUNT" for item in findings):
        for day, hour in sorted(missing):
            findings.append(
                _finding(
                    "MISSING_CELL", "error", "missing demand cell", header_index + 1, 1, day, hour
                )
            )
    errors = tuple(item for item in findings if item.severity == "error")
    if errors:
        raise SchedulingError(
            "INVALID_CSV", "CSV contains invalid demand", findings=tuple(findings)
        )
    ordered = tuple(cells[(day, hour)] for day in range(7) for hour in range(7, 23))
    try:
        validate_demand(ordered, 20)
    except SchedulingError as error:
        finding = Violation(error.code, "error", str(error))
        raise SchedulingError(
            error.code, str(error), findings=tuple(findings) + (finding,)
        ) from error
    return ParsedDemand(ordered, tuple(findings))
