"""Smoke tests for the local NiceGUI application."""

from nicegui import app
from nicegui import ui as nicegui_ui

from ui.app import run_app  # Registers the page with NiceGUI.


def test_home_page_is_registered_at_root() -> None:
    """The browser entry point must expose the manager's landing page."""
    paths = {route.path for route in app.routes}
    assert "/" in paths


def test_run_app_binds_only_to_local_browser(monkeypatch) -> None:
    """The live entry point keeps the approved loopback address and port."""
    options = {}
    monkeypatch.setattr(nicegui_ui, "run", lambda **kwargs: options.update(kwargs))

    run_app()

    assert options["host"] == "127.0.0.1"
    assert options["port"] == 8765
