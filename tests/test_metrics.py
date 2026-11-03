"""Exact coverage, ratio, and unavailable-demand results."""

from src.services.schedules import ScheduleService
from tests.scheduling_support import require_method, week_csv


def _service(tmp_path):
    return ScheduleService(tmp_path / "schedules.sqlite3")


def _read(service, schedule_id):
    return require_method(service, "get_schedule")(schedule_id)


def test_no_import_keeps_transaction_and_coverage_metrics_unavailable(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id

    result = _read(service, schedule_id)

    assert result.state.demand is None
    assert result.weekly.total_transactions is None
    assert result.weekly.coverage_rate is None
    assert result.weekly.transactions_per_staff_hour is None


def test_ratios_use_total_and_separate_unweighted_staffed_cell_average(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    values = {("Monday", 7): 33, ("Monday", 8): 48, ("Monday", 9): 33}
    require_method(service, "import_initial")(schedule_id, week_csv(values=values))
    require_method(service, "set_daily_shift_limit")(schedule_id, 3)
    shifts = []
    for hour in (7, 8, 9):
        require_method(service, "add_shift")(schedule_id, hour, hour + 1)
        shifts.append(_read(service, schedule_id).state.shifts[-1])
    employees = []
    for name in ("A", "B", "C"):
        require_method(service, "add_employee")(schedule_id, name, 3)
        employees.append(_read(service, schedule_id).state.employees[-1])
    add = require_method(service, "add_assignment")
    for employee in employees:
        add(schedule_id, employee.id, 0, shifts[0].id)
        add(schedule_id, employee.id, 0, shifts[1].id)
    for employee in employees[:2]:
        add(schedule_id, employee.id, 0, shifts[2].id)

    result = _read(_service(tmp_path), schedule_id)

    assert result.weekly.total_transactions == 114
    assert result.weekly.scheduled_staff_hours == 8
    assert result.weekly.transactions_per_staff_hour == 14.25
    assert result.weekly.average_staffed_cell_ratio == 14.5
    buckets = {(item.day, item.hour): item for item in result.hourly}
    assert buckets[(0, 7)].scheduled == 3
    assert buckets[(0, 7)].required == 2
    assert buckets[(0, 7)].covered == 2
    assert buckets[(0, 7)].excess == 1
    assert buckets[(0, 10)].transactions_per_staff_hour is None
    assert sum(item.assigned_hours for item in result.employees) == 8


def test_all_unstaffed_ratios_undefined_and_coverage_zero(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    require_method(service, "import_initial")(schedule_id, week_csv(values={("Monday", 7): 12}))

    result = _read(service, schedule_id)

    assert result.weekly.total_transactions == 12
    assert result.weekly.scheduled_staff_hours == 0
    assert result.weekly.coverage_rate == 0
    assert result.weekly.transactions_per_staff_hour is None
    assert result.weekly.average_staffed_cell_ratio is None
    assert all(item.transactions_per_staff_hour is None for item in result.hourly)


def test_removing_assignment_recomputes_exactly_covered_hours(tmp_path) -> None:
    service = _service(tmp_path)
    schedule_id = service.create_schedule("A").id
    require_method(service, "import_initial")(schedule_id, week_csv())
    require_method(service, "add_employee")(schedule_id, "Alex", 8)
    state = _read(service, schedule_id).state
    require_method(service, "add_assignment")(
        schedule_id, state.employees[0].id, 0, state.shifts[0].id
    )
    assigned = _read(service, schedule_id)

    require_method(service, "remove_assignment")(schedule_id, assigned.state.assignments[0].id)
    removed = _read(_service(tmp_path), schedule_id)
    before = {(item.day, item.hour): item.scheduled for item in assigned.hourly}
    after = {(item.day, item.hour): item.scheduled for item in removed.hourly}

    assert {key for key in before if before[key] != after[key]} == {
        (0, hour) for hour in range(7, 15)
    }
    assert removed.weekly.scheduled_staff_hours == 0
    assert removed.weekly.unmet_staff_hours == 112
    assert removed.state.assignments == ()
