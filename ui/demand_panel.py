"""Bounded CSV import and version-bound demand replacement."""

from nicegui import ui

from src.domain.periods import WEEKDAYS
from src.model.scheduling import SchedulingError
from ui.presentation import finding_text, hour_range, person_label, ratio, whole_number
from ui.session import PageSession

MAX_UPLOAD_BYTES = 1024 * 1024


def render_threshold(page: PageSession) -> None:
    """Show direct pre-import setting or post-import refresh proposal."""
    state = page.result.state

    def changed() -> None:
        if page.pending and page.pending.get("kind") == "refresh":
            page.pending = None

    async def submit() -> None:
        try:
            value = whole_number(field.value, "threshold", minimum=1)
            if state.demand is None:
                await page.act(page.service.set_threshold, state.id, value)
            else:
                preview = await page.act(page.service.preview_refresh, state.id, threshold=value)
                if preview is not None:
                    page.pending = {
                        "kind": "refresh",
                        "preview": preview,
                        "threshold": value,
                        "csv_bytes": None,
                        "schedule_id": state.id,
                    }
                    page.refresh()
        except SchedulingError as error:
            page.error = f"{error.code}: {error}"
            page.refresh()

    with ui.row().classes("w-full min-w-0 items-end gap-2 flex-wrap"):
        field = ui.input("Threshold", value=str(state.threshold), on_change=changed).classes("w-28")
        ui.button(
            "Save threshold" if state.demand is None else "Preview threshold change",
            on_click=submit,
        )
    ui.label("Transactions per required employee-hour; minimum one per open hour").classes(
        "text-xs text-gray-600 max-w-full"
    ).style("width: 100%; white-space: normal; overflow-wrap: anywhere")
    if page.pending and page.pending["kind"] == "refresh":
        render_refresh(page)


def render_demand(page: PageSession) -> None:
    """Validate uploaded bytes before import or replacement review."""
    state = page.result.state
    with ui.column().classes("schedule-workspace-intro"):
        ui.label("Import Demand").classes("schedule-workspace-title")
        ui.label("Upload and validate hourly transaction demand").classes(
            "schedule-workspace-subtitle"
        )

    async def upload(event) -> None:
        selected, epoch = page.schedule_id, page.epoch
        if event.file.size() > MAX_UPLOAD_BYTES:
            page.error = "CSV exceeds 1 MiB"
            page.refresh()
            return
        chunks = []
        size = 0
        async for chunk in event.file.iterate(chunk_size=64 * 1024):
            if (selected, epoch) != (page.schedule_id, page.epoch):
                return
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                page.error = "CSV exceeds 1 MiB"
                page.refresh()
                return
            chunks.append(chunk)
        data = b"".join(chunks)
        if (selected, epoch) != (page.schedule_id, page.epoch):
            return
        parsed = await page.act(page.service.validate_import, data)
        if parsed is not None:
            page.pending = {"kind": "upload", "csv_bytes": data, "parsed": parsed}
            page.refresh()

    def rejected() -> None:
        page.error = "CSV exceeds 1 MiB or was rejected"
        page.refresh()

    with ui.card().classes("schedule-workspace-card"):
        ui.label("Upload Demand File").classes("schedule-workspace-card-title")
        ui.label(
            "CSV: one hour column and seven English weekday columns; "
            "07:00–22:00 starts, 112 day/hour counts."
        ).classes("schedule-capacity-meta")
        with ui.element("div").classes("schedule-upload-card"):
            ui.label("Drop a CSV here, or use the file picker").classes(
                "schedule-workspace-card-title"
            )
            ui.upload(
                on_upload=upload,
                on_rejected=rejected,
                auto_upload=True,
                max_file_size=MAX_UPLOAD_BYTES,
            ).props("accept=.csv")
    if page.pending and page.pending["kind"] == "upload":
        pending = page.pending
        parsed = pending["parsed"]
        with ui.card().classes("schedule-workspace-card"):
            with ui.row().classes("schedule-header-row justify-between"):
                ui.label("Demand Preview").classes("schedule-workspace-card-title")
                ui.label(f"{len(parsed.cells)} hourly rows validated").classes("schedule-status")
            with ui.element("div").classes("schedule-demand-table max-h-56"):
                for cell in parsed.cells:
                    ui.label(
                        f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00: {cell.transactions}"
                    ).classes("schedule-demand-row")
            for finding in parsed.findings:
                ui.label(finding_text(finding)).classes(
                    "schedule-alert schedule-alert--warning"
                    if finding.severity == "warning"
                    else "schedule-alert schedule-alert--error"
                )

        async def commit() -> None:
            if state.demand is None:
                await page.act(page.service.import_initial, state.id, pending["csv_bytes"])
            else:
                preview = await page.act(
                    page.service.preview_refresh,
                    state.id,
                    csv_bytes=pending["csv_bytes"],
                )
                if preview is not None:
                    page.pending = {
                        "kind": "refresh",
                        "preview": preview,
                        "csv_bytes": pending["csv_bytes"],
                        "threshold": None,
                        "schedule_id": state.id,
                    }
                    page.refresh()

        ui.button(
            "Import demand" if state.demand is None else "Preview demand replacement",
            on_click=commit,
        ).props("unelevated")
    elif state.demand is not None:
        with ui.card().classes("schedule-workspace-card"):
            with ui.row().classes("schedule-header-row justify-between"):
                ui.label("Current Demand").classes("schedule-workspace-card-title")
                ui.label(f"{len(state.demand)} hourly rows").classes("schedule-status")
            with ui.element("div").classes("schedule-demand-table max-h-56"):
                for cell in state.demand:
                    ui.label(
                        f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00: {cell.transactions}"
                    ).classes("schedule-demand-row")


