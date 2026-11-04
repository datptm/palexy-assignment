"""Red contracts for read-only edit previews and version-bound saves."""

from dataclasses import is_dataclass
from inspect import signature

import pytest

from src.model.scheduling import SchedulingError
from src.services.schedules import ScheduleService
from tests.scheduling_support import require_method, require_symbol, week_csv


def _schedule(tmp_path):
    service = ScheduleService(tmp_path / "schedules.sqlite3")
    schedule_id = service.create_schedule("Week").id
    return service, schedule_id


def _state(service, schedule_id):
    return service.get_schedule(schedule_id).state


def _employee(service, schedule_id, name="Alex", maximum=32):
    service.add_employee(schedule_id, name, maximum)
    return _state(service, schedule_id).employees[-1]


def test_preview_contract_records_are_frozen() -> None:
    """The transient preview values cannot be mutated after review."""
    for name in ("AssignmentOptionPreview", "AssignmentOptionsPreview", "ShiftEditPreview"):
        record = require_symbol("src.model.scheduling", name)
        assert is_dataclass(record)
        assert record.__dataclass_params__.frozen


def test_assignment_options_preview_is_read_only_and_has_stable_ids(tmp_path) -> None:
    """Opening a cell returns every employee once without changing the week."""
    service, schedule_id = _schedule(tmp_path)
    first = _employee(service, schedule_id, "Alex")
    second = _employee(service, schedule_id, "Alex")
    before = service.get_schedule(schedule_id)

    preview = require_method(service, "preview_assignment_options")(
        schedule_id, 0, before.state.shifts[0].id
    )

    assert preview.schedule_id == schedule_id
    assert preview.baseline_version == before.state.version
    assert preview.day == 0
    assert [option.employee_id for option in preview.options] == [first.id, second.id]
    assert service.get_schedule(schedule_id) == before


def test_assignment_options_preview_uses_one_state_read_for_all_staff(
    tmp_path, monkeypatch
) -> None:
    """Opening one cell must not reload SQLite once per employee."""
    import src.services.schedules as schedules_module

    service, schedule_id = _schedule(tmp_path)
    for index in range(5):
        _employee(service, schedule_id, f"Person {index}")
    shift_id = _state(service, schedule_id).shifts[0].id
    real_load = schedules_module.load_state
    reads = []

    def counted_load(connection, selected_id):
        reads.append(selected_id)
        return real_load(connection, selected_id)

    monkeypatch.setattr(schedules_module, "load_state", counted_load)
    preview = require_method(service, "preview_assignment_options")(schedule_id, 0, shift_id)

    assert len(preview.options) == 5
    assert reads == [schedule_id]


def test_assignment_options_preview_blocks_overlap_but_allows_policy_warning(tmp_path) -> None:
    """Hard overlap blocks; a second adjacent shift has a selectable warning."""
    service, schedule_id = _schedule(tmp_path)
    employee = _employee(service, schedule_id, maximum=8)
    service.add_shift(schedule_id, 10, 14)
    state = _state(service, schedule_id)
    service.add_assignment(schedule_id, employee.id, 0, state.shifts[0].id)
    before = service.get_schedule(schedule_id)

    overlap = require_method(service, "preview_assignment_options")(
        schedule_id, 0, state.shifts[-1].id
    )
    adjacent = service.preview_assignment_options(schedule_id, 0, state.shifts[1].id)

    assert overlap.options[0].blocked is True
    assert any(item.severity == "error" for item in overlap.options[0].findings)
    assert adjacent.options[0].blocked is False
    assert {item.code for item in adjacent.options[0].findings} >= {
        "OVER_WEEKLY_MAX",
        "OVER_DAILY_SHIFT_LIMIT",
    }
    assert service.get_schedule(schedule_id) == before


def test_assignment_options_preview_projects_numeric_overage_and_coverage(tmp_path) -> None:
    """A 32-hour worker sees the exact 40-hour effect before a fifth shift."""
    service, schedule_id = _schedule(tmp_path)
    employee = _employee(service, schedule_id)
    service.import_initial(schedule_id, week_csv())
    shift_id = _state(service, schedule_id).shifts[0].id
    for day in range(4):
        service.add_assignment(schedule_id, employee.id, day, shift_id)
    before = service.get_schedule(schedule_id)

    preview = require_method(service, "preview_assignment_options")(schedule_id, 4, shift_id)
    choice = preview.options[0]

    assert choice.blocked is False
    assert choice.current_hours == 32
    assert choice.projected_hours == 40
    assert choice.weekly_max_hours == 32
    assert any(item.code == "OVER_WEEKLY_MAX" for item in choice.findings)
    assert choice.before_weekly.covered_staff_hours == 32
    assert choice.after_weekly.covered_staff_hours == 40
    assert service.get_schedule(schedule_id) == before


def test_shift_preview_reports_impact_without_writing(tmp_path) -> None:
    """A used shift preview names affected work and projects its longer duration."""
    service, schedule_id = _schedule(tmp_path)
    employee = _employee(service, schedule_id)
    service.import_initial(schedule_id, week_csv())
    shift_id = _state(service, schedule_id).shifts[0].id
    service.add_assignment(schedule_id, employee.id, 0, shift_id)
    assignment = _state(service, schedule_id).assignments[0]
    before = service.get_schedule(schedule_id)

    preview = require_method(service, "preview_shift_edit")(schedule_id, shift_id, 7, 16)

    assert preview.schedule_id == schedule_id
    assert preview.baseline_version == before.state.version
    assert preview.affected_assignment_ids == (assignment.id,)
    assert preview.old_duration == 8 and preview.new_duration == 9
    assert preview.projected_result.weekly.scheduled_staff_hours == 9
    assert service.get_schedule(schedule_id) == before


