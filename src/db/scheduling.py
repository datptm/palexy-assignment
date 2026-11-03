"""Schedule-scoped persistence for weekly scheduling records."""

import json
import sqlite3
from dataclasses import asdict

from src.domain.limits import checked_total
from src.model.scheduling import (
    Assignment,
    DemandCell,
    Employee,
    ScheduleState,
    SchedulingError,
    ShiftDefinition,
    Violation,
)


def load_state(connection: sqlite3.Connection, schedule_id: int) -> ScheduleState:
    """Read one complete schedule by stable ID."""
    row = connection.execute(
        "SELECT id,name,version,threshold,daily_shift_limit FROM schedules WHERE id=?",
        (schedule_id,),
    ).fetchone()
    if row is None:
        raise SchedulingError(
            "UNKNOWN_REFERENCE", "schedule does not exist", {"schedule_id": schedule_id}
        )
    employees = tuple(
        Employee(*item)
        for item in connection.execute(
            "SELECT id,name,weekly_max_hours FROM employees WHERE schedule_id=? ORDER BY id",
            (schedule_id,),
        )
    )
    shifts = tuple(
        ShiftDefinition(*item)
        for item in connection.execute(
            "SELECT id,start_hour,end_hour FROM shifts WHERE schedule_id=? ORDER BY id",
            (schedule_id,),
        )
    )
    demand_rows = tuple(
        DemandCell(*item)
        for item in connection.execute(
            "SELECT day,hour,transactions FROM demand_cells WHERE schedule_id=? ORDER BY day,hour",
            (schedule_id,),
        )
    )
    assignments = tuple(
        Assignment(*item)
        for item in connection.execute(
            "SELECT id,employee_id,day,shift_id FROM assignments WHERE schedule_id=? ORDER BY id",
            (schedule_id,),
        )
    )
    warnings = tuple(
        Violation(**json.loads(item[0]))
        for item in connection.execute(
            "SELECT payload FROM demand_import_warnings WHERE schedule_id=? ORDER BY sequence",
            (schedule_id,),
        )
    )
    return ScheduleState(
        row[0],
        row[1],
        row[2],
        row[3],
        row[4],
        employees,
        shifts,
        demand_rows or None,
        assignments,
        warnings,
    )


def replace_demand(
    connection: sqlite3.Connection,
    schedule_id: int,
    cells: tuple[DemandCell, ...],
    findings: tuple[Violation, ...],
) -> None:
    """Replace all demand and accepted warnings inside the caller's transaction."""
    connection.execute("DELETE FROM demand_cells WHERE schedule_id=?", (schedule_id,))
    connection.execute("DELETE FROM demand_import_warnings WHERE schedule_id=?", (schedule_id,))
    connection.executemany(
        "INSERT INTO demand_cells(schedule_id,day,hour,transactions) VALUES(?,?,?,?)",
        ((schedule_id, cell.day, cell.hour, cell.transactions) for cell in cells),
    )
    connection.executemany(
        "INSERT INTO demand_import_warnings(schedule_id,sequence,payload) VALUES(?,?,?)",
        (
            (schedule_id, sequence, json.dumps(asdict(item), sort_keys=True))
            for sequence, item in enumerate(findings)
        ),
    )


def replace_assignments(
    connection: sqlite3.Connection, schedule_id: int, assignments: tuple[Assignment, ...]
) -> None:
    """Replace a roster under the caller's transaction."""
    connection.execute("DELETE FROM assignments WHERE schedule_id=?", (schedule_id,))
    for item in assignments:
        cursor = connection.execute(
            "INSERT INTO assignments(schedule_id,employee_id,day,shift_id) VALUES(?,?,?,?)",
            (schedule_id, item.employee_id, item.day, item.shift_id),
        )
        checked_total(cursor.lastrowid, field="assignment_id")


def insert_employee(
    connection: sqlite3.Connection, schedule_id: int, name: str, maximum: int
) -> int:
    """Insert one worker and return its SQLite ID."""
    return connection.execute(
        "INSERT INTO employees(schedule_id,name,weekly_max_hours) VALUES(?,?,?)",
        (schedule_id, name, maximum),
    ).lastrowid


def update_employee(
    connection: sqlite3.Connection, schedule_id: int, employee_id: int, name: str, maximum: int
) -> None:
    """Update a schedule-owned worker."""
    connection.execute(
        "UPDATE employees SET name=?,weekly_max_hours=? WHERE schedule_id=? AND id=?",
        (name, maximum, schedule_id, employee_id),
    )


def delete_employee(connection: sqlite3.Connection, schedule_id: int, employee_id: int) -> None:
    """Delete one worker and their assignments in the current transaction."""
    connection.execute(
        "DELETE FROM assignments WHERE schedule_id=? AND employee_id=?", (schedule_id, employee_id)
    )
    connection.execute(
        "DELETE FROM employees WHERE schedule_id=? AND id=?", (schedule_id, employee_id)
    )


def insert_shift(connection: sqlite3.Connection, schedule_id: int, start: int, end: int) -> int:
    """Insert one schedule-owned shift and return its ID."""
    return connection.execute(
        "INSERT INTO shifts(schedule_id,start_hour,end_hour) VALUES(?,?,?)",
        (schedule_id, start, end),
    ).lastrowid


def mark_defaults_initialized(connection: sqlite3.Connection, schedule_id: int) -> None:
    """Prevent removed defaults from being recreated on later schema checks."""
    connection.execute("INSERT INTO initialized_schedules(schedule_id) VALUES(?)", (schedule_id,))


def update_shift(
    connection: sqlite3.Connection, schedule_id: int, shift_id: int, start: int, end: int
) -> None:
    """Update one schedule-owned shift."""
    connection.execute(
        "UPDATE shifts SET start_hour=?,end_hour=? WHERE schedule_id=? AND id=?",
        (start, end, schedule_id, shift_id),
    )


def delete_shift(connection: sqlite3.Connection, schedule_id: int, shift_id: int) -> None:
    """Delete one shift and its assignments in the current transaction."""
    connection.execute(
        "DELETE FROM assignments WHERE schedule_id=? AND shift_id=?", (schedule_id, shift_id)
    )
    connection.execute("DELETE FROM shifts WHERE schedule_id=? AND id=?", (schedule_id, shift_id))


def insert_assignment(
    connection: sqlite3.Connection, schedule_id: int, employee_id: int, day: int, shift_id: int
) -> int:
    """Insert one schedule-owned assignment and return its ID."""
    return connection.execute(
        "INSERT INTO assignments(schedule_id,employee_id,day,shift_id) VALUES(?,?,?,?)",
        (schedule_id, employee_id, day, shift_id),
    ).lastrowid


def delete_assignment(connection: sqlite3.Connection, schedule_id: int, assignment_id: int) -> None:
    """Delete one schedule-owned assignment."""
    connection.execute(
        "DELETE FROM assignments WHERE schedule_id=? AND id=?", (schedule_id, assignment_id)
    )


def update_assignment(
    connection: sqlite3.Connection,
    schedule_id: int,
    assignment_id: int,
    employee_id: int,
    day: int,
    shift_id: int,
) -> None:
    """Move one assignment to another valid worker/day/shift."""
    connection.execute(
        "UPDATE assignments SET employee_id=?,day=?,shift_id=? WHERE schedule_id=? AND id=?",
        (employee_id, day, shift_id, schedule_id, assignment_id),
    )
