"""Persistent schedule-state and manual-edit contracts."""

import sqlite3

import pytest

from src.services.schedules import ScheduleService
from tests.scheduling_support import require_method, require_symbol, week_csv


def _service(tmp_path):
    return ScheduleService(tmp_path / "schedules.sqlite3")


def _state(service, schedule_id):
    return require_method(service, "get_schedule")(schedule_id).state


def _employee(service, schedule_id, name="Alex", maximum=40):
    require_method(service, "add_employee")(schedule_id, name, maximum)
    return _state(service, schedule_id).employees[-1]


def _shift(service, schedule_id, start, end):
    require_method(service, "add_shift")(schedule_id, start, end)
    return _state(service, schedule_id).shifts[-1]


def test_new_schedule_defaults_and_second_schedule_are_independent(tmp_path) -> None:
    service = _service(tmp_path)
    first = service.create_schedule("Week A")
    second = service.create_schedule("Week A")

    first_state = _state(_service(tmp_path), first.id)
    second_state = _state(_service(tmp_path), second.id)

    assert first.id != second.id
    assert first_state.threshold == second_state.threshold == 20
    assert first_state.daily_shift_limit == second_state.daily_shift_limit == 1
    assert [(shift.start_hour, shift.end_hour) for shift in first_state.shifts] == [
        (7, 15),
        (15, 23),
    ]
    assert first_state.employees == second_state.employees == ()
    assert first_state.demand is None and second_state.demand is None
    assert first_state.assignments == second_state.assignments == ()
    assert {shift.id for shift in first_state.shifts}.isdisjoint(
        {shift.id for shift in second_state.shifts}
    )