def render_refresh(page: PageSession) -> None:
    """Review and confirm the exact signed replacement proposal."""
    pending = page.pending
    preview = pending["preview"]
    with ui.card().classes("schedule-workspace-card schedule-warning-card"):
        ui.label("Review Demand Replacement").classes("schedule-workspace-card-title")
        ui.label(f"Current threshold: {page.result.state.threshold}")
        if pending["threshold"] is not None:
            ui.label(f"Proposed threshold: {pending['threshold']}")
        else:
            ui.label("Proposed demand: 112 day/hour counts")
            with ui.element("div").classes("schedule-demand-table max-h-44"):
                for cell in preview.draft.state.demand:
                    ui.label(
                        f"{WEEKDAYS[cell.day]} {cell.hour:02d}:00: {cell.transactions}"
                    ).classes("schedule-demand-row")
        ui.label(
            f"This replaces all assignments, including manual edits, and saves the prior "
            f"state in read-only history. {preview.removed_assignments} current; "
            f"{preview.added_assignments} proposed; "
            f"{preview.draft.weekly.unmet_staff_hours} unmet staff-hours."
        ).classes("schedule-alert schedule-alert--warning")
        if preview.draft.weekly.coverage_rate is not None:
            ui.label(f"Proposed coverage: {ratio(preview.draft.weekly.coverage_rate * 100)}%")
        diagnostics = preview.draft.generation_diagnostics
        if diagnostics is not None:
            shifts_by_id = {shift.id: shift for shift in preview.draft.state.shifts}
            ui.label("Generation diagnostics").classes("schedule-workspace-card-title")
            ui.label("Unavoidable shortage lower bound")
            ui.label(diagnostics.lower_bound_message)
            ui.label(
                f"Optimizer cost: C={diagnostics.primary_cost}; "
                f"fairness F={diagnostics.fairness_cost}"
            )
            for shortfall in diagnostics.shortfalls:
                location = WEEKDAYS[shortfall.day]
                if shortfall.hour is not None:
                    location += f" {shortfall.hour:02d}:00"
                elif shortfall.shift_id is not None:
                    shift = shifts_by_id[shortfall.shift_id]
                    location += f" {hour_range(shift.start_hour, shift.end_hour)}"
                ui.label(
                    f"{shortfall.reason}: {location}, "
                    f"{shortfall.unmet_staff_hours} unmet staff-hours"
                )
            for flag in diagnostics.flags:
                ui.label(flag)
        with ui.element("div").classes("max-h-44 overflow-auto"):
            for slot in preview.draft.roster:
                if slot.employees:
                    ui.label(
                        f"{WEEKDAYS[slot.day]} {hour_range(slot.start_hour, slot.end_hour)}: "
                        + ", ".join(
                            person_label(person.name, person.employee_id)
                            for person in slot.employees
                        )
                    )

    async def confirm() -> None:
        if page.pending is not pending or pending["schedule_id"] != page.schedule_id:
            page.pending = None
            page.error = "Preview changed; review the proposal again"
            page.refresh()
            return
        await page.act(
            page.service.confirm_refresh,
            page.schedule_id,
            preview.token,
            threshold=pending["threshold"],
            csv_bytes=pending["csv_bytes"],
            confirmed=True,
        )

    ui.button("Confirm replacement", on_click=confirm)
    ui.button("Cancel", on_click=lambda: _cancel(page)).props("flat")


def _cancel(page) -> None:
    page.pending = None
    page.refresh()
