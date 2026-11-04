"""Employee maintenance and workload controls."""

from functools import partial

from nicegui import ui

from src.model.scheduling import SchedulingError
from ui.presentation import person_label, whole_number
from ui.session import PageSession


def render_staff(page: PageSession) -> None:
    """Render employee forms and deliberate version-bound removal."""
    state = page.result.state
    ui.label("Staff").classes("text-xl font-bold")
    editing = page.editor if page.editor and page.editor[0] == "staff_edit" else None
    employee = next((item for item in state.employees if editing and item.id == editing[1]), None)
    name = ui.input(
        "Employee name", value=page.staff_form.get("name", employee.name if employee else "")
    )
    maximum = ui.input(
        "Weekly maximum",
        value=page.staff_form.get("maximum", str(employee.weekly_max_hours) if employee else ""),
    )

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

    ui.button("Save employee" if employee else "Add employee", on_click=save)
    for metric in page.result.employees:
        label = person_label(metric.name, metric.employee_id)
        utilization = "N/A" if metric.utilization is None else f"{metric.utilization * 100:.0f}%"
        ui.button(
            label,
            on_click=partial(_edit, page, metric.employee_id),
        ).props(f"id=staff-{metric.employee_id}")
        ui.label(f"{metric.assigned_hours} / {metric.maximum_hours} h · {utilization}")
        ui.button(
            f"Remove {label}",
            on_click=partial(_confirm, page, metric.employee_id),
        )
    if page.editor and page.editor[0] == "staff_remove":
        _, employee_id, version, count = page.editor
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
        )
        ui.button("Cancel", on_click=lambda: _cancel(page))


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
