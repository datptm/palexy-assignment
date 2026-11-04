"""Browser entry point for the staff scheduling manager."""

from functools import partial

from nicegui import ui

from src.model.scheduling import SchedulingError
from ui.analysis_panel import render_analysis
from ui.demand_panel import render_demand
from ui.history_panel import render_history
from ui.roster import render_roster
from ui.session import PageSession
from ui.shift_panel import render_shifts
from ui.staff_panel import render_staff


@ui.page("/")
async def home_page() -> None:
    """Build one page-local schedule workflow from persisted service data."""
    page = PageSession()
    page.schedules = page.service.list_schedules()
    if page.schedules:
        page.schedule_id = page.schedules[0].id
        page.result = page.service.get_schedule(page.schedule_id)

    @ui.refreshable
    def content() -> None:
        with (
            ui.column()
            .classes("p-4 gap-2")
            .style("width: 100vw; max-width: 100vw; box-sizing: border-box; overflow-x: hidden")
        ):
            ui.label("Scheduling System").classes("text-2xl font-bold")
            if page.error:
                ui.label(page.error).classes("text-red-700")
                if page.schedule_id is not None:
                    ui.button(
                        "Reload schedule",
                        on_click=lambda: page.act(page.service.get_schedule, page.schedule_id),
                    )
            if page.message:
                ui.label(page.message).classes("text-green-700")
            if page.busy:
                ui.label("Working…")
            if page.result is None:
                name = ui.input("Schedule name")

                def create() -> None:
                    try:
                        record = page.service.create_schedule(name.value)
                        page.schedules = page.service.list_schedules()
                        page.schedule_id = record.id
                        page.result = page.service.get_schedule(record.id)
                        page.epoch += 1
                        page.client.run_javascript(
                            f"localStorage.setItem('selected_schedule_id', '{record.id}')"
                        )
                        page.refresh()
                    except SchedulingError as error:
                        page.error = f"{error.code}: {error}"
                        page.refresh()

                ui.button("Create schedule", on_click=create)
                return
            with ui.row().classes("w-full min-w-0 items-center gap-2 flex-wrap"):
                for schedule in page.schedules:
                    ui.button(
                        f"{schedule.name} #{schedule.id}",
                        on_click=partial(page.select, schedule.id),
                    )
                ui.label(
                    f"Selected schedule: {page.result.state.name} #{page.result.state.id}"
                ).classes("w-full sm:w-auto min-w-0 max-w-full break-all")
            if page.location_hint:
                ui.label(f"Showing {page.location_hint}")
            if page.history is not None:
                render_history(page)
                return
            with ui.row().classes("items-end gap-2 flex-wrap"):
                new_name = ui.input("New schedule name")
                renamed = ui.input("Rename schedule", value=page.result.state.name)

                async def create_another() -> None:
                    record = await page.act(page.service.create_schedule, new_name.value)
                    if record is not None:
                        page.schedules = await page.service_list()
                        page.select(record.id)

                async def rename() -> None:
                    result = await page.act(
                        page.service.rename_schedule, page.schedule_id, renamed.value
                    )
                    if result is not None:
                        page.schedules = await page.service_list()
                        page.refresh()

                ui.button("Create schedule", on_click=create_another)
                ui.button("Save schedule name", on_click=rename)
            render_roster(page)
            with ui.row().classes("gap-2 flex-wrap"):
                for tab in (
                    "Staff",
                    "Shifts",
                    "Demand import",
                    "Hourly analysis",
                    "Warnings",
                    "History",
                ):
                    ui.button(tab, on_click=partial(set_tab, tab))
            if page.tab == "Staff":
                render_staff(page)
            elif page.tab == "Shifts":
                render_shifts(page)
            elif page.tab == "Demand import":
                render_demand(page)
            elif page.tab in ("Hourly analysis", "Warnings"):
                render_analysis(page)
            elif page.tab == "History":
                render_history(page)

    def set_tab(tab: str) -> None:
        page.tab = tab
        page.editor = page.pending = None
        page.location_hint = None
        if tab == "History":
            page.history_list = page.service.list_snapshots(page.schedule_id)
        page.refresh()

    def refresh_now() -> None:
        content._execute_refresh((), {}, instance=content.instance)

    page.refresh = refresh_now
    content()
    ui.timer(0.01, page.bootstrap, once=True)


def run_app() -> None:
    """Start the local NiceGUI server."""
    ui.run(title="Staff Scheduling System", host="127.0.0.1", port=8765, show=False, reload=False)
