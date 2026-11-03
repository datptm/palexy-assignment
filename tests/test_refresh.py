"""Read-only previews, version conflicts, and atomic historical refreshes."""

import sqlite3

import pytest

from src.db.database import connect_database
from src.services.schedules import ScheduleService
from tests.scheduling_support import require_method, require_symbol, week_csv


def _service(tmp_path):
    return ScheduleService(tmp_path / "schedules.sqlite3")


def _read(service, schedule_id):
    return require_method(service, "get_schedule")(schedule_id)


def _history(service, schedule_id):
    return require_method(service, "list_snapshots")(schedule_id)


def _prepared_schedule(tmp_path):
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    require_method(service, "add_employee")(schedule_id, "Alex", 8)
    require_method(service, "import_initial")(schedule_id, week_csv())
    state = _read(service, schedule_id).state
    require_method(service, "add_assignment")(
        schedule_id, state.employees[0].id, 6, state.shifts[1].id
    )
    return service, schedule_id


def test_refresh_preview_and_cancel_leave_active_state_and_history_unchanged(tmp_path) -> None:
    service, schedule_id = _prepared_schedule(tmp_path)
    before = _read(service, schedule_id)
    replacement = week_csv(values={("Monday", 7): 64})

    preview = require_method(service, "preview_refresh")(schedule_id, csv_bytes=replacement)
    cancelled = require_method(service, "confirm_refresh")(
        schedule_id, preview.token, csv_bytes=replacement, confirmed=False
    )

    assert preview.baseline_version == before.state.version
    assert preview.draft.state.demand is not None
    assert cancelled is None
    assert _read(_service(tmp_path), schedule_id) == before
    assert _history(_service(tmp_path), schedule_id) == []


def test_confirmed_refresh_captures_prior_analytics_and_replaces_roster_once(tmp_path) -> None:
    service, schedule_id = _prepared_schedule(tmp_path)
    before = _read(service, schedule_id)
    replacement = week_csv(values={("Monday", 7): 64})
    preview = require_method(service, "preview_refresh")(schedule_id, csv_bytes=replacement)

    committed = require_method(service, "confirm_refresh")(
        schedule_id, preview.token, csv_bytes=replacement, confirmed=True
    )
    reopened = _read(_service(tmp_path), schedule_id)
    history = _history(_service(tmp_path), schedule_id)
    snapshot = require_method(_service(tmp_path), "get_snapshot")(schedule_id, history[0].id)

    assert len(history) == 1
    assert snapshot.state == before.state
    assert snapshot.weekly == before.weekly
    assert snapshot.hourly == before.hourly
    assert snapshot.reason == "DEMAND_REIMPORT"
    assert reopened == committed
    assert reopened.state.version == before.state.version + 1
    assert reopened.state.demand != before.state.demand
    assert reopened.state.assignments != before.state.assignments
    assert reopened.weekly == preview.draft.weekly


def test_stale_preview_after_intervening_edit_rejects_without_snapshot(tmp_path) -> None:
    service, schedule_id = _prepared_schedule(tmp_path)
    replacement = week_csv(values={("Monday", 7): 64})
    preview = require_method(service, "preview_refresh")(schedule_id, csv_bytes=replacement)
    require_method(_service(tmp_path), "rename_schedule")(schedule_id, "Changed")
    after_edit = _read(_service(tmp_path), schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "confirm_refresh")(
            schedule_id, preview.token, csv_bytes=replacement, confirmed=True
        )

    assert failure.value.code == "STALE_PREVIEW"
    assert _read(_service(tmp_path), schedule_id) == after_edit
    assert _history(_service(tmp_path), schedule_id) == []


def test_confirmed_threshold_change_snapshots_prior_settings_and_reuses_demand(tmp_path) -> None:
    service, schedule_id = _prepared_schedule(tmp_path)
    before = _read(service, schedule_id)
    preview = require_method(service, "preview_refresh")(schedule_id, threshold=10)

    committed = require_method(service, "confirm_refresh")(
        schedule_id, preview.token, threshold=10, confirmed=True
    )
    history = _history(_service(tmp_path), schedule_id)
    snapshot = require_method(_service(tmp_path), "get_snapshot")(schedule_id, history[0].id)

    assert len(history) == 1
    assert snapshot.state.threshold == 20
    assert snapshot.weekly == before.weekly
    assert committed.state.threshold == 10
    assert committed.state.demand == before.state.demand
    assert committed.state.assignments != before.state.assignments


