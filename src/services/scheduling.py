"""Shared service transaction and proposal validation helpers."""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from src.db.database import connect_database, initialize_database
from src.domain.limits import bounded_int
from src.domain.validation import validate_state
from src.model.scheduling import ScheduleState, SchedulingError, Violation


@contextmanager
def schedule_connection(path: Path, *, write: bool = False) -> Generator:
    """Initialize schema then optionally lock one atomic write action."""
    with connect_database(path) as connection:
        initialize_database(connection)
        if write:
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")
        yield connection


def valid_id(value: object, field: str) -> int:
    """Require a stable positive database identifier."""
    return bounded_int(value, field=field, minimum=1)


def checked_proposal(state: ScheduleState) -> tuple[Violation, ...]:
    """Reject hard errors in a proposed complete assignment state."""
    findings = validate_state(state)
    error = next((item for item in findings if item.severity == "error"), None)
    if error is not None:
        raise SchedulingError(error.code, error.message, error.details, findings)
    return findings


def with_assignment(state: ScheduleState, assignment) -> ScheduleState:
    """Return a state with one proposed assignment appended."""
    return replace(state, assignments=state.assignments + (assignment,))
