"""Rendered roster, demand, coverage, and warning contracts."""

import pytest
from nicegui import ui

from src.model.scheduling import SchedulingError
from tests.scheduling_support import week_csv
from tests.ui_support import manager_page, sync_test
from ui.presentation import whole_number


def test_whole_number_rejects_oversized_browser_value() -> None:
    """A very long numeric field is rejected before integer conversion or a write."""
    with pytest.raises(SchedulingError) as failure:
        whole_number("9" * 5000, "weekly_max_hours")
    assert failure.value.code == "INVALID_INTEGER"


@sync_test
async def test_roster_shows_seven_editable_days_and_unassigned_shift_cells(
    tmp_path, monkeypatch
) -> None:
    """A new week has a roster grid rather than only the scaffold summary."""

    def seed(service):
        service.create_schedule("Week")

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"):
            await user.should_see(day)
        await user.should_see("Unassigned")
        await user.should_see("07:00–15:00")
        await user.should_see("15:00–23:00")
        await user.should_see("Demand unavailable")


@sync_test
async def test_dashboard_prioritizes_roster_and_compares_required_with_scheduled_staff(
    tmp_path, monkeypatch
) -> None:
    """The main workspace shows essential metrics and an explicit coverage legend."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 40)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        await user.should_see("Weekly staff roster")
        await user.should_see("Monday–Sunday weekly roster")
        await user.should_see("Coverage")
        await user.should_see("Uncovered hours")
        await user.should_see("Scheduled hours")
        await user.should_see("Warnings")
        await user.should_see("Demand & coverage chart")
        await user.should_see("Required staff · navy step line")
        await user.should_see("Scheduled staff · teal bars; red marks a shortage")
        await user.should_see("112 hourly slots have uncovered demand")
        assert len(user.find(ui.echart).elements) == 1


@sync_test
async def test_staff_workspace_opens_in_dialog_instead_of_below_chart(
    tmp_path, monkeypatch
) -> None:
    """Workspace controls stay off the dashboard until opened from navigation."""

    def seed(service):
        service.create_schedule("Week")

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        await user.should_see("Demand & coverage chart")
        await user.should_not_see("Add employee")
        await user.should_not_see("Employee list & capacity")

        user.find("Staff").click()

        await user.should_see("Add employee")
        await user.should_see("Employee list & capacity")
        assert len(user.find(ui.dialog).elements) == 1
        with user.scope(ui.dialog):
            await user.should_not_see("Shifts")
        user.find("Close").click()
        await user.should_not_see("Add employee")


@sync_test
async def test_workspace_dialog_stays_mounted_during_form_interactions(
    tmp_path, monkeypatch
) -> None:
    """Editing within an open workspace must not recreate its dialog."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.add_employee(schedule_id, "Alex", 8)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Staff").click()
        dialog = next(iter(user.find(ui.dialog).elements))
        user.find("Alex #1").click()
        await user.should_see("Edit Employee")
        assert next(iter(user.find(ui.dialog).elements)) is dialog
        user.find("Close").click()
        await user.should_not_see("Edit Employee")


@sync_test
async def test_roster_cell_hides_repeated_capacity_and_keeps_editor_mounted(
    tmp_path, monkeypatch
) -> None:
    """The calendar stays compact while choices update the existing editor."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.add_employee(schedule_id, "Alex", 16)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        await user.should_not_see("8 / 16 h")
        user.find("Tuesday 07:00–15:00").click()
        dialog = next(iter(user.find(ui.dialog).elements))
        user.find("Alex").click()
        await user.should_see("Edit Tuesday 07:00–15:00")
        assert next(iter(user.find(ui.dialog).elements)) is dialog


@sync_test
async def test_demand_and_assignment_reviews_use_labeled_tables(tmp_path, monkeypatch) -> None:
    """Dense day/hour and preview figures have columns a manager can scan."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Demand import").click()
        await user.should_see("Transactions")
        user.find("Close").click()
        user.find("Monday 07:00–15:00").click()
        user.find("Alex").click()
        await user.should_see("Before")
        await user.should_see("After")
        await user.should_see("Scheduled")


