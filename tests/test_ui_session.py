"""Browser selection and committed-view integrity for the manager page."""

import asyncio
import re

from nicegui import ui
from nicegui.elements.upload_files import SmallFileUpload

from tests.scheduling_support import week_csv
from tests.ui_support import input_field, manager_page, sync_test


@sync_test
async def test_selection_empty_page_creates_persisted_default_week(tmp_path, monkeypatch) -> None:
    """The first manager action creates a selected, empty schedule."""
    async with manager_page(tmp_path, monkeypatch) as (user, service):
        await user.should_see("Create schedule")
        input_field(user, "Schedule name").type("Week A")
        user.find("Create schedule").click()

        await user.should_see("Week A")
        saved = service.list_schedules()
        assert len(saved) == 1
        result = service.get_schedule(saved[0].id)
        assert result.state.threshold == 20
        assert result.state.daily_shift_limit == 1
        assert result.state.demand is None
        assert result.state.assignments == ()


@sync_test
async def test_selection_duplicate_names_are_distinguished_by_id(tmp_path, monkeypatch) -> None:
    """Two same-name weeks remain selectable by their stable IDs."""
    ids = []

    def seed(service):
        ids.extend(service.create_schedule("Week").id for _ in range(2))

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        await user.should_see(f"Week #{ids[0]}")
        await user.should_see(f"Week #{ids[1]}")
        user.find(f"Week #{ids[1]}").click()

        await user.should_see(f"Selected schedule: Week #{ids[1]}")
        assert len(service.list_schedules()) == 2


@sync_test
async def test_selection_invalid_saved_id_falls_back_without_phantom_week(
    tmp_path, monkeypatch
) -> None:
    """An untrusted deleted or malformed browser ID cannot select a phantom week."""
    ids = []

    def seed(service):
        ids.append(service.create_schedule("First").id)
        service.create_schedule("Second")

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.javascript_rules[re.compile(r".*localStorage.getItem.*")] = lambda _: "999999"
        await user.open("/")

        await user.should_see(f"Selected schedule: First #{ids[0]}")
        assert len(service.list_schedules()) == 2


@sync_test
async def test_action_boundary_rejected_edit_keeps_last_committed_view(
    tmp_path, monkeypatch
) -> None:
    """A malformed staff maximum reports an error and commits no roster change."""
    schedule_ids = []

    def seed(service):
        schedule_ids.append(service.create_schedule("Week").id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        before = service.get_schedule(schedule_ids[0])
        user.find("Staff").click()
        input_field(user, "Employee name").type("Alex")
        input_field(user, "Weekly maximum").clear().type("1.5")
        user.find("Add employee").click()

        await user.should_see("weekly_max_hours")
        assert service.get_schedule(schedule_ids[0]) == before


@sync_test
async def test_selection_can_create_another_week_and_rename_by_id(tmp_path, monkeypatch) -> None:
    """Creating and renaming a selected week keeps the first week independent."""
    ids = []

    def seed(service):
        ids.append(service.create_schedule("First").id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        input_field(user, "New schedule name").type("Second")
        user.find("Create schedule").click()
        await user.should_see("Selected schedule: Second #2")

        input_field(user, "Rename schedule").clear().type("Renamed")
        user.find("Save schedule name").click()
        await user.should_see("Selected schedule: Renamed #2")

        assert service.get_schedule(ids[0]).state.name == "First"
        assert service.get_schedule(2).state.name == "Renamed"


@sync_test
async def test_selection_discards_upload_from_previous_schedule(tmp_path, monkeypatch) -> None:
    """An upload finishing after a schedule switch cannot become the new proposal."""
    ids = []

    def seed(service):
        ids.extend(service.create_schedule(name).id for name in ("First", "Second"))

    started = asyncio.Event()
    release = asyncio.Event()

    class DelayedUpload(SmallFileUpload):
        def iterate(self, *, chunk_size=1024 * 1024):
            async def chunks():
                started.set()
                await release.wait()
                yield self._data

            return chunks()

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, service):
        user.find("Demand import").click()
        upload = next(iter(user.find(ui.upload).elements))
        task = asyncio.create_task(
            upload.handle_uploads([DelayedUpload("report.csv", "text/csv", week_csv())])
        )
        await started.wait()
        user.find(f"Second #{ids[1]}").click()
        release.set()
        await task

        user.find("Demand import").click()
        await user.should_not_see("Monday 07:00: 0")
        assert service.get_schedule(ids[1]).state.demand is None


@sync_test
async def test_selection_can_switch_while_viewing_history(tmp_path, monkeypatch) -> None:
    """The schedule selector stays reachable in historical read-only mode."""
    ids = []

    def seed(service):
        first = service.create_schedule("First").id
        service.import_initial(first, week_csv())
        service.add_employee(first, "Alex", 8)
        preview = service.preview_refresh(first, threshold=10)
        service.confirm_refresh(first, preview.token, threshold=10, confirmed=True)
        ids.append(service.create_schedule("Second").id)

    async with manager_page(tmp_path, monkeypatch, seed=seed) as (user, _):
        user.find("History").click()
        user.find("THRESHOLD_CHANGE").click()
        await user.should_see("Historical / read-only")

        user.find(f"Second #{ids[0]}").click()
        await user.should_see(f"Selected schedule: Second #{ids[0]}")
        await user.should_not_see("Historical / read-only")
