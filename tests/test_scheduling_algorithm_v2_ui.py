"""Transient algorithm diagnostics in the manager-facing generation summary."""

from nicegui import ui

from tests.scheduling_support import week_csv
from tests.ui_support import manager_page, sync_test


@sync_test
async def test_generation_summary_collapses_shortfalls_under_a_plain_heading(
    tmp_path, monkeypatch
) -> None:
    """Managers can fold generated rationale under a plain shortfalls heading."""

    def seed(service):
        schedule_id = service.create_schedule("Week").id
        service.import_initial(schedule_id, week_csv())
        service.add_employee(schedule_id, "Alex", 8)
        state = service.get_schedule(schedule_id).state
        service.remove_shift(schedule_id, state.shifts[1].id, confirmed=True)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("Auto-schedule").click()

        await user.should_see("Generation diagnostics", retries=50)
        expansion = next(
            element
            for element in user.find(ui.expansion).elements
            if element.text == "Generation diagnostics"
        )
        assert expansion.value is False
        expansion.open()
        assert expansion.value is True
        with user.scope("Generation diagnostics"):
            await user.should_see("Unavoidable shortage lower bound")
            await user.should_see("Optimizer cost")
            await user.should_see("NO_SHIFT_COVERAGE")
            shortfalls = next(
                element
                for element in user.find("Shortfalls").elements
                if isinstance(element, ui.label)
            )
            assert "schedule-workspace-card-title" in shortfalls._classes
            assert "schedule-alert--warning" not in shortfalls._classes
        expansion.close()
        assert expansion.value is False


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
        await user.should_see("Generation diagnostics", retries=50)
        expansion = next(
            element
            for element in user.find(ui.expansion).elements
            if element.text == "Generation diagnostics"
        )
        expansion.open()
        await user.should_see("Optimizer cost")
        await user.should_see("Linear coverage metrics")
