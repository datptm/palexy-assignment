"""Committed hourly coverage, weekly totals, and warnings."""

from functools import partial

from nicegui import ui

from src.domain.periods import WEEKDAYS
from ui.presentation import finding_text, ratio
from ui.session import PageSession


def render_coverage_chart(page: PageSession) -> None:
    """Compare required and scheduled staff for every open hour in the week."""
    result = page.result
    ui.label("Demand & coverage chart").classes("schedule-card-title")
    with ui.row().classes("items-center gap-4"):
        ui.label("Required staff · navy step line").classes("schedule-capacity-meta")
        ui.label("Scheduled staff · teal bars; red marks a shortage").classes(
            "schedule-capacity-meta"
        )
    if result.weekly.total_transactions is None:
        ui.label("Coverage chart is unavailable until demand is imported").classes(
            "schedule-capacity-meta"
        )
        return
    shortage_slots = sum(cell.unmet > 0 for cell in result.hourly)
    if shortage_slots:
        ui.label(f"{shortage_slots} hourly slots have uncovered demand").classes(
            "schedule-alert schedule-alert--error"
        )
    else:
        ui.label("No uncovered staff-hours this week").classes("schedule-alert")
    options = {
        "tooltip": {"trigger": "axis"},
        "legend": {"show": False},
        "grid": {"left": 44, "right": 18, "top": 18, "bottom": 60},
        "xAxis": {
            "type": "category",
            "data": [f"{WEEKDAYS[cell.day][:3]} {cell.hour:02d}:00" for cell in result.hourly],
            "axisLabel": {"interval": 7, "rotate": 0, "hideOverlap": True},
            "axisTick": {"alignWithLabel": True},
        },
        "yAxis": {"type": "value", "minInterval": 1, "name": "Staff"},
        "series": [
            {
                "name": "Required staff",
                "type": "line",
                "step": "start",
                "symbol": "none",
                "lineStyle": {"color": "#14213d", "width": 2},
                "data": [cell.required for cell in result.hourly],
            },
            {
                "name": "Scheduled staff",
                "type": "bar",
                "barMaxWidth": 14,
                "data": [
                    {
                        "value": cell.scheduled,
                        "itemStyle": {
                            "color": "#c74646" if cell.unmet else "#159b9a",
                        },
                    }
                    for cell in result.hourly
                ],
            },
        ],
    }
    ui.echart(options).classes("w-full").style("height: 300px")


def render_analysis(page: PageSession) -> None:
    """Render service metrics without recalculating demand or policy."""
    result = page.result
    weekly = result.weekly
    if page.tab == "Warnings":
        _render_warnings(page)
        return
    with ui.column().classes("schedule-workspace-intro"):
        ui.label("Hourly Analysis & Gap Dashboard").classes("schedule-workspace-title")
        ui.label("Compare transaction demand with scheduled coverage").classes(
            "schedule-workspace-subtitle"
        )
    with ui.card().classes("schedule-workspace-card"):
        with ui.row().classes("schedule-header-row justify-between"):
            ui.label("Weekly Summary").classes("schedule-workspace-card-title")
            ui.label(f"{weekly.scheduled_staff_hours} scheduled staff-hours").classes(
                "schedule-status"
            )
        if weekly.total_transactions is None:
            ui.label("Import demand to see coverage").classes("schedule-capacity-meta")
            ui.label("Coverage unavailable").classes("schedule-status")
        else:
            with ui.element("div").classes("schedule-kpis"):
                _analysis_metric("Transactions", str(weekly.total_transactions))
                _analysis_metric("Required", f"{weekly.required_staff_hours} staff-hours")
                _analysis_metric("Assigned", f"{weekly.covered_staff_hours} staff-hours")
                _analysis_metric("Coverage", f"{ratio(weekly.coverage_rate * 100)}% coverage")
                _analysis_metric("Uncovered", f"{weekly.unmet_staff_hours} staff-hours")
                _analysis_metric("Excess", f"{weekly.excess_staff_hours} staff-hours")
            ui.label(
                f"Overall transactions per staff-hour: {ratio(weekly.transactions_per_staff_hour)}"
            ).classes("schedule-capacity-meta")
            ui.label(f"Staffed-cell average: {ratio(weekly.average_staffed_cell_ratio)}").classes(
                "schedule-capacity-meta"
            )
    if result.warnings:
        with ui.card().classes("schedule-workspace-card"):
            ui.label("Warnings to review").classes("schedule-workspace-card-title")
            for warning in result.warnings:
                ui.label(finding_text(warning)).classes(
                    "schedule-alert schedule-alert--error"
                    if warning.severity == "error"
                    else "schedule-alert schedule-alert--warning"
                )
                ui.button("Locate warning", on_click=partial(_locate, page, warning)).props(
                    "flat dense"
                )
    with ui.card().classes("schedule-workspace-card"):
        render_coverage_chart(page)
    with ui.card().classes("schedule-workspace-card"):
        ui.label("Hourly Coverage").classes("schedule-workspace-card-title")
        with ui.element("div").classes("schedule-hourly-table max-h-80"):
            with ui.element("div").classes("schedule-hourly-row schedule-hourly-head"):
                for heading in ("Day / hour", "Transactions", "Required", "Scheduled", "Gap"):
                    ui.label(heading)
            for cell in result.hourly:
                status = (
                    "Coverage unavailable"
                    if cell.required is None
                    else f"Short {cell.unmet}"
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
                scheduled = f"{cell.scheduled} scheduled"
                with (
                    ui.element("div")
                    .classes("schedule-hourly-row")
                    .props(f"id=analysis-{cell.day}-{cell.hour}")
                ):
                    ui.label(f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00")
                    ui.label(transactions)
                    ui.label(required)
                    ui.label(scheduled)
                    ui.label(
                        f"{status} · "
                        f"{ratio(cell.covered / cell.required * 100) if cell.required else '–'}% coverage"
                    )


def _render_warnings(page: PageSession) -> None:
    """Render actionable findings as compact severity-coded cards."""
    warnings = page.result.warnings
    with ui.column().classes("schedule-workspace-intro"):
        ui.label("Warnings & Inconsistencies").classes("schedule-workspace-title")
        ui.label("List of actionable errors").classes("schedule-workspace-subtitle")
    with ui.row().classes("schedule-header-row justify-between"):
        ui.label(f"{len(warnings)} Active Alerts").classes(
            "schedule-status schedule-status--warning"
        )
    if not warnings:
        ui.label("No active warnings").classes("schedule-alert schedule-alert--success")
        return
    with ui.column().classes("schedule-workspace-list"):
        for warning in warnings:
            tone = (
                "schedule-warning-card--error"
                if warning.severity == "error"
                else "schedule-warning-card--info"
                if warning.severity == "info"
                else ""
            )
            with ui.row().classes(f"schedule-workspace-row schedule-warning-card {tone}"):
                with ui.column().classes("schedule-workspace-row-main gap-1"):
                    ui.label(f"{warning.severity.upper()} · {warning.code}").classes(
                        "font-semibold"
                    )
                    ui.label(finding_text(warning))
                ui.button(
                    "Review and Adjust",
                    on_click=partial(_locate, page, warning),
                ).props("flat dense")


def _analysis_metric(title: str, value: str) -> None:
    """Render one compact weekly analysis value."""
    with ui.column().classes("schedule-metric gap-0"):
        ui.label(title).classes("schedule-metric-label")
        ui.label(value).classes("schedule-metric-value")


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
