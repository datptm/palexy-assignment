"""Import boundary and complete-week normalization tests."""

from pathlib import Path

import pytest

from tests.scheduling_support import demand_map, require_symbol, week_csv


def _parse(report: bytes):
    parser = require_symbol("src.domain.csv_import", "parse_transactions_csv")
    return parser(report)


def _error(report: bytes):
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")
    with pytest.raises(SchedulingError) as failure:
        _parse(report)
    return failure.value


def test_complete_zero_report_is_available_demand_with_112_cells() -> None:
    result = _parse(week_csv())

    assert len(result.cells) == 112
    assert demand_map(result.cells) == {(day, hour): 0 for day in range(7) for hour in range(7, 23)}


def test_friday_first_date_headers_normalize_to_monday_first() -> None:
    order = (
        "Fri, 07 Aug",
        "Sat, 08 Aug",
        "Sun, 09 Aug",
        "Mon, 10 Aug",
        "Tue, 11 Aug",
        "Wed, 12 Aug",
        "Thu, 13 Aug",
    )
    values = {(order[0], 7): 22, (order[3], 7): 12}

    result = _parse(week_csv(day_order=order, values=values, title=True))

    assert len(result.cells) == 112
    assert demand_map(result.cells)[(4, 7)] == 22
    assert demand_map(result.cells)[(0, 7)] == 12
    assert any(finding.severity == "warning" and finding.row == 1 for finding in result.findings)


def test_supplied_report_friday_7am_count_normalizes_to_friday() -> None:
    report = Path("data/sample_transaction_interview.csv").read_bytes()

    result = _parse(report)

    assert len(result.cells) == 112
    assert demand_map(result.cells)[(4, 7)] == 22


def test_recognized_totals_are_ignored_with_positioned_warnings() -> None:
    result = _parse(week_csv(total=True))

    assert len(result.cells) == 112
    assert sum(cell.transactions for cell in result.cells) == 0
    assert len(result.findings) >= 2
    assert all(
        finding.severity == "warning" and finding.row is not None for finding in result.findings
    )


def test_multiple_bad_cells_report_all_discoverable_positions() -> None:
    values = {
        ("Monday", 7): "",
        ("Tuesday", 8): "-1",
        ("Wednesday", 9): "1.5",
        ("Thursday", 10): "text",
    }

    error = _error(week_csv(values=values))

    positions = {(item.day, item.hour) for item in error.findings if item.severity == "error"}
    assert positions == {(0, 7), (1, 8), (2, 9), (3, 10)}
    assert all(item.row is not None and item.column is not None for item in error.findings)


def test_duplicate_normalized_weekday_is_rejected() -> None:
    error = _error(week_csv(day_order=("Mon", "Monday", "Wed", "Thu", "Fri", "Sat", "Sun")))

    assert any(
        item.code == "DUPLICATE_WEEKDAY" and item.column is not None for item in error.findings
    )


@pytest.mark.parametrize(
    "report,expected_code",
    [
        (b"x" * (1024 * 1024 + 1), "RESOURCE_LIMIT"),
        (b"\xff", "INVALID_ENCODING"),
        (b"", "INVALID_CSV"),
    ],
)
def test_bad_or_oversized_input_has_distinct_error(report: bytes, expected_code: str) -> None:
    error = _error(report)

    assert error.code == expected_code


def test_weekly_transaction_total_overflow_is_rejected() -> None:
    report = week_csv(values={("Monday", 7): 2**31 - 1, ("Monday", 8): 1})

    error = _error(report)

    assert error.code == "INTEGER_OVERFLOW"
    assert any(item.code == "INTEGER_OVERFLOW" for item in error.findings)


@pytest.mark.parametrize(
    "report",
    [
        week_csv() + b"\n" * 240,
        b",".join([b"Hour"] + [b"Monday"] * 32) + b"\n",
        b"Hour,Monday\n07:00," + b"1" * 4097,
    ],
)
def test_csv_shape_caps_reject_rows_columns_and_long_cells(report: bytes) -> None:
    error = _error(report)

    assert error.code == "RESOURCE_LIMIT"


@pytest.mark.parametrize(
    "old,new,expected_code",
    [
        (b"07:00", b"06:00", "INVALID_HOUR"),
        (b"08:00", b"07:00", "DUPLICATE_HOUR"),
    ],
)
def test_unknown_or_duplicate_hour_is_rejected(old: bytes, new: bytes, expected_code: str) -> None:
    error = _error(week_csv().replace(old, new, 1))

    assert any(item.code == expected_code and item.row is not None for item in error.findings)
