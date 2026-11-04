"""Transient algorithm diagnostics in the manager-facing generation summary."""

from tests.scheduling_support import week_csv
from tests.ui_support import input_field, manager_page, sync_test


@sync_test
async def test_generation_summary_explains_shortfalls_and_clears_transient_diagnostics(
    tmp_path, monkeypatch
) -> None:
    """The displayed rationale belongs only to the current generated result."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)
        state = service.get_schedule(schedule_id).state
        service.remove_shift(schedule_id, state.shifts[1].id, confirmed=True)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Auto-schedule").click()

        await user.should_see("Generation diagnostics")
        await user.should_see("Unavoidable shortage lower bound")
        await user.should_see("Optimizer cost")
        await user.should_see("NO_SHIFT_COVERAGE")

        user.find("Staff").click()
        await user.should_see("Effective capacity")
        await user.should_see("Target hours")
        input_field(user, "Employee name").type("Taylor")
        input_field(user, "Weekly maximum").type("8")
        user.find("Add employee").click()

        await user.should_not_see("Generation diagnostics")
        await user.open("/")
        await user.should_not_see("Generation diagnostics")


@sync_test
async def test_generation_explanation_keeps_linear_metrics_distinct_from_optimizer_cost(
    tmp_path, monkeypatch
) -> None:
    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Auto-schedule").click()

        await user.should_see("Coverage")
        await user.should_see("Optimizer cost")
        await user.should_see("Linear coverage metrics")