def test_altered_proposal_cannot_reuse_preview_token(tmp_path) -> None:
    service, schedule_id = _prepared_schedule(tmp_path)
    original = week_csv(values={("Monday", 7): 64})
    altered = week_csv(values={("Monday", 7): 65})
    preview = require_method(service, "preview_refresh")(schedule_id, csv_bytes=original)
    before = _read(service, schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "confirm_refresh")(
            schedule_id, preview.token, csv_bytes=altered, confirmed=True
        )

    assert failure.value.code == "INVALID_PREVIEW"
    assert _read(_service(tmp_path), schedule_id) == before
    assert _history(_service(tmp_path), schedule_id) == []


def test_two_previews_of_same_version_allow_only_first_confirmation(tmp_path) -> None:
    first_service, schedule_id = _prepared_schedule(tmp_path)
    second_service = _service(tmp_path)
    first_report = week_csv(values={("Monday", 7): 64})
    second_report = week_csv(values={("Tuesday", 7): 64})
    first = require_method(first_service, "preview_refresh")(schedule_id, csv_bytes=first_report)
    second = require_method(second_service, "preview_refresh")(schedule_id, csv_bytes=second_report)
    require_method(first_service, "confirm_refresh")(
        schedule_id, first.token, csv_bytes=first_report, confirmed=True
    )
    after_first = _read(_service(tmp_path), schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(second_service, "confirm_refresh")(
            schedule_id, second.token, csv_bytes=second_report, confirmed=True
        )

    assert failure.value.code == "STALE_PREVIEW"
    assert _read(_service(tmp_path), schedule_id) == after_first
    assert len(_history(_service(tmp_path), schedule_id)) == 1


def test_snapshot_insert_failure_rolls_back_active_changes(tmp_path) -> None:
    service, schedule_id = _prepared_schedule(tmp_path)
    replacement = week_csv(values={("Monday", 7): 64})
    preview = require_method(service, "preview_refresh")(schedule_id, csv_bytes=replacement)
    before = _read(service, schedule_id)
    with connect_database(service.database_path) as connection:
        connection.execute(
            "CREATE TRIGGER fail_history BEFORE INSERT ON history_snapshots "
            "BEGIN SELECT RAISE(FAIL, 'injected snapshot failure'); END"
        )

    with pytest.raises(sqlite3.DatabaseError, match="injected snapshot failure"):
        require_method(service, "confirm_refresh")(
            schedule_id, preview.token, csv_bytes=replacement, confirmed=True
        )

    assert _read(_service(tmp_path), schedule_id) == before
    assert _history(_service(tmp_path), schedule_id) == []


def test_standalone_regeneration_cancel_keeps_assignments_without_history(tmp_path) -> None:
    service, schedule_id = _prepared_schedule(tmp_path)
    before = _read(service, schedule_id)
    preview = require_method(service, "preview_generation")(schedule_id)

    cancelled = require_method(service, "confirm_generation")(
        schedule_id, preview.token, confirmed=False
    )

    assert cancelled is None
    assert _read(_service(tmp_path), schedule_id) == before
    assert _history(_service(tmp_path), schedule_id) == []


def test_snapshot_read_is_scoped_to_its_schedule(tmp_path) -> None:
    service, schedule_id = _prepared_schedule(tmp_path)
    other_id = service.create_schedule("B").id
    replacement = week_csv(values={("Monday", 7): 64})
    preview = require_method(service, "preview_refresh")(schedule_id, csv_bytes=replacement)
    require_method(service, "confirm_refresh")(
        schedule_id, preview.token, csv_bytes=replacement, confirmed=True
    )
    snapshot_id = _history(service, schedule_id)[0].id
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "get_snapshot")(other_id, snapshot_id)

    assert failure.value.code == "UNKNOWN_REFERENCE"
    assert _history(_service(tmp_path), other_id) == []
