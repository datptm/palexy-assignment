"""Service lifecycle contracts for generated scheduling diagnostics."""

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
        ("missing_demand", "MISSING_DEMAND"),
        ("missing_shifts", "MISSING_SHIFTS"),
        ("no_eligible_staff", "NO_ELIGIBLE_EMPLOYEE"),
    ],
)
def test_blocked_generation_maps_legacy_error_and_preserves_everything(
    tmp_path, prepare, expected_code
) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("Week").id
    if prepare != "missing_demand":
        require_method(service, "import_initial")(schedule_id, week_csv())
    if prepare == "missing_shifts":
        for shift in tuple(_read(service, schedule_id).state.shifts):
            require_method(service, "remove_shift")(schedule_id, shift.id, confirmed=True)
    if prepare == "no_eligible_staff":
        require_method(service, "add_employee")(schedule_id, "Zero capacity", 0)
    before = _read(service, schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(service, "generate")(schedule_id)

    assert failure.value.code == expected_code
    assert _read(_service(tmp_path), schedule_id) == before


def test_generation_preview_is_read_only_and_confirmed_diagnostics_match_result(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("Week").id
    require_method(service, "import_initial")(schedule_id, week_csv())
    require_method(service, "add_employee")(schedule_id, "Alex", 8)
    state = _read(service, schedule_id).state
    require_method(service, "add_assignment")(
        schedule_id, state.employees[0].id, 6, state.shifts[1].id
    )
    before = _read(service, schedule_id)

    preview = require_method(service, "preview_generation")(schedule_id)

    assert _read(_service(tmp_path), schedule_id) == before
    assert preview.draft.generation_diagnostics is not None
    committed = require_method(service, "confirm_generation")(
        schedule_id, preview.token, confirmed=True
    )

    assert committed.generation_diagnostics == preview.draft.generation_diagnostics
    assert _read(_service(tmp_path), schedule_id) == committed
    assert (
        require_method(_service(tmp_path), "get_schedule")(schedule_id).generation_diagnostics
        is None
    )


def test_competing_generation_previews_reject_stale_confirmation_without_lost_update(
    tmp_path,
) -> None:
    first_service = _service(tmp_path)
    schedule_id = first_service.create_schedule("Week").id
    require_method(first_service, "import_initial")(schedule_id, week_csv())
    require_method(first_service, "add_employee")(schedule_id, "Alex", 8)
    state = _read(first_service, schedule_id).state
    require_method(first_service, "add_assignment")(
        schedule_id, state.employees[0].id, 6, state.shifts[1].id
    )
    second_service = _service(tmp_path)

    first = require_method(first_service, "preview_generation")(schedule_id)
    second = require_method(second_service, "preview_generation")(schedule_id)
    committed = require_method(first_service, "confirm_generation")(
        schedule_id, first.token, confirmed=True
    )
    after_first = _read(_service(tmp_path), schedule_id)
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        require_method(second_service, "confirm_generation")(
            schedule_id, second.token, confirmed=True
        )

    assert failure.value.code == "STALE_PREVIEW"
    assert _read(_service(tmp_path), schedule_id) == after_first == committed


def test_generated_refresh_preview_and_commit_carry_the_same_draft_diagnostics(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("Week").id
    require_method(service, "import_initial")(schedule_id, week_csv())
    require_method(service, "add_employee")(schedule_id, "Alex", 8)
    replacement = week_csv(values={("Monday", 7): 64})

    preview = require_method(service, "preview_refresh")(schedule_id, csv_bytes=replacement)
    committed = require_method(service, "confirm_refresh")(
        schedule_id, preview.token, csv_bytes=replacement, confirmed=True
    )

    assert preview.draft.generation_diagnostics is not None
    assert committed.generation_diagnostics == preview.draft.generation_diagnostics
    assert _read(_service(tmp_path), schedule_id) == committed
