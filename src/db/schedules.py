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
