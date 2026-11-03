"""Behavior tests for the service, domain, model, and SQLite boundary."""

import pytest

from src.db.database import connect_database, initialize_database
from src.model.schedule import Schedule
from src.services.schedules import ScheduleService


def test_created_schedule_is_persisted_and_returned_as_model(tmp_path):
    database_path = tmp_path / "schedules.sqlite3"
    service = ScheduleService(database_path)

    created = service.create_schedule("  Week A  ")
    schedules = ScheduleService(database_path).list_schedules()

    assert created == Schedule(id=1, name="Week A")
    assert schedules == [created]


@pytest.mark.parametrize("name", ["", "   ", "x" * 101, None])
def test_invalid_schedule_name_is_rejected_without_writing(tmp_path, name):
    service = ScheduleService(tmp_path / "schedules.sqlite3")

    with pytest.raises(ValueError, match="schedule name"):
        service.create_schedule(name)

    assert service.list_schedules() == []


def test_database_initialization_can_be_repeated(tmp_path):
    database_path = tmp_path / "schedules.sqlite3"
    service = ScheduleService(database_path)
    created = service.create_schedule("Week A")

    with connect_database(database_path) as connection:
        initialize_database(connection)
        initialize_database(connection)

    assert service.list_schedules() == [created]


def test_schedule_name_is_stored_as_data_not_sql(tmp_path):
    service = ScheduleService(tmp_path / "schedules.sqlite3")
    name = "Week'); DROP TABLE schedules; --"

    created = service.create_schedule(name)

    assert service.list_schedules() == [created]
