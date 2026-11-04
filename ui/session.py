"""One browser page's active result and guarded service actions."""

import logging
from collections.abc import Callable
from typing import Any

from nicegui import run, ui

from src.model.schedule import Schedule
from src.model.scheduling import ScheduleResult, SchedulingError, SnapshotSummary
from src.services.schedules import ScheduleService
from ui.presentation import finding_text

log = logging.getLogger(__name__)


class PageSession:
    """Keep transient page state separate from persisted schedule state."""

    def __init__(self) -> None:
        self.service = ScheduleService()
        self.client = ui.context.client
        self.schedules = []
        self.schedule_id: int | None = None
        self.result: ScheduleResult | None = None
        self.tab = "Roster"
        self.editor: tuple | None = None
        self.pending: dict[str, Any] | None = None
        self.history = None
        self.history_list = []
        self.staff_form: dict[str, str] = {}
        self.location_hint: str | None = None
        self.error: str | None = None
        self.message: str | None = None
        self.busy = False
        self.epoch = 0
        self.refresh: Callable[[], None] = lambda: None

    async def bootstrap(self) -> None:
        """Validate the browser preference against persisted schedule IDs."""
        opened_epoch = self.epoch
        schedules = await run.io_bound(self.service.list_schedules)
        try:
            saved = await self.client.run_javascript(
                "localStorage.getItem('selected_schedule_id')", timeout=1.0
            )
        except TimeoutError:
            saved = None
        if self.epoch != opened_epoch:
            return
        self.schedules = schedules
        valid = {item.id for item in schedules}
        selected = int(saved) if isinstance(saved, str) and saved.isdecimal() else None
        if selected not in valid:
            selected = schedules[0].id if schedules else None
        if selected != self.schedule_id:
            self.select(selected)
        elif selected is not None and saved != str(selected):
            self.client.run_javascript(
                f"localStorage.setItem('selected_schedule_id', '{selected}')"
            )

    async def service_list(self) -> list[Schedule]:
        """Reload the persisted schedule index after creation or rename."""
        return await run.io_bound(self.service.list_schedules)

    async def service_history_list(self) -> list[SnapshotSummary]:
        """Read the selected schedule's snapshot index."""
        return await run.io_bound(self.service.list_snapshots, self.schedule_id)

    def select(self, schedule_id: int | None) -> None:
        """Switch active schedule and invalidate transient work."""
        self.epoch += 1
        self.busy = False
        self.schedule_id = schedule_id
        self.editor = self.pending = self.history = None
        self.staff_form = {}
        self.location_hint = None
        self.tab = "Roster"
        self.error = self.message = None
        self.result = None if schedule_id is None else self.service.get_schedule(schedule_id)
        if schedule_id is not None:
            self.client.run_javascript(
                f"localStorage.setItem('selected_schedule_id', '{schedule_id}')"
            )
        self.refresh()

    async def act(self, method: Callable, *args: Any, **kwargs: Any) -> Any:
        """Run a service action once and apply only its current-page result."""
        if self.busy:
            return None
        self.busy = True
        selected, epoch = self.schedule_id, self.epoch
        focus_cell = None
        if method.__name__ == "add_assignment":
            focus_cell = (args[2], args[3])
        elif method.__name__ == "reassign_assignment":
            focus_cell = (args[3], args[4])
        elif method.__name__ == "remove_assignment" and self.result is not None:
            assignment = next(
                (item for item in self.result.state.assignments if item.id == args[1]), None
            )
            if assignment is not None:
                focus_cell = (assignment.day, assignment.shift_id)
        self.error = self.message = None
        self.refresh()
        try:
            value = await run.io_bound(method, *args, **kwargs)
            if (selected, epoch) != (self.schedule_id, self.epoch):
                return None
            if isinstance(value, ScheduleResult):
                self.result = value
                self.pending = None
                self.editor = None
                if method.__name__ != "get_schedule":
                    self.message = "Saved"
            return value
        except SchedulingError as error:
            if (selected, epoch) == (self.schedule_id, self.epoch):
                findings = " | ".join(finding_text(item) for item in error.findings)
                self.error = f"{error.code}: {error} {findings}".strip()
                if error.details:
                    self.error += " · " + ", ".join(
                        f"{key}: {value}" for key, value in error.details.items()
                    )
                if error.code == "STALE_PREVIEW" and selected is not None:
                    self.result = await run.io_bound(self.service.get_schedule, selected)
                    self.pending = None
                    self.editor = None
            return None
        except Exception:
            if (selected, epoch) == (self.schedule_id, self.epoch):
                log.error("Unexpected %s failure for schedule %s", method.__name__, selected)
                self.error = "Operation failed. Reload the schedule and try again."
                if selected is not None:
                    self.result = await run.io_bound(self.service.get_schedule, selected)
            return None
        finally:
            if (selected, epoch) == (self.schedule_id, self.epoch):
                self.busy = False
                self.refresh()
                if focus_cell is not None and self.message == "Saved":
                    day, shift_id = focus_cell
                    self.client.run_javascript(
                        f"document.getElementById('roster-cell-{day}-{shift_id}')?.focus()"
                    )
