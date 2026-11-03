"""Opt-in local timing scenarios; elapsed time is reported, never asserted."""

import os
import platform
import time
from itertools import islice

import pytest

from src.domain.csv_import import parse_transactions_csv
from src.domain.generation import generate_draft
from src.domain.metrics import calculate_result
from src.model.scheduling import Employee, ScheduleState, ShiftDefinition
from src.services.schedules import ScheduleService
from tests.scheduling_support import week_csv

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SCHEDULING_BENCHMARKS") != "1", reason="local benchmark only"
)


def _report(label: str, start: float) -> None:
    print(
        f"{label}: {time.perf_counter() - start:.4f}s on {platform.platform()} / {platform.processor()}"
    )


def test_import_and_metrics_timing() -> None:
    """Measure bounded report parsing and a fresh analytics calculation."""
    report = week_csv()
    start = time.perf_counter()
    parsed = parse_transactions_csv(report)
    state = ScheduleState(
        1, "Benchmark", 0, 20, 1, (), (ShiftDefinition(1, 7, 15),), parsed.cells, ()
    )
    calculate_result(state)
    _report("import plus metrics (target under 1s)", start)


def test_pure_generation_100_employees_32_shifts_timing() -> None:
    """Measure the accepted large draft scenario without a CI timing gate."""
    parsed = parse_transactions_csv(week_csv())
    pairs = islice(((start, end) for start in range(7, 23) for end in range(start + 1, 24)), 32)
    shifts = tuple(
        ShiftDefinition(index + 1, start, end) for index, (start, end) in enumerate(pairs)
    )
    employees = tuple(Employee(index + 1, f"Worker {index + 1}", 8) for index in range(100))
    state = ScheduleState(1, "Benchmark", 0, 20, 1, employees, shifts, parsed.cells, ())
    start = time.perf_counter()
    generate_draft(state)
    _report("pure generation 100 employees/32 shifts (target under 10s)", start)


def test_confirmed_refresh_timing(tmp_path) -> None:
    """Measure confirmation including snapshot persistence separately."""
    service = ScheduleService(tmp_path / "benchmark.sqlite3")
    schedule_id = service.create_schedule("Benchmark").id
    service.add_employee(schedule_id, "Worker", 8)
    service.import_initial(schedule_id, week_csv())
    report = week_csv(values={("Monday", 7): 64})
    preview = service.preview_refresh(schedule_id, csv_bytes=report)
    start = time.perf_counter()
    service.confirm_refresh(schedule_id, preview.token, csv_bytes=report, confirmed=True)
    _report("confirmed refresh including snapshot", start)
