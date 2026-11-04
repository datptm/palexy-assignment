"""Read-only prior state inspection."""

from functools import partial

from nicegui import ui

from src.domain.periods import WEEKDAYS
from ui.presentation import hour_range, person_label, ratio
from ui.session import PageSession


def render_history(page: PageSession) -> None:
    """Show schedule-owned snapshots without restore or edit actions."""
    with ui.column().classes("schedule-workspace-intro"):
        ui.label("Schedule History").classes("schedule-workspace-title")
        ui.label("Generated runs · historical versions are read-only").classes(
            "schedule-workspace-subtitle"
        )
    if page.history is None:
        if not page.history_list:
            ui.label("No saved history yet").classes("schedule-alert")
            return
        with ui.column().classes("schedule-history-list"):
            for summary in page.history_list:
                with ui.card().classes("schedule-workspace-card schedule-history-entry"):
                    with ui.row().classes("schedule-header-row justify-between"):
                        with ui.column().classes("gap-1"):
                            ui.button(
                                f"Version {summary.prior_version} · {summary.reason}",
                                on_click=partial(_open, page, summary.id),
                            ).props("flat")
                            ui.label(summary.captured_at_utc).classes("schedule-capacity-meta")
                        ui.button(
                            "View version",
                            on_click=partial(_open, page, summary.id),
                        ).props("unelevated")
        return
    snapshot = page.history
    with ui.row().classes("schedule-header-row justify-between"):
        ui.label("Historical / read-only").classes("schedule-status")
        ui.button("Return to active", on_click=lambda: _return_active(page)).props("flat")
    with ui.element("div").classes("schedule-kpis"):
        with ui.column().classes("schedule-metric gap-0"):
            ui.label(f"Threshold: {snapshot.state.threshold}").classes("schedule-metric-label")
        _history_metric("Daily shift limit", str(snapshot.state.daily_shift_limit))
        _history_metric("Scheduled staff-hours", str(snapshot.weekly.scheduled_staff_hours))
        _history_metric("Coverage", ratio(snapshot.weekly.coverage_rate))
        _history_metric("Required staff-hours", str(snapshot.weekly.required_staff_hours))
        _history_metric("Unmet staff-hours", str(snapshot.weekly.unmet_staff_hours))
    with ui.card().classes("schedule-workspace-card"):
        ui.label("Employee capacity").classes("schedule-workspace-card-title")
        with ui.column().classes("schedule-workspace-list"):
            for metric in snapshot.employees:
                with ui.row().classes("schedule-workspace-row"):
                    ui.label(person_label(metric.name, metric.employee_id))
                    ui.label(f"{metric.assigned_hours} / {metric.maximum_hours} h").classes(
                        "schedule-capacity-meta"
                    )
    with ui.element("div").classes("schedule-workspace-grid schedule-workspace-grid--even"):
        with ui.card().classes("schedule-workspace-card"):
            ui.label("Demand").classes("schedule-workspace-card-title")
            with ui.element("div").classes("schedule-demand-table max-h-56"):
                for cell in snapshot.state.demand or ():
                    ui.label(
                        f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00: {cell.transactions}"
                    ).classes("schedule-demand-row")
        with ui.card().classes("schedule-workspace-card"):
            ui.label("Assignments").classes("schedule-workspace-card-title")
            with ui.element("div").classes("max-h-56 overflow-auto"):
                for assignment in snapshot.state.assignments:
                    shift = next(
                        item for item in snapshot.state.shifts if item.id == assignment.shift_id
                    )
                    person = next(
                        item
                        for item in snapshot.state.employees
                        if item.id == assignment.employee_id
                    )
                    ui.label(
                        f"{WEEKDAYS[assignment.day]} "
                        f"{hour_range(shift.start_hour, shift.end_hour)} "
                        f"{person_label(person.name, person.id)}"
                    )
    if snapshot.warnings:
        with ui.card().classes("schedule-workspace-card"):
            ui.label("Captured warnings").classes("schedule-workspace-card-title")
            for warning in snapshot.warnings:
                ui.label(f"{warning.code}: {warning.message}").classes(
                    "schedule-alert schedule-alert--warning"
                )
    with ui.card().classes("schedule-workspace-card"):
        ui.label("Captured hourly analysis").classes("schedule-workspace-card-title")
        with ui.element("div").classes("schedule-hourly-table max-h-56"):
            for cell in snapshot.hourly:
                ui.label(
                    f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00 · "
                    f"{cell.transactions if cell.transactions is not None else '–'} transactions · "
                    f"{cell.required if cell.required is not None else '–'} required · "
                    f"{cell.scheduled} scheduled"
                ).classes("schedule-demand-row")


async def _open(page, snapshot_id: int) -> None:
    snapshot = await page.act(page.service.get_snapshot, page.schedule_id, snapshot_id)
    if snapshot is not None:
        page.history = snapshot
        page.pending = page.editor = None
        page.refresh()


async def _return_active(page) -> None:
    result = await page.act(page.service.get_schedule, page.schedule_id)
    if result is not None:
        page.history = None
        page.tab = "Roster"
        page.refresh()


def _history_metric(title: str, value: str) -> None:
    """Render one captured read-only metric."""
    with ui.column().classes("schedule-metric gap-0"):
        ui.label(title).classes("schedule-metric-label")
        ui.label(value).classes("schedule-metric-value")