def test_rename_keeps_stable_id_and_children_after_reopen(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("Old").id
    employee = _employee(service, schedule_id)

    require_method(service, "rename_schedule")(schedule_id, "  New  ")
    reopened = _state(_service(tmp_path), schedule_id)

    assert reopened.id == schedule_id
    assert reopened.name == "New"
    assert [item.id for item in reopened.employees] == [employee.id]


def test_legacy_named_schedule_migrates_once_without_changing_its_id(tmp_path) -> None:
    database_path = tmp_path / "schedules.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE schedules (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        connection.execute("INSERT INTO schedules (id, name) VALUES (41, 'Legacy')")

    first = _state(ScheduleService(database_path), 41)
    second = _state(ScheduleService(database_path), 41)

    assert first == second
    assert first.id == 41 and first.name == "Legacy"
    assert [(shift.start_hour, shift.end_hour) for shift in first.shifts] == [(7, 15), (15, 23)]


def test_duplicate_staff_names_use_ids_and_invalid_maximum_does_not_write(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    first = _employee(service, schedule_id, "Alex", 0)
    second = _employee(service, schedule_id, "Alex", 2**31 - 1)
    before = _state(service, schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "add_employee")(schedule_id, "Bad", True)

    assert first.id != second.id
    assert failure.value.details["field"] == "weekly_max_hours"
    assert _state(_service(tmp_path), schedule_id) == before


def test_manual_over_maximum_add_commits_numeric_warning_and_persists(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    employee = _employee(service, schedule_id, maximum=32)
    morning = _state(service, schedule_id).shifts[0]
    add = require_method(service, "add_assignment")
    for day in range(4):
        add(schedule_id, employee.id, day, morning.id)

    result = add(schedule_id, employee.id, 4, morning.id)
    reopened = require_method(_service(tmp_path), "get_schedule")(schedule_id)

    assert len(reopened.state.assignments) == 5
    warning = next(item for item in result.warnings if item.code == "OVER_WEEKLY_MAX")
    assert warning.severity == "warning"
    assert warning.details == {
        "employee_id": employee.id,
        "before_hours": 32,
        "added_hours": 8,
        "assigned_hours": 40,
        "limit": 32,
        "excess": 8,
    }
    assert any(item.code == "OVER_WEEKLY_MAX" for item in reopened.warnings)


def test_lowering_staff_maximum_keeps_assignments_and_adds_warning(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    employee = _employee(service, schedule_id, maximum=16)
    morning = _state(service, schedule_id).shifts[0]
    require_method(service, "add_assignment")(schedule_id, employee.id, 0, morning.id)

    result = require_method(service, "edit_employee")(schedule_id, employee.id, "Alex", 4)

    assert len(result.state.assignments) == 1
    warning = next(item for item in result.warnings if item.code == "OVER_WEEKLY_MAX")
    assert warning.details["assigned_hours"] == 8
    assert warning.details["limit"] == 4
    assert warning.details["excess"] == 4
    assert any(
        item.code == "OVER_WEEKLY_MAX"
        for item in require_method(_service(tmp_path), "get_schedule")(schedule_id).warnings
    )


def test_overlap_rejects_atomically_but_adjacent_shift_warns_on_daily_limit(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    employee = _employee(service, schedule_id)
    morning, evening = _state(service, schedule_id).shifts
    overlap = _shift(service, schedule_id, 10, 18)
    add = require_method(service, "add_assignment")
    add(schedule_id, employee.id, 0, morning.id)
    before = _state(service, schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        add(schedule_id, employee.id, 0, overlap.id)
    assert failure.value.code == "SHIFT_OVERLAP"
    assert _state(_service(tmp_path), schedule_id) == before

    result = add(schedule_id, employee.id, 0, evening.id)
    assert len(_state(service, schedule_id).assignments) == 2
    assert any(item.code == "OVER_DAILY_SHIFT_LIMIT" for item in result.warnings)


def test_used_shift_edit_checks_other_day_and_rolls_back_all_assignments(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    employee = _employee(service, schedule_id)
    morning, evening = _state(service, schedule_id).shifts
    add = require_method(service, "add_assignment")
    add(schedule_id, employee.id, 0, morning.id)
    add(schedule_id, employee.id, 1, morning.id)
    add(schedule_id, employee.id, 1, evening.id)
    before = _state(service, schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "edit_shift")(schedule_id, morning.id, 7, 16)

    assert failure.value.code == "SHIFT_OVERLAP"
    assert _state(_service(tmp_path), schedule_id) == before


def test_reassignment_and_cross_schedule_reference_reject_without_loss(tmp_path) -> None:
    service = _service(tmp_path)
    first_id = service.create_schedule("A").id
    second_id = service.create_schedule("B").id
    first_employee = _employee(service, first_id)
    foreign_employee = _employee(service, second_id)
    morning = _state(service, first_id).shifts[0]
    add = require_method(service, "add_assignment")
    add(first_id, first_employee.id, 0, morning.id)
    assignment = _state(service, first_id).assignments[0]
    before = _state(service, first_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "reassign_assignment")(
            first_id, assignment.id, foreign_employee.id, 0, morning.id
        )

    assert failure.value.code == "UNKNOWN_REFERENCE"
    assert _state(_service(tmp_path), first_id) == before


def test_confirmed_staff_removal_deletes_dependents_and_cancel_does_nothing(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    employee = _employee(service, schedule_id)
    morning = _state(service, schedule_id).shifts[0]
    require_method(service, "add_assignment")(schedule_id, employee.id, 0, morning.id)
    before = _state(service, schedule_id)
    remove = require_method(service, "remove_employee")

    remove(schedule_id, employee.id, confirmed=False)
    assert _state(_service(tmp_path), schedule_id) == before
    remove(schedule_id, employee.id, confirmed=True)
    after = _state(_service(tmp_path), schedule_id)
    assert after.employees == ()
    assert after.assignments == ()


def test_used_shift_removal_requires_confirmation_and_clears_dependents(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    employee = _employee(service, schedule_id)
    morning = _state(service, schedule_id).shifts[0]
    require_method(service, "add_assignment")(schedule_id, employee.id, 0, morning.id)
    before = _state(service, schedule_id)
    remove = require_method(service, "remove_shift")

    remove(schedule_id, morning.id, confirmed=False)
    assert _state(_service(tmp_path), schedule_id) == before
    remove(schedule_id, morning.id, confirmed=True)
    after = _state(_service(tmp_path), schedule_id)
    assert morning.id not in {shift.id for shift in after.shifts}
    assert after.assignments == ()


def test_duplicate_shift_times_reject_without_changing_existing_shift(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    before = _state(service, schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "add_shift")(schedule_id, 7, 15)

    assert failure.value.code == "DUPLICATE_SHIFT_DEFINITION"
    assert _state(_service(tmp_path), schedule_id) == before


def test_preimport_threshold_change_persists_without_demand_or_history(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id

    require_method(service, "set_threshold")(schedule_id, 21)
    state = _state(_service(tmp_path), schedule_id)

    assert state.threshold == 21
    assert state.demand is None
    assert state.assignments == ()
    assert require_method(_service(tmp_path), "list_snapshots")(schedule_id) == []


def test_invalid_refresh_preview_preserves_demand_roster_and_history(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    _employee(service, schedule_id)
    require_method(service, "import_initial")(schedule_id, week_csv())
    before = require_method(service, "get_schedule")(schedule_id)
    history_before = require_method(service, "list_snapshots")(schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError):
        require_method(service, "preview_refresh")(
            schedule_id, csv_bytes=week_csv(values={("Monday", 7): ""})
        )

    assert require_method(_service(tmp_path), "get_schedule")(schedule_id) == before
    assert require_method(_service(tmp_path), "list_snapshots")(schedule_id) == history_before
