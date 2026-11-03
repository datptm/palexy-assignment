"""Parameterized SQLite operations for schedules."""

import sqlite3

from src.model.schedule import Schedule


def insert_schedule(connection: sqlite3.Connection, name: str) -> Schedule:
    """Persist a validated schedule name and return the stored record."""
    cursor = connection.execute("INSERT INTO schedules (name) VALUES (?)", (name,))
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return a schedule ID")
    return Schedule(id=cursor.lastrowid, name=name)


def select_schedules(connection: sqlite3.Connection) -> list[Schedule]:
    """Return all schedules in creation order."""
    rows = connection.execute("SELECT id, name FROM schedules ORDER BY id").fetchall()
    return [Schedule(id=row[0], name=row[1]) for row in rows]


def update_name(connection: sqlite3.Connection, schedule_id: int, name: str) -> None:
    """Rename one schedule by ID."""
    connection.execute("UPDATE schedules SET name=? WHERE id=?", (name, schedule_id))


def update_setting(
    connection: sqlite3.Connection, schedule_id: int, field: str, value: int
) -> None:
    """Set one allowlisted schedule setting."""
    if field == "threshold":
        connection.execute("UPDATE schedules SET threshold=? WHERE id=?", (value, schedule_id))
    elif field == "daily_shift_limit":
        connection.execute(
            "UPDATE schedules SET daily_shift_limit=? WHERE id=?", (value, schedule_id)
        )
    else:
        raise ValueError("unknown schedule setting")


def increment_version(connection: sqlite3.Connection, schedule_id: int) -> bool:
    """Advance a version without crossing the integer ceiling."""
    cursor = connection.execute(
        "UPDATE schedules SET version=version+1 WHERE id=? AND version<2147483647",
        (schedule_id,),
    )
    return cursor.rowcount == 1
