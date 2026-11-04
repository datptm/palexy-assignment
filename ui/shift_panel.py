"""Shift definitions, daily limit, and impact review."""

from functools import partial

from nicegui import ui

from src.domain.periods import WEEKDAYS
from src.model.scheduling import SchedulingError
from ui.presentation import finding_text, hour_range, whole_number
from ui.session import PageSession


def render_shifts(page: PageSession) -> None:
    """Render service-backed shift controls and confirmations."""
    state = page.result.state
    ui.label("Shifts").classes("text-xl font-bold")
    limit = ui.input("Daily shift limit", value=str(state.daily_shift_limit))

    async def save_limit() -> None:
        try:
            parsed = whole_number(limit.value, "daily_shift_limit", minimum=1)
            await page.act(page.service.set_daily_shift_limit, state.id, parsed)
        except SchedulingError as error:
            page.error = f"{error.code}: {error}"
            page.refresh()

    ui.button("Save daily limit", on_click=save_limit)
    editing = page.editor if page.editor and page.editor[0] == "shift_edit" else None
    old = next((item for item in state.shifts if editing and item.id == editing[1]), None)
    proposed = editing[2] if editing and len(editing) > 2 else None
    start = ui.input(
        "Start hour",
        value=str(proposed.new_start_hour if proposed else old.start_hour) if old else "",
    )
    end = ui.input(
        "End hour",
        value=str(proposed.new_end_hour if proposed else old.end_hour) if old else "",
    )

    async def submit() -> None:
        try:
            first = whole_number(start.value, "start_hour", minimum=7)
            last = whole_number(end.value, "end_hour", minimum=8)
            if old:
                preview = await page.act(
                    page.service.preview_shift_edit, state.id, old.id, first, last
                )
                if preview is not None:
                    page.editor = ("shift_edit", old.id, preview)
                    page.refresh()
            else:
                await page.act(page.service.add_shift, state.id, first, last)
        except SchedulingError as error:
            page.error = f"{error.code}: {error}"
            page.refresh()

    ui.button("Preview shift edit" if old else "Add shift", on_click=submit)
    for shift in state.shifts:
        ui.label(f"{hour_range(shift.start_hour, shift.end_hour)} · shift #{shift.id}")
        ui.button(f"Edit shift #{shift.id}", on_click=partial(_edit, page, shift.id))
        ui.button(f"Remove shift #{shift.id}", on_click=partial(_remove, page, shift.id))
    if editing and len(editing) > 2:
        preview = editing[2]
        ui.label(
            f"{len(preview.affected_assignment_ids)} assignment affected · "
            f"{preview.old_duration} → {preview.new_duration} hours"
        )
        for employee_id, day in preview.affected_employee_days:
            person = next(item for item in state.employees if item.id == employee_id)
            ui.label(f"{person.name} #{employee_id} · {WEEKDAYS[day]}")
        for finding in preview.findings:
            ui.label(finding_text(finding))
        if preview.projected_result is not None:
            projected = preview.projected_result
            ui.label(
                f"Scheduled staff-hours: {page.result.weekly.scheduled_staff_hours} → "
                f"{projected.weekly.scheduled_staff_hours}"
            )
            if page.result.weekly.covered_staff_hours is not None:
                ui.label(
                    f"Covered staff-hours: {page.result.weekly.covered_staff_hours} → "
                    f"{projected.weekly.covered_staff_hours}"
                )
            for metric in projected.employees:
                current = next(
                    item for item in page.result.employees if item.employee_id == metric.employee_id
                )
                if metric.assigned_hours != current.assigned_hours:
                    ui.label(
                        f"{metric.name} #{metric.employee_id}: "
                        f"{current.assigned_hours} → {metric.assigned_hours} h"
                    )

            async def save_shift() -> None:
                if start.value != str(preview.new_start_hour) or end.value != str(
                    preview.new_end_hour
                ):
                    page.error = "Shift proposal changed; preview again"
                    page.editor = ("shift_edit", old.id)
                    page.refresh()
                    return
                await page.act(
                    page.service.edit_shift,
                    state.id,
                    old.id,
                    preview.new_start_hour,
                    preview.new_end_hour,
                    expected_version=preview.baseline_version,
                )

            ui.button("Save shift", on_click=save_shift)
        ui.button("Cancel", on_click=lambda: _cancel(page))
    if page.editor and page.editor[0] == "shift_remove":
        _, shift_id, version, count = page.editor
        ui.label(f"Remove shift? {count} assignment" + ("s" if count != 1 else ""))
        ui.button(
            "Confirm removal",
            on_click=lambda: page.act(
                page.service.remove_shift,
                state.id,
                shift_id,
                confirmed=True,
                expected_version=version,
            ),
        )
        ui.button("Cancel", on_click=lambda: _cancel(page))


def _edit(page, shift_id: int) -> None:
    page.editor = ("shift_edit", shift_id)
    page.refresh()


def _remove(page, shift_id: int) -> None:
    fresh = page.service.get_schedule(page.schedule_id)
    count = sum(item.shift_id == shift_id for item in fresh.state.assignments)
    page.editor = ("shift_remove", shift_id, fresh.state.version, count)
    page.refresh()


def _cancel(page) -> None:
    page.editor = None
    page.refresh()
