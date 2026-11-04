"""Manager actions through the real NiceGUI page and a temporary SQLite file."""

from nicegui import ui
from nicegui.elements.upload_files import SmallFileUpload

from tests.scheduling_support import week_csv
from tests.ui_support import input_field, manager_page, sync_test


@sync_test
async def test_staff_edit_invalid_limit_preserves_input_and_same_name_id(
    tmp_path, monkeypatch
) -> None:
    """Invalid staff input writes nothing; editing a duplicate name targets one ID."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        ids.append(schedule_id)
        for _ in range(2):
            service.add_employee(schedule_id, "Alex", 8)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        before = service.get_schedule(ids[0])
        user.find("Staff").click()
        user.find(f"Alex #{before.state.employees[1].id}").click()
        input_field(user, "Weekly maximum").clear().type("-1")
        user.find("Save employee").click()

        await user.should_see("weekly_max_hours")
        assert next(iter(input_field(user, "Weekly maximum").elements)).value == "-1"
        assert service.get_schedule(ids[0]) == before


@sync_test
async def test_staff_removal_cancel_then_confirm_removes_dependents(tmp_path, monkeypatch) -> None:
    """A used employee is removed only after the assignment count is reviewed."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.add_employee(schedule_id, "Alex", 8)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)
        ids.extend((schedule_id, state.employees[0].id))

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.find("Staff").click()
        user.find(f"Remove Alex #{ids[1]}").click()
        await user.should_see("1 assignment")
        user.find("Cancel").click()
        assert len(service.get_schedule(ids[0]).state.assignments) == 1

        user.find(f"Remove Alex #{ids[1]}").click()
        user.find("Confirm removal").click()
        await user.should_not_see(f"Alex #{ids[1]}")
        assert service.get_schedule(ids[0]).state.assignments == ()


