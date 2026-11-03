"""Manual command-line tools against isolated SQLite files."""

import importlib

from src.services.schedules import ScheduleService
from tests.scheduling_support import week_csv


def _tool(name: str, monkeypatch, data_dir):
    common = importlib.import_module("scripts._common")
    monkeypatch.setattr(common, "DATA_DIR", data_dir)
    return importlib.import_module(f"scripts.{name}")


def test_schedule_commands_create_list_and_show_state(tmp_path, monkeypatch, capsys) -> None:
    """A manager can create a week and see its ID and default shifts."""
    tool = _tool("schedules", monkeypatch, tmp_path)

    assert tool.main(["--db-name", "manual.sqlite3", "create", "Shop week"]) == 0
    assert tool.main(["--db-name", "manual.sqlite3", "add-employee", "1", "Alex", "8"]) == 0
    assert tool.main(["--db-name", "manual.sqlite3", "list"]) == 0
    assert tool.main(["--db-name", "manual.sqlite3", "show", "1"]) == 0

    output = capsys.readouterr().out
    assert "Shop week" in output
    assert "ID 1" in output
    assert "07:00-15:00" in output
    assert "15:00-23:00" in output
    assert "Demand: unavailable" in output
    assert "Alex, 0/8 hours" in output


def test_import_command_previews_replacement_then_requires_flag_to_commit(
    tmp_path, monkeypatch, capsys
) -> None:
    """A second report stays read-only until explicit replacement is requested."""
    tool = _tool("import_csv", monkeypatch, tmp_path)
    service = ScheduleService(tmp_path / "manual.sqlite3")
    schedule_id = service.create_schedule("Shop week").id
    service.add_employee(schedule_id, "Alex", 8)
    (tmp_path / "first.csv").write_bytes(week_csv())
    (tmp_path / "replacement.csv").write_bytes(week_csv(values={("Monday", 7): 64}))

    assert tool.main(["--db-name", "manual.sqlite3", "1", "first.csv"]) == 0
    before = service.get_schedule(schedule_id)
    assert len(before.state.demand) == 112

    assert tool.main(["--db-name", "manual.sqlite3", "1", "replacement.csv"]) == 0
    assert service.get_schedule(schedule_id) == before
    assert service.list_snapshots(schedule_id) == []

    assert (
        tool.main(["--db-name", "manual.sqlite3", "1", "replacement.csv", "--confirm-replace"]) == 0
    )
    after = service.get_schedule(schedule_id)
    assert after.state.demand != before.state.demand
    assert len(service.list_snapshots(schedule_id)) == 1
    assert "Preview only" in capsys.readouterr().out


def test_generate_command_previews_nonempty_roster_without_writing(
    tmp_path, monkeypatch, capsys
) -> None:
    """Generation keeps a manual roster until the caller supplies confirmation."""
    tool = _tool("generate", monkeypatch, tmp_path)
    service = ScheduleService(tmp_path / "manual.sqlite3")
    schedule_id = service.create_schedule("Shop week").id
    service.add_employee(schedule_id, "Alex", 8)
    service.import_initial(schedule_id, week_csv())
    state = service.get_schedule(schedule_id).state
    service.add_assignment(schedule_id, state.employees[0].id, 6, state.shifts[1].id)
    before = service.get_schedule(schedule_id)

    assert tool.main(["--db-name", "manual.sqlite3", "1"]) == 0
    assert service.get_schedule(schedule_id) == before
    assert tool.main(["--db-name", "manual.sqlite3", "1", "--confirm-replace"]) == 0
    assert service.get_schedule(schedule_id).state.assignments != before.state.assignments
    assert "Preview only" in capsys.readouterr().out


def test_import_command_rejects_path_escape_and_oversized_file(
    tmp_path, monkeypatch, capsys
) -> None:
    """Import accepts only bounded files inside the allowed data directory."""
    tool = _tool("import_csv", monkeypatch, tmp_path)
    service = ScheduleService(tmp_path / "manual.sqlite3")
    schedule_id = service.create_schedule("Shop week").id
    (tmp_path / "large.csv").write_bytes(b"x" * (1024 * 1024 + 1))

    assert tool.main(["--db-name", "manual.sqlite3", "1", "../outside.csv"]) == 2
    assert tool.main(["--db-name", "manual.sqlite3", "1", "large.csv"]) == 2
    assert service.get_schedule(schedule_id).state.demand is None
    errors = capsys.readouterr().err
    assert "inside" in errors
    assert "1 MiB" in errors
