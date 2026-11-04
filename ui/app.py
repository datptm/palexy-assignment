"""Browser entry point for the staff scheduling manager."""

from functools import partial

from nicegui import ui

from src.model.scheduling import SchedulingError
from ui.analysis_panel import render_analysis
from ui.demand_panel import render_demand
from ui.history_panel import render_history
from ui.roster import render_roster, render_roster_dialog
from ui.session import PageSession
from ui.shift_panel import render_shifts
from ui.staff_panel import render_staff

PAGE_STYLES = """
<style>
    :root {
        color-scheme: light;
        --schedule-navy: #14213d;
        --schedule-blue: #1672c4;
        --schedule-teal: #159b9a;
        --schedule-amber: #bf7910;
        --schedule-red: #c74646;
        --schedule-muted: #64748b;
        --schedule-border: #dce3eb;
        --schedule-surface: #ffffff;
        --schedule-background: #f3f6fa;
    }
    body { background: var(--schedule-background); color: var(--schedule-navy); }
    .schedule-page {
        box-sizing: border-box;
        gap: 16px;
        margin: 0 auto;
        max-width: 1600px;
        min-height: 100vh;
        padding: 24px clamp(16px, 3vw, 44px) 48px;
        width: 100%;
    }
    .schedule-header, .schedule-header-row, .schedule-navigation {
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        width: 100%;
    }
    .schedule-header { justify-content: space-between; }
    .schedule-page .q-btn { text-transform: none; }
    .schedule-brand { color: var(--schedule-navy); font-size: 1.65rem; font-weight: 750; }
    .schedule-subtitle { color: var(--schedule-muted); font-size: .9rem; }
    .schedule-card {
        background: var(--schedule-surface);
        border: 1px solid var(--schedule-border);
        border-radius: 12px;
        box-shadow: 0 2px 8px rgb(20 33 61 / 4%);
        min-width: 0;
        padding: 18px;
        width: 100%;
    }
    .schedule-card-title { color: var(--schedule-navy); font-size: 1.05rem; font-weight: 700; }
    .schedule-toolbar { gap: 14px; }
    .schedule-kpis { display: grid; gap: 10px; grid-template-columns: repeat(4, minmax(130px, 1fr)); width: 100%; }
    .schedule-metric {
        background: #f8fafc;
        border: 1px solid #e6ebf1;
        border-radius: 9px;
        min-width: 0;
        padding: 12px 14px;
    }
    .schedule-metric-label { color: var(--schedule-muted); font-size: .78rem; font-weight: 600; }
    .schedule-metric-value { color: var(--schedule-navy); font-size: 1.35rem; font-weight: 750; line-height: 1.4; }
    .schedule-metric-detail { color: var(--schedule-muted); font-size: .78rem; }
    .schedule-metric--healthy .schedule-metric-value { color: #087f75; }
    .schedule-metric--warning .schedule-metric-value { color: var(--schedule-amber); }
    .schedule-metric--critical .schedule-metric-value { color: var(--schedule-red); }
    .schedule-navigation { border-bottom: 1px solid var(--schedule-border); gap: 6px; padding-bottom: 10px; }
    .schedule-grid-scroll { max-width: 100%; overflow-x: auto; width: 100%; }
    .schedule-grid {
        display: grid;
        grid-template-columns: minmax(112px, 145px) repeat(7, minmax(145px, 1fr));
        min-width: 1180px;
    }
    .schedule-grid-heading {
        align-items: center;
        background: #f4f7fa;
        border-bottom: 1px solid var(--schedule-border);
        color: #334155;
        display: flex;
        font-size: .85rem;
        font-weight: 700;
        justify-content: center;
        min-height: 42px;
        padding: 8px;
    }
    .schedule-grid-shift {
        align-items: flex-start;
        border-bottom: 1px solid #e8edf2;
        color: #334155;
        display: flex;
        flex-direction: column;
        font-size: .85rem;
        font-weight: 650;
        justify-content: center;
        padding: 12px;
    }
    .schedule-grid-cell {
        border-bottom: 1px solid #e8edf2;
        border-left: 1px solid #eef1f5;
        min-height: 105px;
        padding: 8px;
    }
    .schedule-grid-cell .q-btn {
        font-size: .72rem;
        min-height: 28px;
        padding: 2px 7px;
        text-align: left;
        white-space: normal;
    }
    .schedule-grid-cell .q-btn__content { white-space: normal; }
    .schedule-assignee {
        color: #176b69;
        display: inline-flex;
        font-size: .76rem;
        margin: 0;
        padding: 3px 2px 3px 8px;
    }
    .schedule-assignee-row {
        align-items: center;
        background: #e7f5f4;
        border: 1px solid #c9e8e5;
        border-radius: 999px;
        display: inline-flex;
        flex-wrap: nowrap;
        gap: 0;
        margin: 4px 3px 0 0;
    }
    .schedule-assignee-remove { color: #176b69; }
    .schedule-workspace-dialog {
        box-sizing: border-box;
        gap: 18px;
        max-height: 88vh;
        overflow-y: auto;
        width: min(1120px, calc(100vw - 40px));
    }
    .q-dialog__inner--minimized > .schedule-workspace-dialog {
        max-width: min(1120px, calc(100vw - 40px)) !important;
        width: min(1120px, calc(100vw - 40px)) !important;
    }
    .schedule-workspace-dialog .q-btn { text-transform: none; }
    .schedule-workspace-intro { gap: 2px; width: 100%; }
    .schedule-workspace-title { color: var(--schedule-navy); font-size: 1.25rem; font-weight: 750; }
    .schedule-workspace-subtitle { color: var(--schedule-muted); font-size: .82rem; }
    .schedule-workspace-grid {
        align-items: start;
        display: grid;
        gap: 14px;
        grid-template-columns: minmax(230px, .78fr) minmax(0, 1.5fr);
        width: 100%;
    }
    .schedule-workspace-grid--even { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .schedule-workspace-card {
        background: #fff;
        border: 1px solid var(--schedule-border);
        border-radius: 9px;
        box-shadow: 0 1px 3px rgb(20 33 61 / 5%);
        gap: 10px;
        min-width: 0;
        padding: 14px;
        width: 100%;
    }
    .schedule-workspace-card-title { color: #23344c; font-size: .9rem; font-weight: 700; }
    .schedule-workspace-card .q-field { width: 100%; }
    .schedule-workspace-card .q-btn { max-width: 100%; }
    .schedule-assignment-dialog { gap: 14px; }
    .q-dialog__inner--minimized > .schedule-assignment-dialog {
        max-width: min(920px, calc(100vw - 40px)) !important;
        width: min(920px, calc(100vw - 40px)) !important;
    }
    .schedule-assignment-grid {
        align-items: start;
        display: grid;
        gap: 14px;
        grid-template-columns: minmax(240px, .85fr) minmax(0, 1.15fr);
        width: 100%;
    }
    .schedule-assignment-section { gap: 10px; }
    .schedule-assignment-moving {
        background: #eaf2fb;
        border-radius: 8px;
        color: #315d8a;
        padding: 10px 14px;
        width: 100%;
    }
    .schedule-assignment-person-row, .schedule-assignment-destination-row {
        align-items: center;
        border-top: 1px solid #e8edf2;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: space-between;
        padding: 9px 0;
        width: 100%;
    }
    .schedule-assignment-destinations { max-height: 220px; overflow-y: auto; width: 100%; }
    .schedule-assignment-day { color: #334155; font-size: .82rem; font-weight: 650; min-width: 90px; }
    .schedule-assignment-destination-row .q-btn { font-size: .78rem; }
    .schedule-assignment-choices { display: grid; gap: 8px; max-height: 340px; overflow-y: auto; width: 100%; }
    .schedule-assignment-choice {
        border: 1px solid #e6ebf1;
        border-radius: 8px;
        padding: 9px 11px;
        width: 100%;
    }
    .schedule-assignment-choice--selected { background: #eef8f8; border-color: #76c9c2; }
    .schedule-assignment-reasons { color: #96620d; font-size: .78rem; }
    .schedule-assignment-primary { align-self: flex-end; }
    .schedule-workspace-list { gap: 8px; width: 100%; }
    .schedule-workspace-row {
        align-items: center;
        border: 1px solid #e6ebf1;
        border-radius: 7px;
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: space-between;
        padding: 9px 10px;
        width: 100%;
    }
    .schedule-workspace-row-main { flex: 1 1 180px; min-width: 0; }
    .schedule-workspace-row-actions { align-items: center; display: flex; flex-wrap: wrap; gap: 4px; }
    .schedule-hourly-table { max-width: 100%; overflow: auto; width: 100%; }
    .schedule-table-scroll { max-height: 260px; max-width: 100%; overflow: auto; width: 100%; }
    .schedule-data-table { border-collapse: collapse; font-size: .82rem; min-width: 440px; width: 100%; }
    .schedule-data-table th, .schedule-data-table td {
        border-bottom: 1px solid #e8edf2;
        padding: 7px 10px;
        text-align: left;
        vertical-align: top;
    }
    .schedule-data-table th { background: #f0f4f7; color: #334155; font-weight: 700; position: sticky; top: 0; }
    .schedule-data-table tbody tr:nth-child(even) { background: #f8fafc; }
    .schedule-review-list { list-style: disc; margin: 0; padding-left: 22px; }
    .schedule-review-list li { margin: 5px 0; }
    .schedule-hourly-row:nth-child(even) { background: #f5f8fa; }
    .schedule-hourly-row {
        align-items: center;
        border-bottom: 1px solid #e8edf2;
        display: grid;
        font-size: .75rem;
        gap: 8px;
        grid-template-columns: minmax(145px, 1.6fr) repeat(4, minmax(64px, .7fr));
        min-width: 540px;
        padding: 6px 9px;
    }
    .schedule-hourly-head {
        background: #f0f4f7;
        color: #334155;
        font-weight: 700;
        position: sticky;
        top: 0;
        z-index: 1;
    }
    .schedule-warning-card { border-left: 4px solid var(--schedule-amber); }
    .schedule-warning-card--error { border-left-color: var(--schedule-red); }
    .schedule-warning-card--info { border-left-color: var(--schedule-blue); }
    .schedule-history-list { border-left: 2px solid #d5e0ea; gap: 12px; margin-left: 10px; padding-left: 16px; }
    .schedule-history-entry { position: relative; }
    .schedule-history-entry::before {
        background: var(--schedule-blue);
        border: 3px solid #eaf2fb;
        border-radius: 50%;
        content: "";
        height: 10px;
        left: -24px;
        position: absolute;
        top: 14px;
        width: 10px;
    }
    .schedule-upload-card {
        align-items: center;
        background: #f8fafc;
        border: 1px dashed #aebdca;
        border-radius: 8px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 16px;
        width: 100%;
    }
    .schedule-upload-card .q-uploader {
        background: transparent;
        box-shadow: none;
        width: 100% !important;
    }
    .schedule-empty { color: var(--schedule-red); font-size: .76rem; font-weight: 650; margin-top: 8px; }
    .schedule-supporting { display: grid; gap: 16px; grid-template-columns: minmax(230px, .7fr) minmax(0, 2fr); width: 100%; }
    .schedule-capacity-row { gap: 4px; width: 100%; }
    .schedule-capacity-track { background: #e7edf3; border-radius: 99px; height: 7px; overflow: hidden; width: 100%; }
    .schedule-capacity-fill { background: var(--schedule-teal); border-radius: inherit; height: 100%; }
    .schedule-capacity-fill--warning { background: #d89823; }
    .schedule-capacity-meta { color: var(--schedule-muted); font-size: .78rem; }
    .schedule-status {
        background: #eaf2fb;
        border-radius: 999px;
        color: #315d8a;
        font-size: .76rem;
        font-weight: 650;
        padding: 4px 10px;
    }
    .schedule-status--warning { background: #fff0c7; color: #8a5a08; }
    .schedule-alert { border-radius: 8px; padding: 10px 12px; width: 100%; }
    .schedule-alert--error { background: #fff0ef; border: 1px solid #f3c7c3; color: #a53d39; }
    .schedule-alert--warning { background: #fff7e6; border: 1px solid #f0d7a1; color: #96620d; }
    .schedule-alert--success { background: #ecf8f4; border: 1px solid #c7e9dc; color: #18745a; }
    @media (max-width: 760px) {
        .schedule-page { padding: 14px 12px 32px; }
        .schedule-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .schedule-supporting { grid-template-columns: minmax(0, 1fr); }
        .schedule-card { padding: 14px; }
        .schedule-workspace-dialog {
            gap: 12px;
            max-height: 92vh;
            padding: 14px;
            width: calc(100vw - 20px);
        }
        .schedule-workspace-grid,
        .schedule-workspace-grid--even,
        .schedule-assignment-grid { grid-template-columns: minmax(0, 1fr); }
        .schedule-workspace-title { font-size: 1.1rem; }
    }
</style>
"""


