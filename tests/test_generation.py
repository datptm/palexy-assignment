"""Draft prerequisites, useful coverage, capacity, and deterministic ties."""

import pytest

from src.services.schedules import ScheduleService
from tests.scheduling_support import require_method, require_symbol, week_csv


def _service(tmp_path):
    return ScheduleService(tmp_path / "schedules.sqlite3")


def _read(service, schedule_id):
    return require_method(service, "get_schedule")(schedule_id)


@pytest.mark.parametrize(
    "prepare,expected_code",
    [
        ("none", "MISSING_DEMAND"),
        ("no_shifts", "MISSING_SHIFTS"),
        ("zero_max", "NO_ELIGIBLE_EMPLOYEE"),
    ],
)
def test_generation_prerequisites_preserve_current_state(tmp_path, prepare, expected_code) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    if prepare != "none":
        require_method(service, "import_initial")(schedule_id, week_csv())
    if prepare == "no_shifts":
        for shift in tuple(_read(service, schedule_id).state.shifts):
            require_method(service, "remove_shift")(schedule_id, shift.id, confirmed=True)
    if prepare == "zero_max":
        require_method(service, "add_employee")(schedule_id, "Alex", 0)
    before = _read(service, schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "generate")(schedule_id)

    assert failure.value.code == expected_code
    assert _read(_service(tmp_path), schedule_id) == before


def test_insufficient_capacity_commits_valid_partial_draft(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    require_method(service, "import_initial")(schedule_id, week_csv())
    require_method(service, "add_employee")(schedule_id, "Alex", 8)
    employee = _read(service, schedule_id).state.employees[0]

    result = require_method(service, "generate")(schedule_id)

    assert {(item.employee_id, item.day, item.shift_id) for item in result.state.assignments} == {
        (employee.id, 0, result.state.shifts[0].id)
    }
    assert result.weekly.scheduled_staff_hours == 8
    assert result.weekly.unmet_staff_hours == 104
    assert result.weekly.coverage_rate == 8 / 112
    assert _read(_service(tmp_path), schedule_id) == result


def test_equal_candidates_use_stable_employee_id_and_repeated_inputs_match(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    require_method(service, "import_initial")(schedule_id, week_csv())
    for name in ("Z", "A"):
        require_method(service, "add_employee")(schedule_id, name, 8)
    employees = _read(service, schedule_id).state.employees

    first = require_method(service, "generate")(schedule_id)
    preview = require_method(service, "preview_generation")(schedule_id)

    assert first.state.assignments[0].employee_id == min(item.id for item in employees)
    assert first.state.assignments[0].day == 0
    assert first.state.assignments[0].shift_id == first.state.shifts[0].id
    assert {
        (item.employee_id, item.day, item.shift_id) for item in preview.draft.state.assignments
    } == {(item.employee_id, item.day, item.shift_id) for item in first.state.assignments}


def test_generated_roster_obeys_reference_overlap_and_hour_invariants(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    require_method(service, "import_initial")(
        schedule_id, week_csv(values={("Monday", 7): 64, ("Tuesday", 8): 48})
    )
    for name, maximum in (("A", 8), ("B", 16), ("C", 0)):
        require_method(service, "add_employee")(schedule_id, name, maximum)

    result = require_method(service, "generate")(schedule_id)
    employees = {item.id: item for item in result.state.employees}
    shifts = {item.id: item for item in result.state.shifts}
    assignments = result.state.assignments

    assert all(item.employee_id in employees and item.shift_id in shifts for item in assignments)
    assert len({(item.employee_id, item.day, item.shift_id) for item in assignments}) == len(
        assignments
    )
    assert all(0 <= item.day <= 6 for item in assignments)
    for employee in employees.values():
        own = [item for item in assignments if item.employee_id == employee.id]
        hours = sum(
            shifts[item.shift_id].end_hour - shifts[item.shift_id].start_hour for item in own
        )
        assert hours <= employee.weekly_max_hours
        assert len({item.day for item in own}) == len(own)
    assert (
        sum(item.assigned_hours for item in result.employees) == result.weekly.scheduled_staff_hours
    )
    assert result.weekly.unmet_staff_hours > 0
