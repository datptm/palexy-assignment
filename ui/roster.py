"""Roster-first week grid and direct assignment editor."""

from functools import partial

from nicegui import ui

from src.domain.periods import WEEKDAYS
from ui.demand_panel import render_threshold
from ui.presentation import finding_text, hour_range, person_label, ratio
from ui.session import PageSession


def render_roster(page: PageSession) -> None:
    """Show the selected committed week and its editable shift cells."""
    result = page.result
    state = result.state
    ui.label(f"Threshold: {state.threshold} · Daily shift limit: {state.daily_shift_limit}")
    render_threshold(page)
    with ui.row().classes("w-full min-w-0 items-center gap-4 flex-wrap"):
        ui.label("Imported demand" if state.demand is not None else "Demand unavailable")
        ui.label("Draft roster" if state.assignments else "Empty roster")
        ui.label(f"{len(result.warnings)} current warnings")
        ui.label(f"{result.weekly.scheduled_staff_hours} scheduled staff-hours")
        if state.demand is not None:
            ui.label(f"{result.weekly.unmet_staff_hours} unmet staff-hours")
            ui.label(f"{ratio(result.weekly.coverage_rate * 100)}% coverage").classes(
                "w-full sm:w-auto"
            )
    for warning in result.warnings:
        ui.label(finding_text(warning))
    if state.demand is None:
        if page.tab != "Demand import":
            ui.label("Import demand to see coverage")

    async def generate() -> None:
        if not state.assignments:
            await page.act(page.service.generate, state.id)
            return
        preview = await page.act(page.service.preview_generation, state.id)
        if preview is not None:
            page.pending = {"kind": "generation", "preview": preview}
            page.refresh()

    ui.button("Auto-schedule", on_click=generate)
    if page.pending and page.pending["kind"] == "generation":
        _replacement(page)
    if not state.shifts:
        ui.label("No shifts configured. Add a shift before generating.")
    with ui.element("div").classes("w-full max-w-full min-w-0 overflow-x-auto"):
        with ui.row().classes("min-w-max gap-4"):
            for day, name in enumerate(WEEKDAYS):
                with ui.column().classes("min-w-40").props(f"id=roster-day-{day}"):
                    ui.label(name).classes("font-bold")
                    for shift in sorted(
                        state.shifts,
                        key=lambda item: (item.start_hour, item.end_hour, item.id),
                    ):
                        slot = next(
                            item
                            for item in result.roster
                            if item.day == day and item.shift_id == shift.id
                        )
                        ui.button(
                            f"{name} {hour_range(shift.start_hour, shift.end_hour)}",
                            on_click=partial(_open_cell, page, day, shift.id),
                        ).props(f"id=roster-cell-{day}-{shift.id}")
                        if slot.employees:
                            for person in slot.employees:
                                ui.label(person_label(person.name, person.employee_id))
                                ui.label(f"{person.assigned_hours} / {person.maximum_hours} h")
                            for assignment in state.assignments:
                                if assignment.day == day and assignment.shift_id == shift.id:
                                    ui.button(
                                        "Remove assignment",
                                        on_click=partial(
                                            page.act,
                                            page.service.remove_assignment,
                                            state.id,
                                            assignment.id,
                                        ),
                                    )
                        else:
                            ui.label("Unassigned")
    if page.editor and page.editor[0] == "cell":
        _assignment_editor(page)


def _open_cell(page, day: int, shift_id: int) -> None:
    preview = page.service.preview_assignment_options(page.schedule_id, day, shift_id)
    page.editor = ("cell", day, shift_id, preview, None, None)
    page.refresh()