@sync_test
async def test_shift_setting_rejects_invalid_limit_and_persists_valid_shift(
    tmp_path, monkeypatch
) -> None:
    """Shift and daily-limit controls accept only valid whole-hour values."""
    ids = []

    def seed(service):
        ids.append(service.create_schedule("Week").id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.find("Shifts").click()
        input_field(user, "Daily shift limit").clear().type("0")
        user.find("Save daily limit").click()
        await user.should_see("daily_shift_limit")
        assert service.get_schedule(ids[0]).state.daily_shift_limit == 1

        input_field(user, "Start hour").clear().type("10")
        input_field(user, "End hour").clear().type("14")
        user.find("Add shift").click()
        await user.should_see("10:00–14:00")
        assert any(
            (shift.start_hour, shift.end_hour) == (10, 14)
            for shift in service.get_schedule(ids[0]).state.shifts
        )


@sync_test
async def test_shift_edit_or_removal_conflict_and_cancel_keep_used_shift(
    tmp_path, monkeypatch
) -> None:
    """A used shift exposes a blocking preview and deletion cancellation is inert."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.add_employee(schedule_id, "Alex", 16)
        state = service.get_schedule(schedule_id).state
        for shift in state.shifts:
            service.add_assignment(schedule_id, state.employees[0].id, 0, shift.id)
        ids.extend((schedule_id, state.shifts[0].id))

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        before = service.get_schedule(ids[0])
        user.find("Shifts").click()
        user.find(f"Edit shift #{ids[1]}").click()
        input_field(user, "End hour").clear().type("16")
        user.find("Preview shift edit").click()
        await user.should_see("overlap")
        assert service.get_schedule(ids[0]) == before

        user.find("Cancel").click()
        user.find(f"Remove shift #{ids[1]}").click()
        await user.should_see("1 assignment")
        user.find("Cancel").click()
        assert service.get_schedule(ids[0]) == before


@sync_test
async def test_used_shift_warning_preview_can_save_after_review(tmp_path, monkeypatch) -> None:
    """A policy warning allows a reviewed definition edit at version zero or later."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.add_employee(schedule_id, "Alex", 8)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)
        ids.extend((schedule_id, state.shifts[0].id))

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.find("Shifts").click()
        user.find(f"Edit shift #{ids[1]}").click()
        input_field(user, "End hour").clear().type("16")
        user.find("Preview shift edit").click()
        await user.should_see("OVER_WEEKLY_MAX")
        user.find("Save shift").click()

        await user.should_see("07:00–16:00")
        saved = service.get_schedule(ids[0])
        assert saved.state.shifts[0].end_hour == 16
        assert saved.employees[0].assigned_hours == 9


@sync_test
async def test_assignment_add_or_remove_updates_hours_without_reload(tmp_path, monkeypatch) -> None:
    """An empty cell accepts a manual assignment before demand and removal reverses it."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.add_employee(schedule_id, "Alex", 8)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.find("Monday 07:00–15:00").click()
        assert len(user.find(ui.dialog).elements) == 1
        user.find("Alex").click()
        user.find("Add assignment").click()
        await user.should_see("8 / 8 h")
        assignment_id = service.get_schedule(ids[0]).state.assignments[0].id
        assert len(service.get_schedule(ids[0]).state.assignments) == 1

        remove_button = user.find(f"remove-assignment-{assignment_id}")
        button = next(iter(remove_button.elements))
        assert button.props.get("icon") == "close"
        assert button.props.get("aria-label") == "Remove assignment for Alex"
        remove_button.click()
        await user.should_see("Unassigned")
        await user.should_not_see("Alex #1")
        assert service.get_schedule(ids[0]).state.assignments == ()


@sync_test
async def test_reassignment_stale_preview_preserves_original_assignment(
    tmp_path, monkeypatch
) -> None:
    """A changed schedule version makes the reviewed reassignment invalid."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        for name in ("Alex", "Bea"):
            service.add_employee(schedule_id, name, 8)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        original = service.get_schedule(ids[0]).state.assignments[0]
        user.find("Monday 07:00–15:00").click()
        user.find("Reassign").click()
        user.find("Bea").click()
        service.rename_schedule(ids[0], "Changed elsewhere")
        user.find("Save reassignment").click()

        await user.should_see("STALE_PREVIEW")
        await user.should_not_see("Save reassignment")
        assert service.get_schedule(ids[0]).state.assignments[0] == original


@sync_test
async def test_import_invalid_upload_preserves_demand_and_roster(tmp_path, monkeypatch) -> None:
    """Oversized bytes fail at the upload boundary without replacing active data."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        before = service.get_schedule(ids[0])
        user.find("Demand import").click()
        upload = next(iter(user.find(ui.upload).elements))
        await upload.handle_uploads(
            [SmallFileUpload("report.csv", "text/csv", b"x" * (1024 * 1024 + 1))]
        )

        await user.should_see("1 MiB")
        assert service.get_schedule(ids[0]) == before
        assert service.list_snapshots(ids[0]) == []


@sync_test
async def test_import_valid_report_shows_findings_then_commits_without_roster(
    tmp_path, monkeypatch
) -> None:
    """A reordered report with ignorable totals becomes 112 demand cells only."""
    ids = []

    def seed(service):
        ids.append(service.create_schedule("Week").id)

    csv_bytes = week_csv(
        day_order=("Friday", "Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"),
        values={("Friday", 7): 22},
        title=True,
        total=True,
    )
    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.find("Demand import").click()
        upload = next(iter(user.find(ui.upload).elements))
        await upload.handle_uploads([SmallFileUpload("report.csv", "text/csv", csv_bytes)])
        await user.should_see("Friday 07:00: 22")
        await user.should_see("warning")
        assert service.get_schedule(ids[0]).state.demand is None

        user.find("Import demand").click()
        await user.should_see("Imported demand")
        saved = service.get_schedule(ids[0])
        assert len(saved.state.demand) == 112
        assert saved.state.assignments == ()
        assert service.list_snapshots(ids[0]) == []


@sync_test
async def test_import_invalid_encoding_shows_error_and_keeps_existing_demand(
    tmp_path, monkeypatch
) -> None:
    """Bad UTF-8 is rejected by the service without a partial write."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        before = service.get_schedule(ids[0])
        user.find("Demand import").click()
        upload = next(iter(user.find(ui.upload).elements))
        await upload.handle_uploads([SmallFileUpload("report.csv", "text/csv", b"\xff")])

        await user.should_see("INVALID_ENCODING")
        assert service.get_schedule(ids[0]) == before


@sync_test
async def test_refresh_preview_cancel_preserves_manual_roster_and_history(
    tmp_path, monkeypatch
) -> None:
    """Changing a proposal before confirmation discards its preview and writes nothing."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        before = service.get_schedule(ids[0])
        input_field(user, "Threshold").clear().type("10")
        user.find("Preview threshold change").click()
        await user.should_see("replaces all assignments")
        user.find("Cancel").click()

        assert service.get_schedule(ids[0]) == before
        assert service.list_snapshots(ids[0]) == []


@sync_test
async def test_refresh_preview_preimport_threshold_saves_without_history(
    tmp_path, monkeypatch
) -> None:
    """Before demand, threshold is a direct setting change rather than a replacement."""
    ids = []

    def seed(service):
        ids.append(service.create_schedule("Week").id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        input_field(user, "Threshold").clear().type("10")
        user.find("Save threshold").click()

        await user.should_see("Threshold: 10")
        assert service.get_schedule(ids[0]).state.threshold == 10
        assert service.list_snapshots(ids[0]) == []


@sync_test
async def test_generation_missing_demand_shows_specific_prerequisite(tmp_path, monkeypatch) -> None:
    """Auto-schedule cannot claim success without imported demand."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.add_employee(schedule_id, "Alex", 8)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        before = service.get_schedule(ids[0])
        user.find("Auto-schedule").click()

        await user.should_see("MISSING_DEMAND")
        assert service.get_schedule(ids[0]) == before


@sync_test
async def test_refresh_confirmation_uses_same_proposal_and_saves_prior_state(
    tmp_path, monkeypatch
) -> None:
    """A threshold preview is read-only; confirmation replaces and snapshots once."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        before = service.get_schedule(ids[0])
        input_field(user, "Threshold").clear().type("10")
        user.find("Preview threshold change").click()
        await user.should_see("replaces all assignments")
        assert service.get_schedule(ids[0]) == before
        assert service.list_snapshots(ids[0]) == []

        user.find("Confirm replacement").click()
        await user.should_see("Threshold: 10")
        assert service.get_schedule(ids[0]).state.threshold == 10
        snapshots = service.list_snapshots(ids[0])
        assert len(snapshots) == 1
        assert service.get_snapshot(ids[0], snapshots[0].id).state == before.state


@sync_test
async def test_generation_partial_draft_is_success_and_regeneration_cancel_is_inert(
    tmp_path, monkeypatch
) -> None:
    """One worker yields a partial draft; a later replacement can be cancelled."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.find("Auto-schedule").click()
        await user.should_see("104 unmet staff-hours")
        before = service.get_schedule(ids[0])
        assert before.weekly.unmet_staff_hours == 104

        user.find("Auto-schedule").click()
        await user.should_see("replaces all assignments")
        assert len(user.find(ui.dialog).elements) == 1
        user.find("Cancel").click()
        assert service.get_schedule(ids[0]) == before
        assert service.list_snapshots(ids[0]) == []


@sync_test
async def test_history_is_read_only_and_return_reloads_active_result(tmp_path, monkeypatch) -> None:
    """The captured prior version is distinct from current state and has no edit action."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)
        preview = service.preview_refresh(schedule_id, threshold=10)
        service.confirm_refresh(schedule_id, preview.token, threshold=10, confirmed=True)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.find("History").click()
        user.find("THRESHOLD_CHANGE").click()
        await user.should_see("Historical / read-only")
        await user.should_see("Threshold: 20")
        assert len(user.find(ui.dialog).elements) == 1
        await user.should_not_see("Restore snapshot")
        await user.should_not_see("Add employee")

        user.find("Return to active").click()
        await user.should_see("Threshold: 10")
        assert service.get_schedule(ids[0]).state.threshold == 10


@sync_test
async def test_reassignment_moves_to_selected_destination_atomically(tmp_path, monkeypatch) -> None:
    """A reviewed move changes person, day, and shift in one service write."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        for name in ("Alex", "Bea"):
            service.add_employee(schedule_id, name, 16)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        original = service.get_schedule(ids[0]).state.assignments[0]
        state = service.get_schedule(ids[0]).state
        user.find("Monday 07:00–15:00").click()
        user.find("Reassign").click()
        user.find("Destination Tuesday 15:00–23:00").click()
        user.find("Bea").click()
        user.find("Save reassignment").click()

        await user.should_see("Bea #2")
        saved = service.get_schedule(ids[0]).state.assignments
        assert len(saved) == 1
        assert saved[0].id == original.id
        assert (saved[0].employee_id, saved[0].day, saved[0].shift_id) == (
            state.employees[1].id,
            1,
            state.shifts[1].id,
        )


@sync_test
async def test_changed_threshold_discards_reviewed_refresh(tmp_path, monkeypatch) -> None:
    """Editing the proposed threshold invalidates its signed preview in the page."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)
        ids.append(schedule_id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        input_field(user, "Threshold").clear().type("10")
        user.find("Preview threshold change").click()
        await user.should_see("replaces all assignments")
        input_field(user, "Threshold").clear().type("11")
        user.find("Confirm replacement").click()

        await user.should_see("Preview changed")
        assert service.get_schedule(ids[0]).state.threshold == 20
        assert service.list_snapshots(ids[0]) == []
