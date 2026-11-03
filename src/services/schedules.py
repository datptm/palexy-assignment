"""Schedule use cases for future UI actions."""

from pathlib import Path

from src.db.database import DEFAULT_DATABASE_PATH, connect_database, initialize_database
from src.db.schedules import insert_schedule, select_schedules
from src.domain.schedules import normalize_schedule_name
from src.model.schedule import Schedule


class ScheduleService:
    """Coordinate schedule validation and SQLite persistence."""

    def __init__(self, database_path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = database_path

    def create_schedule(self, name: str) -> Schedule:
        """Validate and persist a new schedule."""
        normalized_name = normalize_schedule_name(name)
        with connect_database(self.database_path) as connection:
            initialize_database(connection)
            return insert_schedule(connection, normalized_name)

    def list_schedules(self) -> list[Schedule]:
        """Return schedules available to the application."""
        with connect_database(self.database_path) as connection:
            initialize_database(connection)
            return select_schedules(connection)
