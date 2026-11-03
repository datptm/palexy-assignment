"""Browser entry point for the staff scheduling system."""

from nicegui import ui

from src.domain.periods import DEFAULT_SHIFTS, WEEKDAYS


@ui.page("/")
def home_page() -> None:
    """Show the starting point for planning a typical store week."""
    with ui.column().classes("w-full max-w-5xl mx-auto p-8 gap-6"):
        ui.label("Staff Scheduling System").classes("text-3xl font-bold")
        ui.label("Plan a typical week around demand, shifts, and fair work hours.").classes(
            "text-lg text-gray-600"
        )

        with ui.card().classes("w-full"):
            ui.label("Weekly planning").classes("text-xl font-semibold")
            ui.label("Days: " + " · ".join(WEEKDAYS))
            ui.label("Default shifts")
            for start_hour, end_hour in DEFAULT_SHIFTS:
                ui.label(f"{start_hour:02d}:00–{end_hour:02d}:00")

        ui.label(
            "This is the project foundation. Schedule editing and demand import come next."
        ).classes("text-gray-600")


def run_app() -> None:
    """Start the local NiceGUI server."""
    ui.run(title="Staff Scheduling System", host="127.0.0.1", port=8765, show=False, reload=False)
