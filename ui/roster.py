"""Roster-first week grid and direct assignment editor."""

from functools import partial

from nicegui import ui

from src.domain.periods import WEEKDAYS
from ui.analysis_panel import render_coverage_chart
from ui.demand_panel import render_threshold
from ui.presentation import finding_text, hour_range, person_label, ratio
from ui.session import PageSession


def render_roster(page: PageSession) -> None:
    """Show the selected committed week and its editable shift cells."""
    result = page.result
    state = result.state
    with ui.card().classes("schedule-card gap-4"):
        with ui.row().classes("schedule-header-row justify-between"):
            ui.label("Monday–Sunday weekly roster").classes("schedule-card-title")

            async def generate() -> None:
                if not state.assignments:
                    await page.act(page.service.generate, state.id)
                    return
                preview = await page.act(page.service.preview_generation, state.id)
                if preview is not None:
                    page.pending = {"kind": "generation", "preview": preview}
                    page.refresh()

            ui.button("Auto-schedule", on_click=generate).props("unelevated")
        with ui.row().classes("schedule-header-row"):
            ui.label(f"Threshold: {state.threshold}").classes("schedule-status")
            ui.label(f"Daily shift limit: {state.daily_shift_limit}").classes("schedule-status")
            ui.label("Draft roster" if state.assignments else "Empty roster").classes(
                "schedule-status"
            )
            ui.label(
                "Imported demand" if state.demand is not None else "Demand unavailable"
            ).classes("schedule-status")
        render_threshold(page)
        with ui.element("div").classes("schedule-kpis"):
            coverage = (
                f"{ratio(result.weekly.coverage_rate * 100)}%"
                if result.weekly.coverage_rate is not None
                else "Unavailable"
            )
            coverage_detail = (
                "of required staff-hours"
                if state.demand is not None
                else "Coverage appears after CSV import"
            )
            _metric_card(
                "Coverage",
                coverage,
                coverage_detail,
                "healthy" if result.weekly.coverage_rate == 1 else "warning",
            )
            _metric_card(
                "Uncovered hours",
                (str(result.weekly.unmet_staff_hours) if state.demand is not None else "—"),
                f"{result.weekly.unmet_staff_hours} unmet staff-hours across the week"
                if state.demand is not None
                else "Hours unavailable until demand is imported",
                "critical" if result.weekly.unmet_staff_hours else "",
            )
            _metric_card(
                "Scheduled hours",
                str(result.weekly.scheduled_staff_hours),
                "staff-hours assigned",
            )
            _metric_card(
                "Warnings",
                str(len(result.warnings)),
                "current schedule findings",
                "warning" if result.warnings else "healthy",
            )
        if result.warnings:
            with ui.column().classes("gap-1 w-full"):
                ui.label("Warnings to review").classes("schedule-card-title")
                for warning in result.warnings:
                    tone = (
                        "schedule-alert--error"
                        if warning.severity == "error"
                        else "schedule-alert--warning"
                        if warning.severity == "warning"
                        else ""
                    )
                    ui.label(finding_text(warning)).classes(f"schedule-alert {tone}")
    if state.demand is None:
        if page.tab != "Demand import":
            ui.label("Import demand to see coverage")

    if not state.shifts:
        ui.label("No shifts configured. Add a shift before generating.").classes("schedule-alert")
    with ui.element("div").classes("w-full max-w-full min-w-0 overflow-x-auto"):
        with ui.element("div").classes("schedule-grid-scroll"):
            with ui.element("div").classes("schedule-grid"):
                ui.label("Shift").classes("schedule-grid-heading")
                for day, name in enumerate(WEEKDAYS):
                    with ui.column().classes("schedule-grid-heading").props(f"id=roster-day-{day}"):
                        ui.label(name)
                shifts = sorted(
                    state.shifts,
                    key=lambda item: (item.start_hour, item.end_hour, item.id),
                )
                for shift in shifts:
                    with ui.column().classes("schedule-grid-shift"):
                        ui.label(hour_range(shift.start_hour, shift.end_hour))
                    for day, name in enumerate(WEEKDAYS):
                        slot = next(
                            item
                            for item in result.roster
                            if item.day == day and item.shift_id == shift.id
                        )
                        with ui.column().classes("schedule-grid-cell"):
                            ui.button(
                                f"{name} {hour_range(shift.start_hour, shift.end_hour)}",
                                on_click=partial(_open_cell, page, day, shift.id),
                            ).props(f"id=roster-cell-{day}-{shift.id}").props("flat")
                            if slot.employees:
                                for person in slot.employees:
                                    assignment = next(
                                        item
                                        for item in state.assignments
                                        if item.day == day
                                        and item.shift_id == shift.id
                                        and item.employee_id == person.employee_id
                                    )
                                    with ui.row().classes("schedule-assignee-row"):
                                        ui.label(
                                            person_label(person.name, person.employee_id)
                                        ).classes("schedule-assignee")
                                        remove_button = ui.button(
                                            icon="close",
                                            on_click=partial(
                                                page.act,
                                                page.service.remove_assignment,
                                                state.id,
                                                assignment.id,
                                            ),
                                        ).props(
                                            f"id=remove-assignment-{assignment.id} flat round dense"
                                        )
                                        remove_button.props["aria-label"] = (
                                            f"Remove assignment for {person.name}"
                                        )
                                        remove_button.classes("schedule-assignee-remove")
                                        remove_button.tooltip(
                                            f"Remove assignment for {person.name}"
                                        ).mark(f"remove-assignment-{assignment.id}")
                                    ui.label(
                                        f"{person.assigned_hours} / {person.maximum_hours} h"
                                    ).classes("schedule-capacity-meta")
                            else:
                                ui.label("Unassigned").classes("schedule-empty")
    if page.editor and page.editor[0] == "cell":
        editor = ui.dialog().props("persistent")
        with editor, ui.card().classes("schedule-card schedule-workspace-dialog gap-2"):
            with ui.row().classes("schedule-header-row justify-between"):
                ui.label("Edit assignment").classes("schedule-card-title")
                ui.button(
                    "Close",
                    icon="close",
                    on_click=lambda: _close_editor(page),
                ).props("flat")
            _assignment_editor(page)
        editor.open()
    elif page.pending and page.pending["kind"] == "generation":
        confirmation = ui.dialog().props("persistent")
        with confirmation, ui.card().classes("schedule-card schedule-workspace-dialog gap-2"):
            ui.label("Review regenerated roster").classes("schedule-card-title")
            _replacement(page)
        confirmation.open()
    with ui.card().classes("schedule-card gap-3 w-full"):
        render_coverage_chart(page)


def _metric_card(title: str, value: str, detail: str, tone: str = "") -> None:
    """Render one compact summary metric with a semantic status tone."""
    tone_class = f" schedule-metric--{tone}" if tone else ""
    with ui.column().classes(f"schedule-metric{tone_class} gap-0"):
        ui.label(title).classes("schedule-metric-label")
        ui.label(value).classes("schedule-metric-value")
        ui.label(detail).classes("schedule-metric-detail")


def _close_editor(page: PageSession) -> None:
    """Close the current assignment dialog without changing the schedule."""
    page.editor = None
    page.refresh()


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
