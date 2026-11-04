"""Employee maintenance and workload controls."""

from functools import partial

from nicegui import ui

from src.model.scheduling import SchedulingError
from ui.presentation import person_label, whole_number
from ui.session import PageSession


def render_staff(page: PageSession) -> None:
    """Render employee forms and deliberate version-bound removal."""
    state = page.result.state
    generation_employees = (
        {}
        if page.result.generation_diagnostics is None
        else {item.employee_id: item for item in page.result.generation_diagnostics.employees}
    )
    editing = page.editor if page.editor and page.editor[0] == "staff_edit" else None
    employee = next((item for item in state.employees if editing and item.id == editing[1]), None)
    with ui.column().classes("schedule-workspace-intro"):
        ui.label("Staff Management").classes("schedule-workspace-title")
        ui.label("Add & edit employees").classes("schedule-workspace-subtitle")

    async def save() -> None:
        page.staff_form = {"name": name.value, "maximum": maximum.value}
        try:
            limit = whole_number(maximum.value, "weekly_max_hours")
            if employee:
                result = await page.act(
                    page.service.edit_employee, state.id, employee.id, name.value, limit
                )
            else:
                result = await page.act(page.service.add_employee, state.id, name.value, limit)
            if result is not None:
                page.staff_form = {}
                page.refresh()
        except SchedulingError as error:
            page.error = f"{error.code}: {error}"
            page.refresh()

    with ui.element("div").classes("schedule-workspace-grid"):
        with ui.card().classes("schedule-workspace-card"):
            ui.label("Edit Employee" if employee else "Add New Employee").classes(
                "schedule-workspace-card-title"
            )
            name = ui.input(
                "Employee name",
                value=page.staff_form.get("name", employee.name if employee else ""),
            )
            maximum = ui.input(
                "Weekly maximum",
                value=page.staff_form.get(
                    "maximum", str(employee.weekly_max_hours) if employee else ""
                ),
            )
            ui.button("Save employee" if employee else "Add employee", on_click=save).props(
                "unelevated"
            )
        with ui.card().classes("schedule-workspace-card"):
            with ui.row().classes("schedule-header-row justify-between"):
                ui.label("Employee list & capacity").classes("schedule-workspace-card-title")
                ui.label(f"{len(page.result.employees)} employees").classes("schedule-status")
            if not page.result.employees:
                ui.label("Add staff to review weekly capacity").classes("schedule-capacity-meta")
            with ui.column().classes("schedule-workspace-list"):
                for metric in page.result.employees:
                    label = person_label(metric.name, metric.employee_id)
                    utilization = metric.utilization
                    percentage = 0 if utilization is None else min(100, max(0, utilization * 100))
                    fill_class = (
                        "schedule-capacity-fill schedule-capacity-fill--warning"
                        if utilization is not None and utilization > 1
                        else "schedule-capacity-fill"
                    )
                    with ui.column().classes("schedule-workspace-row"):
                        with ui.row().classes("schedule-header-row justify-between"):
                            ui.button(
                                label,
                                on_click=partial(_edit, page, metric.employee_id),
                            ).props(f"id=staff-{metric.employee_id} flat dense")
                            ui.button(
                                f"Remove {label}",
                                on_click=partial(_confirm, page, metric.employee_id),
                            ).props("flat dense")
                        ui.label(
                            f"{metric.assigned_hours} / {metric.maximum_hours} h · "
                            f"{'N/A' if utilization is None else f'{utilization * 100:.0f}%'}"
                        ).classes("schedule-capacity-meta")
                        generation_metric = generation_employees.get(metric.employee_id)
                        if generation_metric is not None:
                            ui.label(
                                f"Effective capacity: {generation_metric.effective_capacity} h"
                            ).classes("schedule-capacity-meta")
                            ui.label(
                                f"Target hours: {generation_metric.target_hours:.1f} h"
                            ).classes("schedule-capacity-meta")
                        with ui.element("div").classes("schedule-capacity-track"):
                            ui.element("div").classes(fill_class).style(f"width: {percentage:.0f}%")
                        overage = max(0, metric.assigned_hours - metric.maximum_hours)
                        if overage:
                            ui.label(f"{overage} h over weekly maximum").classes(
                                "schedule-capacity-meta text-amber-800"
                            )
            if page.editor and page.editor[0] == "staff_remove":
                _, employee_id, version, count = page.editor
                with ui.card().classes("schedule-workspace-card schedule-warning-card"):
                    ui.label(f"Remove employee? {count} assignment" + ("s" if count != 1 else ""))
                    ui.button(
                        "Confirm removal",
                        on_click=lambda: page.act(
                            page.service.remove_employee,
                            state.id,
                            employee_id,
                            confirmed=True,
                            expected_version=version,
                        ),
                    ).props("unelevated color=negative")
                    ui.button("Cancel", on_click=lambda: _cancel(page)).props("flat")


def _edit(page, employee_id: int) -> None:
    page.editor = ("staff_edit", employee_id)
    page.staff_form = {}
    page.refresh()


def _confirm(page, employee_id: int) -> None:
    fresh = page.service.get_schedule(page.schedule_id)
    count = sum(item.employee_id == employee_id for item in fresh.state.assignments)
    page.editor = ("staff_remove", employee_id, fresh.state.version, count)
    page.refresh()


def _cancel(page) -> None:
    page.editor = None
    page.refresh()
