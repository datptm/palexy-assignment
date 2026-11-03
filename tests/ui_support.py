"""Isolated NiceGUI page simulation for the proposed manager workflow."""

import asyncio
import importlib
from contextlib import asynccontextmanager
from functools import wraps

from nicegui import run, ui
from nicegui.testing import UserInteraction, user_simulation

from src.services.schedules import ScheduleService


def sync_test(async_test):
    """Run an async NiceGUI test without an additional pytest plugin."""

    @wraps(async_test)
    def wrapper(*args, **kwargs):
        return asyncio.run(async_test(*args, **kwargs))

    return wrapper


def input_field(user, label):
    """Target one editable control even when a nearby label has the same text."""
    elements = {
        element
        for element in user.find(label).elements
        if isinstance(element, (ui.input, ui.number))
    }
    assert len(elements) == 1, f"expected one editable field named {label}"
    return UserInteraction(user, elements, label)


@asynccontextmanager
async def manager_page(tmp_path, monkeypatch, *, seed=None):
    """Open the real root page against a temporary SQLite database."""
    original_init = ScheduleService.__init__
    database_path = tmp_path / "schedules.sqlite3"

    def isolated_init(self, _database_path=None):
        original_init(self, database_path)

    monkeypatch.setattr(ScheduleService, "__init__", isolated_init)
    # NiceGUI creates an unused CPU process pool at startup; it is unavailable
    # in the restricted test environment. Its thread offload remains real.
    monkeypatch.setattr(run, "setup", lambda: None)
    service = ScheduleService(database_path)
    if seed is not None:
        seed(service)
    async with user_simulation() as user:
        import ui.app

        importlib.reload(ui.app)
        await user.open("/")
        yield user, service