@ui.page("/")
async def home_page() -> None:
    """Build one page-local schedule workflow from persisted service data."""
    ui.add_head_html(PAGE_STYLES)
    page = PageSession()
    page.schedules = page.service.list_schedules()
    if page.schedules:
        page.schedule_id = page.schedules[0].id
        page.result = page.service.get_schedule(page.schedule_id)

    @ui.refreshable
    def content() -> None:
        with (
            ui.column().classes("schedule-page").style("box-sizing: border-box; overflow-x: hidden")
        ):
            with ui.row().classes("schedule-header"):
                with ui.column().classes("gap-0"):
                    ui.label("Weekly staff roster").classes("schedule-brand")
                    ui.label(
                        "Plan coverage, balance hours, and review the week at a glance"
                    ).classes("schedule-subtitle")
                if page.result is not None:
                    ui.label("Draft schedule").classes("schedule-status")
            if page.error:
                ui.label(page.error).classes("schedule-alert schedule-alert--error")
                if page.schedule_id is not None:
                    ui.button(
                        "Reload schedule",
                        on_click=lambda: page.act(page.service.get_schedule, page.schedule_id),
                    )
            if page.message:
                ui.label(page.message).classes("schedule-alert schedule-alert--success")
            if page.busy:
                ui.label("Working…")
            if page.result is None:
                with ui.card().classes("schedule-card gap-3"):
                    ui.label("Start a weekly schedule").classes("schedule-card-title")
                    ui.label("Create a named week to add staff, shifts, and transaction demand.")
                    name = ui.input("Schedule name").classes("w-full max-w-md")

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

                    ui.button("Create schedule", on_click=create).props("unelevated")
                return
            with ui.card().classes("schedule-card schedule-toolbar"):
                with ui.row().classes("schedule-header-row"):
                    ui.label(
                        f"Selected schedule: {page.result.state.name} #{page.result.state.id}"
                    ).classes("schedule-card-title min-w-0")
                    for schedule in page.schedules:
                        button = ui.button(
                            f"{schedule.name} #{schedule.id}",
                            on_click=partial(page.select, schedule.id),
                        )
                        button.props("unelevated" if schedule.id == page.schedule_id else "outline")
                with ui.row().classes("schedule-header-row"):
                    new_name = ui.input("New schedule name").classes("w-48")
                    renamed = ui.input("Rename schedule", value=page.result.state.name).classes(
                        "w-48"
                    )

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

                    ui.button("Create schedule", on_click=create_another).props("outline")
                    ui.button("Save schedule name", on_click=rename).props("outline")
            if page.location_hint:
                ui.label(f"Showing {page.location_hint}").classes("schedule-status")
            with ui.row().classes("schedule-navigation"):
                for tab in (
                    "Staff",
                    "Shifts",
                    "Demand import",
                    "Hourly analysis",
                    "Warnings",
                    "History",
                ):
                    button = ui.button(tab, on_click=partial(set_tab, tab))
                    button.props("unelevated" if page.tab == tab else "flat").classes(
                        "font-semibold"
                    )
            render_roster(page)

    dialog = ui.dialog().props("persistent")

    @ui.refreshable
    def dialog_content() -> None:
        if page.result is None:
            return
        if page.tab == "Roster":
            render_roster_dialog(page)
        else:
            with ui.card().classes("schedule-card schedule-workspace-dialog"):
                with ui.row().classes("schedule-header-row justify-between"):
                    ui.label(page.tab).classes("schedule-card-title")
                    ui.button(
                        "Close",
                        icon="close",
                        on_click=lambda: set_tab("Roster"),
                    ).props("flat")
                if page.error:
                    ui.label(page.error).classes("schedule-alert schedule-alert--error")
                if page.message:
                    ui.label(page.message).classes("schedule-alert schedule-alert--success")
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
        dialog_content._execute_refresh((), {}, instance=dialog_content.instance)
        should_open = (
            page.tab != "Roster"
            or (page.editor is not None and page.editor[0] == "cell")
            or (page.pending is not None and page.pending["kind"] == "generation")
        )
        if should_open and not dialog.value:
            dialog.open()
        elif not should_open and dialog.value:
            dialog.close()

    page.refresh = refresh_now
    content()
    with dialog:
        dialog_content()
    ui.timer(0.01, page.bootstrap, once=True)


def run_app() -> None:
    """Start the local NiceGUI server."""
    ui.run(title="Weekly Staff Roster", host="127.0.0.1", port=8765, show=False, reload=False)
