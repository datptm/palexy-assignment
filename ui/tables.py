"""Small semantic tables for read-only scheduling details."""

from collections.abc import Iterable

from nicegui import ui


def render_data_table(headers: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> None:
    """Show compact text rows with accessible column headings and horizontal overflow."""
    with ui.element("div").classes("schedule-table-scroll"):
        with ui.element("table").classes("schedule-data-table"):
            with ui.element("thead"):
                with ui.element("tr"):
                    for header in headers:
                        with ui.element("th").props("scope=col"):
                            ui.label(header)
            with ui.element("tbody"):
                for row in rows:
                    with ui.element("tr"):
                        for value in row:
                            with ui.element("td"):
                                ui.label(value)