def _assignment_editor(page) -> None:
    _, day, shift_id, preview, selected_id, replacing_id = page.editor
    state = page.result.state
    shift = next(item for item in state.shifts if item.id == shift_id)
    ui.label(f"Edit {WEEKDAYS[day]} {hour_range(shift.start_hour, shift.end_hour)}")
    current = tuple(
        item for item in state.assignments if item.day == day and item.shift_id == shift_id
    )
    if replacing_id is not None:
        original = next(item for item in state.assignments if item.id == replacing_id)
        original_shift = next(item for item in state.shifts if item.id == original.shift_id)
        original_person = next(item for item in state.employees if item.id == original.employee_id)
        ui.label(
            f"Moving {person_label(original_person.name, original_person.id)} from "
            f"{WEEKDAYS[original.day]} "
            f"{hour_range(original_shift.start_hour, original_shift.end_hour)}"
        )
        ui.label("Choose a destination day and shift, then an employee")
        with ui.element("div").classes("max-h-36 overflow-auto"):
            for destination_day, day_name in enumerate(WEEKDAYS):
                for destination_shift in state.shifts:
                    ui.button(
                        f"Destination {day_name} "
                        f"{hour_range(destination_shift.start_hour, destination_shift.end_hour)}",
                        on_click=partial(
                            _choose_destination,
                            page,
                            destination_day,
                            destination_shift.id,
                            replacing_id,
                        ),
                    )
    for assignment in current:
        person = next(item for item in state.employees if item.id == assignment.employee_id)
        ui.label(person_label(person.name, person.id))
        ui.button(
            "Remove assignment",
            on_click=partial(page.act, page.service.remove_assignment, state.id, assignment.id),
        )
        ui.button(
            "Reassign",
            on_click=partial(_start_reassign, page, day, shift_id, assignment.id),
        )
    names = [item.name for item in state.employees]
    for option in preview.options:
        person = next(item for item in state.employees if item.id == option.employee_id)
        label = (
            person_label(person.name, person.id) if names.count(person.name) > 1 else person.name
        )
        choice_button = ui.button(
            label,
            on_click=partial(_choose, page, person.id),
        )
        if option.blocked:
            choice_button.disable()
            ui.label("Blocked: " + "; ".join(finding_text(f) for f in option.findings))
    if selected_id is not None:
        option = next(item for item in preview.options if item.employee_id == selected_id)
        if replacing_id is None:
            ui.label(
                f"{option.current_hours} + {shift.end_hour - shift.start_hour} = "
                f"{option.projected_hours} h; limit {option.weekly_max_hours} h"
            )
        else:
            ui.label(
                f"{option.current_hours} → {option.projected_hours} h; "
                f"limit {option.weekly_max_hours} h"
            )
        ui.label(
            f"Daily shifts: {option.current_daily_shift_count} → "
            f"{option.projected_daily_shift_count}; limit {option.daily_shift_limit}"
        )
        if option.after_weekly is not None and option.before_weekly.covered_staff_hours is not None:
            ui.label(
                f"Covered staff-hours: {option.before_weekly.covered_staff_hours} → "
                f"{option.after_weekly.covered_staff_hours}"
            )
        elif option.after_weekly is not None:
            ui.label("Demand unavailable; coverage cannot be projected")
        if option.after_hourly is not None and option.before_weekly.covered_staff_hours is not None:
            with ui.element("div").classes("max-h-36 overflow-auto"):
                for before_hour, after_hour in zip(
                    option.before_hourly, option.after_hourly, strict=True
                ):
                    ui.label(
                        f"{WEEKDAYS[before_hour.day]} {before_hour.hour:02d}:00: "
                        f"{before_hour.scheduled} → {after_hour.scheduled} scheduled, "
                        f"{before_hour.covered} → {after_hour.covered} covered"
                    )
        for finding in option.findings:
            ui.label(finding_text(finding))
        if not option.blocked:
            if replacing_id is None:
                ui.button(
                    "Add assignment",
                    on_click=lambda: page.act(
                        page.service.add_assignment,
                        state.id,
                        selected_id,
                        day,
                        shift_id,
                        expected_version=preview.baseline_version,
                    ),
                )
            else:
                ui.button(
                    "Save reassignment",
                    on_click=lambda: page.act(
                        page.service.reassign_assignment,
                        state.id,
                        replacing_id,
                        selected_id,
                        day,
                        shift_id,
                        expected_version=preview.baseline_version,
                    ),
                )


def _choose(page, employee_id: int) -> None:
    mode, day, shift_id, preview, _, replacing_id = page.editor
    page.editor = (mode, day, shift_id, preview, employee_id, replacing_id)
    page.refresh()


def _choose_destination(page, day: int, shift_id: int, assignment_id: int) -> None:
    preview = page.service.preview_assignment_options(
        page.schedule_id, day, shift_id, replacing_assignment_id=assignment_id
    )
    page.editor = ("cell", day, shift_id, preview, None, assignment_id)
    page.refresh()


def _start_reassign(page, day: int, shift_id: int, assignment_id: int) -> None:
    preview = page.service.preview_assignment_options(
        page.schedule_id,
        day,
        shift_id,
        replacing_assignment_id=assignment_id,
    )
    page.editor = ("cell", day, shift_id, preview, None, assignment_id)
    page.refresh()


def _replacement(page) -> None:
    pending = page.pending
    preview = pending["preview"]
    ui.label(
        f"This replaces all assignments: {preview.removed_assignments} removed, "
        f"{preview.added_assignments} added; "
        f"{preview.draft.weekly.unmet_staff_hours} unmet staff-hours"
    )
    if preview.draft.weekly.coverage_rate is not None:
        ui.label(f"Proposed coverage: {ratio(preview.draft.weekly.coverage_rate * 100)}%")
    with ui.element("div").classes("max-h-44 overflow-auto"):
        for slot in preview.draft.roster:
            if slot.employees:
                ui.label(
                    f"{WEEKDAYS[slot.day]} {hour_range(slot.start_hour, slot.end_hour)}: "
                    + ", ".join(
                        person_label(person.name, person.employee_id) for person in slot.employees
                    )
                )
    ui.button(
        "Confirm replacement",
        on_click=lambda: page.act(
            page.service.confirm_generation, page.schedule_id, preview.token, confirmed=True
        ),
    )
    ui.button("Cancel", on_click=lambda: _cancel(page))


def _cancel(page) -> None:
    page.pending = None
    page.refresh()
