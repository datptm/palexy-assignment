"""Committed hourly coverage, weekly totals, and warnings."""

from functools import partial

from nicegui import ui

from src.domain.periods import WEEKDAYS
from ui.presentation import finding_text, ratio
from ui.session import PageSession


def render_analysis(page: PageSession) -> None:
    """Render service metrics without recalculating demand or policy."""
    result = page.result
    weekly = result.weekly
    if weekly.total_transactions is None:
        ui.label("Import demand to see coverage")
    else:
        ui.label(f"{weekly.total_transactions} transactions")
        ui.label(f"{weekly.required_staff_hours} required staff-hours")
        ui.label(f"{weekly.covered_staff_hours} covered staff-hours")
        ui.label(f"{weekly.unmet_staff_hours} unmet staff-hours")
        ui.label(f"{weekly.excess_staff_hours} excess staff-hours")
        ui.label(f"{ratio(weekly.coverage_rate * 100)}% coverage")
        ui.label(
            f"Overall transactions per staff-hour: {ratio(weekly.transactions_per_staff_hour)}"
        )
        ui.label(f"Staffed-cell average: {ratio(weekly.average_staffed_cell_ratio)}")
    ui.label(f"{weekly.scheduled_staff_hours} scheduled staff-hours")
    for warning in result.warnings:
        ui.label(finding_text(warning))
        ui.button("Locate warning", on_click=partial(_locate, page, warning))
    if page.tab == "Warnings":
        return
    with ui.element("div").classes("w-full max-h-96 overflow-auto"):
        for cell in result.hourly:
            status = (
                "Coverage unavailable"
                if cell.required is None
                else f"Shortage {cell.unmet}"
                if cell.unmet
                else f"Excess {cell.excess}"
                if cell.excess
                else "Covered"
            )
            transactions = (
                "Demand unavailable"
                if cell.transactions is None
                else f"{cell.transactions} transactions"
            )
            required = "– required" if cell.required is None else f"{cell.required} required"
            ui.label(
                f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00 · {transactions} · "
                f"{required} · {cell.scheduled} scheduled · {status} · "
                f"{ratio(cell.covered / cell.required * 100) if cell.required else '–'}% coverage · "
                f"{ratio(cell.transactions_per_staff_hour)} transactions per staff-hour"
            ).props(f"id=analysis-{cell.day}-{cell.hour}")


def _locate(page, warning) -> None:
    details = warning.details
    day = warning.day if warning.day is not None else details.get("day")
    hour = warning.hour if warning.hour is not None else details.get("hour")
    employee_id = details.get("employee_id")
    anchor = None
    if type(day) is int and 0 <= day <= 6 and type(hour) is int and 7 <= hour <= 22:
        page.tab = "Hourly analysis"
        page.location_hint = f"{WEEKDAYS[day]} {hour:02d}:00"
        anchor = f"analysis-{day}-{hour}"
    elif type(day) is int and 0 <= day <= 6:
        page.tab = "Roster"
        page.location_hint = WEEKDAYS[day]
        anchor = f"roster-day-{day}"
    elif type(employee_id) is int and employee_id > 0:
        page.tab = "Staff"
        person = next(
            (item for item in page.result.state.employees if item.id == employee_id), None
        )
        page.location_hint = person.name if person is not None else f"staff #{employee_id}"
        anchor = f"staff-{employee_id}"
    else:
        page.location_hint = finding_text(warning)
    page.refresh()
    if anchor:
        page.client.run_javascript(
            f"document.getElementById('{anchor}')?.scrollIntoView({{block: 'center'}})"
        )