@sync_test
async def test_assignment_editor_guides_selection_and_impact_review(tmp_path, monkeypatch) -> None:
    """An empty cell separates the current roster, choices, and proposed impact."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Monday 07:00–15:00").click()
        await user.should_see("Current assignments")
        await user.should_see("No one assigned to this shift")
        await user.should_see("Choose an employee")
        await user.should_see("Select a person to review the impact")
        user.find("Alex").click()
        await user.should_see("Review impact")
        await user.should_see("Weekly hours")
        await user.should_see("Daily shifts")
        await user.should_see("Add assignment")


@sync_test
async def test_reassignment_editor_separates_destination_and_employee_choice(
    tmp_path, monkeypatch
) -> None:
    """A move shows its source and destination choices before save."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        for name in ("Alex", "Bea"):
            service.add_employee(schedule_id, name, 16)
        state = service.get_schedule(schedule_id).state
        service.add_assignment(schedule_id, state.employees[0].id, 0, state.shifts[0].id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Monday 07:00–15:00").click()
        user.find("Reassign").click()
        await user.should_see("Moving assignment")
        await user.should_see("Choose destination")
        user.find("Destination Tuesday 15:00–23:00").click()
        await user.should_see("Choose an employee")
        user.find("Bea").click()
        await user.should_see("Review impact")
        await user.should_see("Save reassignment")


@sync_test
async def test_workspace_dialogs_follow_reference_screen_sections(tmp_path, monkeypatch) -> None:
    """Each workspace opens in the shared dialog shell with its designed heading."""

    def seed(service):
        service.create_schedule("Week")

    workspaces = (
        ("Staff", "Staff Management"),
        ("Shifts", "Shift Configurations"),
        ("Demand import", "Import Demand"),
        ("Hourly analysis", "Hourly Analysis & Gap Dashboard"),
        ("Warnings", "Warnings & Inconsistencies"),
        ("History", "Schedule History"),
    )
    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        for tab, heading in workspaces:
            user.find(tab).click()
            await user.should_see(heading)
            assert len(user.find(ui.dialog).elements) == 1


@sync_test
async def test_roster_displays_both_same_name_assignees_by_stable_id(tmp_path, monkeypatch) -> None:
    """One cell lists every person even when display names collide."""
    ids = []

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        for _ in range(2):
            service.add_employee(schedule_id, "Alex", 8)
        state = service.get_schedule(schedule_id).state
        ids.extend(item.id for item in state.employees)
        for employee_id in ids:
            service.add_assignment(schedule_id, employee_id, 0, state.shifts[0].id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        await user.should_see(f"Alex #{ids[0]}")
        await user.should_see(f"Alex #{ids[1]}")


@sync_test
async def test_analysis_distinguishes_missing_demand_from_imported_zero(
    tmp_path, monkeypatch
) -> None:
    """Zero transactions are shown as zero, while absent demand is unavailable."""
    schedule_ids = []

    def seed(service):
        schedule_ids.append(service.create_schedule("Missing").id)
        zero_id = service.create_schedule("Zero").id
        schedule_ids.append(zero_id)
        service.import_initial(zero_id, week_csv())

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        await user.should_see("Import demand to see coverage")
        user.find("Hourly analysis").click()
        await user.should_see("Coverage unavailable")
        user.find(f"Zero #{schedule_ids[1]}").click()
        user.find("Hourly analysis").click()

        await user.should_see("0 transactions")
        await user.should_see("1 required")
        await user.should_see("Monday 07:00")


@sync_test
async def test_analysis_or_warning_shows_numeric_gap_and_overage(tmp_path, monkeypatch) -> None:
    """A required-two/staffed-three hour shows excess one, capped coverage, and warning."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv(values={("Monday", 7): 33}))
        service.add_shift(schedule_id, 7, 8)
        state = service.get_schedule(schedule_id).state
        for name in ("A", "B", "C"):
            service.add_employee(schedule_id, name, 0)
        state = service.get_schedule(schedule_id).state
        short_shift = state.shifts[-1]
        for employee in state.employees:
            service.add_assignment(schedule_id, employee.id, 0, short_shift.id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Hourly analysis").click()

        await user.should_see("Monday 07:00")
        await user.should_see("2 required")
        await user.should_see("3 scheduled")
        await user.should_see("Excess 1")
        await user.should_see("100% coverage")
        await user.should_see("OVER_WEEKLY_MAX")
        user.find("Locate warning").click()
        await user.should_see("Showing A")
        user.find("Warnings").click()
        await user.should_see("Warnings & Inconsistencies")
        await user.should_see("Review and Adjust")


@sync_test
async def test_analysis_or_warning_labels_both_distinct_weekly_ratios(
    tmp_path, monkeypatch
) -> None:
    """The overall 14.25 ratio is separate from the staffed-cell mean 14.5."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(
            schedule_id,
            week_csv(values={("Monday", 7): 33, ("Monday", 8): 48, ("Monday", 9): 33}),
        )
        service.set_daily_shift_limit(schedule_id, 3)
        for hour in (7, 8, 9):
            service.add_shift(schedule_id, hour, hour + 1)
        for name in ("A", "B", "C"):
            service.add_employee(schedule_id, name, 3)
        state = service.get_schedule(schedule_id).state
        short_shifts = state.shifts[-3:]
        for employee in state.employees:
            service.add_assignment(schedule_id, employee.id, 0, short_shifts[0].id)
            service.add_assignment(schedule_id, employee.id, 0, short_shifts[1].id)
        for employee in state.employees[:2]:
            service.add_assignment(schedule_id, employee.id, 0, short_shifts[2].id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Hourly analysis").click()
        await user.should_see("Overall transactions per staff-hour: 14.25")
        await user.should_see("Staffed-cell average: 14.5")
