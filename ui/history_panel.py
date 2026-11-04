"""Read-only prior state inspection."""

from functools import partial

from nicegui import ui

from src.domain.periods import WEEKDAYS
from ui.presentation import hour_range, person_label, ratio
from ui.session import PageSession


def render_history(page: PageSession) -> None:
    """Show schedule-owned snapshots without restore or edit actions."""
    ui.label("History").classes("text-xl font-bold")
    if page.history is None:
        for summary in page.history_list or ():
            ui.button(
                f"{summary.reason} · {summary.captured_at_utc} · version {summary.prior_version}",
                on_click=partial(_open, page, summary.id),
            )
        return
    snapshot = page.history
    ui.label("Historical / read-only")
    ui.label(f"Threshold: {snapshot.state.threshold}")
    ui.label(f"Daily shift limit: {snapshot.state.daily_shift_limit}")
    ui.label(f"{snapshot.weekly.scheduled_staff_hours} scheduled staff-hours")
    ui.label(f"Coverage: {ratio(snapshot.weekly.coverage_rate)}")
    ui.label(f"Required staff-hours: {snapshot.weekly.required_staff_hours}")
    ui.label(f"Unmet staff-hours: {snapshot.weekly.unmet_staff_hours}")
    ui.label(
        f"Overall transactions per staff-hour: {ratio(snapshot.weekly.transactions_per_staff_hour)}"
    )
    for metric in snapshot.employees:
        ui.label(
            f"{person_label(metric.name, metric.employee_id)}: "
            f"{metric.assigned_hours} / {metric.maximum_hours} h"
        )
    for cell in snapshot.state.demand or ():
        ui.label(f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00: {cell.transactions}")
    for assignment in snapshot.state.assignments:
        shift = next(item for item in snapshot.state.shifts if item.id == assignment.shift_id)
        person = next(
            item for item in snapshot.state.employees if item.id == assignment.employee_id
        )
        ui.label(
            f"{WEEKDAYS[assignment.day]} {hour_range(shift.start_hour, shift.end_hour)} "
            f"{person_label(person.name, person.id)}"
        )
    for warning in snapshot.warnings:
        ui.label(f"{warning.code}: {warning.message}")
    with ui.element("div").classes("max-h-48 overflow-auto"):
        for cell in snapshot.hourly:
            ui.label(
                f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00 · "
                f"{cell.transactions if cell.transactions is not None else '–'} transactions · "
                f"{cell.required if cell.required is not None else '–'} required · "
                f"{cell.scheduled} scheduled"
            )
    ui.button("Return to active", on_click=lambda: _return_active(page))


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