def test_shift_preview_conflict_is_blocked_and_keeps_old_definition(tmp_path) -> None:
    """A conflicting time proposal returns a hard finding and leaves state intact."""
    service, schedule_id = _schedule(tmp_path)
    employee = _employee(service, schedule_id)
    state = _state(service, schedule_id)
    service.add_assignment(schedule_id, employee.id, 0, state.shifts[0].id)
    service.add_assignment(schedule_id, employee.id, 0, state.shifts[1].id)
    before = service.get_schedule(schedule_id)

    preview = require_method(service, "preview_shift_edit")(schedule_id, state.shifts[0].id, 7, 16)

    assert any(item.severity == "error" for item in preview.findings)
    assert preview.projected_result is None
    assert service.get_schedule(schedule_id) == before


@pytest.mark.parametrize(
    "operation",
    ["add_assignment", "reassign_assignment", "edit_shift", "remove_employee", "remove_shift"],
)
def test_expected_version_rejects_stale_write_atomically(tmp_path, operation) -> None:
    """All five reviewed edits must reject an intervening committed version."""
    service, schedule_id = _schedule(tmp_path)
    employee = _employee(service, schedule_id)
    state = _state(service, schedule_id)
    service.add_assignment(schedule_id, employee.id, 0, state.shifts[0].id)
    reviewed_version = _state(service, schedule_id).version
    service.rename_schedule(schedule_id, "Changed elsewhere")
    before = service.get_schedule(schedule_id)
    assignment_id = before.state.assignments[0].id
    calls = {
        "add_assignment": (employee.id, 1, state.shifts[0].id),
        "reassign_assignment": (assignment_id, employee.id, 1, state.shifts[0].id),
        "edit_shift": (state.shifts[0].id, 7, 14),
        "remove_employee": (employee.id,),
        "remove_shift": (state.shifts[0].id,),
    }
    kwargs = {"expected_version": reviewed_version}
    if operation.startswith("remove_"):
        kwargs["confirmed"] = True

    assert "expected_version" in signature(require_method(service, operation)).parameters, (
        f"missing planned ScheduleService.{operation} expected_version gate"
    )

    with pytest.raises(SchedulingError) as failure:
        require_method(service, operation)(schedule_id, *calls[operation], **kwargs)

    assert failure.value.code == "STALE_PREVIEW"
    assert service.get_schedule(schedule_id) == before


def test_assignment_preview_rejects_foreign_employee_reference(tmp_path) -> None:
    """A replacement ID from another schedule cannot inspect or change this roster."""
    service, schedule_id = _schedule(tmp_path)
    other_id = service.create_schedule("Other").id
    foreign = _employee(service, other_id)
    before = service.get_schedule(schedule_id)

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "preview_assignment_options")(
            schedule_id,
            0,
            before.state.shifts[0].id,
            replacing_assignment_id=foreign.id,
        )

    assert failure.value.code == "UNKNOWN_REFERENCE"
    assert service.get_schedule(schedule_id) == before


def test_reviewed_shift_edit_accepts_initial_version_zero(tmp_path) -> None:
    """A newly created schedule can save its first version-bound shift edit."""
    service, schedule_id = _schedule(tmp_path)
    state = _state(service, schedule_id)
    assert state.version == 0

    preview = service.preview_shift_edit(schedule_id, state.shifts[0].id, 7, 14)
    saved = service.edit_shift(
        schedule_id,
        state.shifts[0].id,
        7,
        14,
        expected_version=preview.baseline_version,
    )

    assert saved.state.version == 1
    assert saved.state.shifts[0].end_hour == 14


def test_reassignment_preview_includes_origin_and_destination_hours(tmp_path) -> None:
    """A move preview reports coverage changes at both ends of the move."""
    service, schedule_id = _schedule(tmp_path)
    employee = _employee(service, schedule_id)
    service.import_initial(schedule_id, week_csv())
    state = _state(service, schedule_id)
    service.add_assignment(schedule_id, employee.id, 0, state.shifts[0].id)
    assignment_id = _state(service, schedule_id).assignments[0].id

    preview = service.preview_assignment_options(
        schedule_id,
        1,
        state.shifts[1].id,
        replacing_assignment_id=assignment_id,
    )
    option = preview.options[0]

    assert {(cell.day, cell.hour) for cell in option.before_hourly} == {
        (day, hour) for day, start in ((0, 7), (1, 15)) for hour in range(start, start + 8)
    }
    assert {(cell.day, cell.hour) for cell in option.after_hourly} == {
        (day, hour) for day, start in ((0, 7), (1, 15)) for hour in range(start, start + 8)
    }


def test_shift_preview_rejects_noninteger_range_without_writing(tmp_path) -> None:
    """Malformed browser times produce a structured error and retain the shift."""
    service, schedule_id = _schedule(tmp_path)
    before = service.get_schedule(schedule_id)

    with pytest.raises(SchedulingError) as failure:
        service.preview_shift_edit(schedule_id, before.state.shifts[0].id, "7", 15)

    assert failure.value.code == "INVALID_SHIFT_RANGE"
    assert service.get_schedule(schedule_id) == before
