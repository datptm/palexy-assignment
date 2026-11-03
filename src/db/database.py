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
    """Create the baseline schedule table if it does not yet exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
        """
    )
