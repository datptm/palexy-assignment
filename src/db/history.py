"""Versioned, schedule-scoped historical snapshots."""

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone

from src.domain.demand import validate_demand
from src.domain.limits import bounded_int, checked_total
from src.domain.shifts import validate_shift_range
from src.domain.validation import validate_state
from src.model.scheduling import (
    Assignment,
    DemandCell,
    Employee,
    EmployeeMetric,
    HistoricalSnapshot,
    HourlyMetric,
    ScheduleResult,
    ScheduleState,
    SchedulingError,
    ShiftDefinition,
    SnapshotSummary,
    Violation,
    WeeklyMetric,
)


def append_snapshot(connection: sqlite3.Connection, result: ScheduleResult, reason: str) -> int:
    """Capture a prior state and analytics as canonical versioned JSON."""
    captured = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(
        {
            "schema_version": 1,
            "state": asdict(result.state),
            "hourly": [asdict(item) for item in result.hourly],
            "weekly": asdict(result.weekly),
            "employees": [asdict(item) for item in result.employees],
            "warnings": [asdict(item) for item in result.warnings],
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    cursor = connection.execute(
        "INSERT INTO history_snapshots(schedule_id,captured_at_utc,reason,prior_version,payload) VALUES(?,?,?,?,?)",
        (result.state.id, captured, reason, result.state.version, payload),
    )
    return checked_total(cursor.lastrowid, field="snapshot_id")


def list_snapshots(connection: sqlite3.Connection, schedule_id: int) -> list[SnapshotSummary]:
    """List immutable snapshots for one schedule."""
    return [
        SnapshotSummary(*row)
        for row in connection.execute(
            "SELECT id,schedule_id,captured_at_utc,reason,prior_version FROM history_snapshots WHERE schedule_id=? ORDER BY id",
            (schedule_id,),
        )
    ]


def get_snapshot(
    connection: sqlite3.Connection, schedule_id: int, snapshot_id: int
) -> HistoricalSnapshot:
    """Read and structurally validate a stored snapshot."""
    row = connection.execute(
        "SELECT id,schedule_id,captured_at_utc,reason,payload FROM history_snapshots WHERE id=? AND schedule_id=?",
        (snapshot_id, schedule_id),
    ).fetchone()
    if row is None:
        raise SchedulingError("UNKNOWN_REFERENCE", "snapshot does not exist in this schedule")
    try:
        payload = json.loads(row[4])
        if payload["schema_version"] != 1:
            raise ValueError("unknown snapshot schema")
        raw = payload["state"]
        state = ScheduleState(
            raw["id"],
            raw["name"],
            raw["version"],
            raw["threshold"],
            raw["daily_shift_limit"],
            tuple(Employee(**item) for item in raw["employees"]),
            tuple(ShiftDefinition(**item) for item in raw["shifts"]),
            None if raw["demand"] is None else tuple(DemandCell(**item) for item in raw["demand"]),
            tuple(Assignment(**item) for item in raw["assignments"]),
            tuple(Violation(**item) for item in raw["import_warnings"]),
        )
        if state.id != schedule_id:
            raise ValueError("snapshot schedule mismatch")
        bounded_int(state.id, field="schedule_id", minimum=1)
        bounded_int(state.version, field="version")
        bounded_int(state.threshold, field="threshold", minimum=1)
        bounded_int(state.daily_shift_limit, field="daily_shift_limit", minimum=1)
        if not isinstance(state.name, str) or not 1 <= len(state.name.strip()) <= 100:
            raise ValueError("invalid snapshot name")
        for employee in state.employees:
            bounded_int(employee.id, field="employee_id", minimum=1)
            bounded_int(employee.weekly_max_hours, field="weekly_max_hours")
            if not isinstance(employee.name, str) or not 1 <= len(employee.name.strip()) <= 100:
                raise ValueError("invalid employee name")
        for shift in state.shifts:
            bounded_int(shift.id, field="shift_id", minimum=1)
            validate_shift_range(shift.start_hour, shift.end_hour)
        if state.demand is not None:
            validate_demand(state.demand, state.threshold)
        if any(item.severity == "error" for item in validate_state(state)):
            raise ValueError("invalid snapshot assignments")
        hourly = tuple(HourlyMetric(**item) for item in payload["hourly"])
        weekly = WeeklyMetric(**payload["weekly"])
        employees = tuple(EmployeeMetric(**item) for item in payload["employees"])
        warnings = tuple(Violation(**item) for item in payload["warnings"])
        if len(hourly) != 112:
            raise ValueError("invalid hourly metric count")
        if {(item.day, item.hour) for item in hourly} != {
            (day, hour) for day in range(7) for hour in range(7, 23)
        }:
            raise ValueError("invalid hourly coordinates")
        if len(employees) != len(state.employees):
            raise ValueError("invalid employee metric count")
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise SchedulingError("INVALID_SNAPSHOT", "snapshot payload is malformed") from error
    return HistoricalSnapshot(
        row[0], row[1], row[2], row[3], state, hourly, weekly, employees, warnings
    )
