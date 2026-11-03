"""Shared bounded paths and output for manual scheduling commands."""

import argparse
import re
import sys
from pathlib import Path

from src.model.scheduling import ScheduleResult, SchedulingError
from src.services.schedules import ScheduleService

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPOSITORY_ROOT / "data"
MAX_CSV_BYTES = 1024 * 1024


def add_database_option(parser: argparse.ArgumentParser) -> None:
    """Add a database filename constrained to the local data directory."""
    parser.add_argument(
        "--db-name",
        default="schedules.sqlite3",
        help="SQLite filename inside data/ (default: schedules.sqlite3)",
    )


def database_service(name: str, *, must_exist: bool = False) -> ScheduleService:
    """Open a named local database without permitting path traversal."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}\.sqlite3", name):
        raise ValueError("database name must be a simple .sqlite3 filename")
    base = DATA_DIR.resolve()
    path = (base / name).resolve()
    if not path.is_relative_to(base):
        raise ValueError("database must stay inside data/")
    if must_exist and not path.is_file():
        raise ValueError(f"database does not exist: {name}")
    return ScheduleService(path)


def read_csv(source: str) -> bytes:
    """Read at most 1 MiB from a regular CSV inside the data directory."""
    base = DATA_DIR.resolve()
    candidate = Path(source)
    if candidate.is_absolute():
        path = candidate.resolve()
    elif candidate.parts and candidate.parts[0] == "data":
        path = (REPOSITORY_ROOT / candidate).resolve()
    else:
        path = (base / candidate).resolve()
    if not path.is_relative_to(base):
        raise ValueError("CSV path must stay inside data/")
    if not path.is_file():
        raise ValueError(f"CSV does not exist: {source}")
    with path.open("rb") as report:
        content = report.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("CSV exceeds 1 MiB")
    return content


def print_summary(result: ScheduleResult) -> None:
    """Print the identifying and weekly measures of a schedule result."""
    state = result.state
    print(f"Schedule ID {state.id}: {state.name} (version {state.version})")
    print(
        f"Employees: {len(state.employees)}; shifts: {len(state.shifts)}; assignments: {len(state.assignments)}"
    )
    print(f"Demand: {'available (112 hours)' if state.demand is not None else 'unavailable'}")
    weekly = result.weekly
    if weekly.coverage_rate is not None:
        print(
            f"Coverage: {weekly.coverage_rate:.1%}; "
            f"scheduled: {weekly.scheduled_staff_hours}; "
            f"unmet: {weekly.unmet_staff_hours}; excess: {weekly.excess_staff_hours}"
        )
    for warning in result.warnings:
        print(f"Warning {warning.code}: {warning.message}")


def report_error(error: ValueError | OSError) -> int:
    """Report a safe error and optional CSV positions to standard error."""
    if isinstance(error, SchedulingError):
        print(f"{error.code}: {error}", file=sys.stderr)
        for finding in error.findings:
            if finding.severity == "error":
                print(
                    f"  {finding.code} at row {finding.row}, column {finding.column}, "
                    f"day {finding.day}, hour {finding.hour}",
                    file=sys.stderr,
                )
    else:
        print(f"Error: {error}", file=sys.stderr)
    return 2
