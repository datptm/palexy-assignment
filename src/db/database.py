"""SQLite connection lifecycle and schema setup."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "schedules.sqlite3"


@contextmanager
def connect_database(path: Path = DEFAULT_DATABASE_PATH) -> Generator[sqlite3.Connection]:
    """Open a SQLite database and commit or roll back as the scope exits."""
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create or migrate all schedule tables as one repeatable action."""
    connection.execute("SAVEPOINT schedule_schema")
    try:
        _apply_schema(connection)
        connection.execute("RELEASE SAVEPOINT schedule_schema")
    except Exception:
        connection.execute("ROLLBACK TO SAVEPOINT schedule_schema")
        connection.execute("RELEASE SAVEPOINT schedule_schema")
        raise


def _apply_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(schedules)")}
    for name, definition in (
        ("threshold", "INTEGER NOT NULL DEFAULT 20 CHECK(threshold BETWEEN 1 AND 2147483647)"),
        (
            "daily_shift_limit",
            "INTEGER NOT NULL DEFAULT 1 CHECK(daily_shift_limit BETWEEN 1 AND 2147483647)",
        ),
        ("version", "INTEGER NOT NULL DEFAULT 0 CHECK(version BETWEEN 0 AND 2147483647)"),
    ):
        if name not in columns:
            connection.execute(f"ALTER TABLE schedules ADD COLUMN {name} {definition}")
    schema = """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY, schedule_id INTEGER NOT NULL,
            name TEXT NOT NULL, weekly_max_hours INTEGER NOT NULL CHECK(weekly_max_hours BETWEEN 0 AND 2147483647),
            UNIQUE(schedule_id,id), FOREIGN KEY(schedule_id) REFERENCES schedules(id)
        );
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY, schedule_id INTEGER NOT NULL,
            start_hour INTEGER NOT NULL CHECK(start_hour BETWEEN 7 AND 22),
            end_hour INTEGER NOT NULL CHECK(end_hour BETWEEN 8 AND 23 AND start_hour < end_hour),
            UNIQUE(schedule_id,id), UNIQUE(schedule_id,start_hour,end_hour),
            FOREIGN KEY(schedule_id) REFERENCES schedules(id)
        );
        CREATE TABLE IF NOT EXISTS demand_cells (
            schedule_id INTEGER NOT NULL, day INTEGER NOT NULL CHECK(day BETWEEN 0 AND 6),
            hour INTEGER NOT NULL CHECK(hour BETWEEN 7 AND 22),
            transactions INTEGER NOT NULL CHECK(transactions BETWEEN 0 AND 2147483647),
            PRIMARY KEY(schedule_id,day,hour), FOREIGN KEY(schedule_id) REFERENCES schedules(id)
        );
        CREATE TABLE IF NOT EXISTS demand_import_warnings (
            schedule_id INTEGER NOT NULL, sequence INTEGER NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(schedule_id,sequence), FOREIGN KEY(schedule_id) REFERENCES schedules(id)
        );
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY, schedule_id INTEGER NOT NULL, employee_id INTEGER NOT NULL,
            day INTEGER NOT NULL CHECK(day BETWEEN 0 AND 6), shift_id INTEGER NOT NULL,
            UNIQUE(schedule_id,employee_id,day,shift_id),
            FOREIGN KEY(schedule_id) REFERENCES schedules(id),
            FOREIGN KEY(schedule_id,employee_id) REFERENCES employees(schedule_id,id),
            FOREIGN KEY(schedule_id,shift_id) REFERENCES shifts(schedule_id,id)
        );
        CREATE TABLE IF NOT EXISTS history_snapshots (
            id INTEGER PRIMARY KEY, schedule_id INTEGER NOT NULL,
            captured_at_utc TEXT NOT NULL, reason TEXT NOT NULL,
            prior_version INTEGER NOT NULL, payload TEXT NOT NULL,
            FOREIGN KEY(schedule_id) REFERENCES schedules(id)
        );
        CREATE INDEX IF NOT EXISTS idx_history_schedule ON history_snapshots(schedule_id,id);
        CREATE TABLE IF NOT EXISTS initialized_schedules (
            schedule_id INTEGER PRIMARY KEY, FOREIGN KEY(schedule_id) REFERENCES schedules(id)
        );
        """
    for statement in schema.split(";"):
        if statement.strip():
            connection.execute(statement)
    from src.domain.limits import MAX_INTEGER, checked_total
    from src.model.scheduling import SchedulingError

    for (schedule_id,) in connection.execute("SELECT id FROM schedules"):
        if schedule_id > MAX_INTEGER:
            raise SchedulingError("INTEGER_OVERFLOW", "legacy schedule ID exceeds limit")
        exists = connection.execute(
            "SELECT 1 FROM initialized_schedules WHERE schedule_id=?", (schedule_id,)
        ).fetchone()
        if not exists:
            existing = set(
                connection.execute(
                    "SELECT start_hour,end_hour FROM shifts WHERE schedule_id=?", (schedule_id,)
                )
            )
            for start, end in ((7, 15), (15, 23)):
                if (start, end) not in existing:
                    cursor = connection.execute(
                        "INSERT INTO shifts(schedule_id,start_hour,end_hour) VALUES(?,?,?)",
                        (schedule_id, start, end),
                    )
                    checked_total(cursor.lastrowid, field="shift_id")
            connection.execute(
                "INSERT INTO initialized_schedules(schedule_id) VALUES(?)", (schedule_id,)
            )
