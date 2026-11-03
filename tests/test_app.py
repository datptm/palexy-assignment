"""Smoke tests for the local NiceGUI application."""

from nicegui import app

import ui.app  # noqa: F401  # Registers the page with NiceGUI.


def test_home_page_is_registered_at_root() -> None:
    """The browser entry point must expose the manager's landing page."""
    paths = {route.path for route in app.routes}
    assert "/" in paths
