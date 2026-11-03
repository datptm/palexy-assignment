"""Pure current-state coverage and workload calculations."""

from collections import Counter

from src.domain.demand import required_staff
from src.domain.limits import checked_total
from src.domain.validation import validate_state
from src.model.scheduling import (
    EmployeeMetric,
    HourlyMetric,
    RosterSlot,
    ScheduleResult,
    ScheduleState,
    WeeklyMetric,
)


def calculate_result(state: ScheduleState) -> ScheduleResult:
    """Calculate metrics and current warnings without changing state."""
    shifts = {shift.id: shift for shift in state.shifts}
    counts: Counter[tuple[int, int]] = Counter()
    employee_hours: Counter[int] = Counter()
    for assignment in state.assignments:
        shift = shifts[assignment.shift_id]
        duration = shift.end_hour - shift.start_hour
        employee_hours[assignment.employee_id] += duration
        for hour in range(shift.start_hour, shift.end_hour):
            counts[(assignment.day, hour)] += 1
    scheduled_total = checked_total(sum(counts.values()), field="scheduled_staff_hours")
    demand = {(cell.day, cell.hour): cell.transactions for cell in state.demand or ()}
    hourly = []
    total_transactions = required_total = covered_total = unmet_total = excess_total = 0
    staffed_ratios = []
    for day in range(7):
        for hour in range(7, 23):
            scheduled = counts[(day, hour)]
            if state.demand is None:
                hourly.append(
                    HourlyMetric(day, hour, None, None, scheduled, None, None, None, None)
                )
                continue
            transactions = demand[(day, hour)]
            required = required_staff(transactions, state.threshold)
            covered = min(required, scheduled)
            unmet = required - covered
            excess = max(0, scheduled - required)
            ratio = transactions / scheduled if scheduled else None
            hourly.append(
                HourlyMetric(
                    day, hour, transactions, required, scheduled, covered, unmet, excess, ratio
                )
            )
            total_transactions += transactions
            required_total += required
            covered_total += covered
            unmet_total += unmet
            excess_total += excess
            if ratio is not None:
                staffed_ratios.append(ratio)
    metrics = tuple(
        EmployeeMetric(
            employee.id,
            employee.name,
            checked_total(employee_hours[employee.id], field="employee_hours"),
            employee.weekly_max_hours,
            employee_hours[employee.id] / employee.weekly_max_hours
            if employee.weekly_max_hours
            else None,
        )
        for employee in state.employees
    )
    if state.demand is None:
        weekly = WeeklyMetric(None, None, scheduled_total, None, None, None, None, None, None)
    else:
        for name, value in (
            ("total_transactions", total_transactions),
            ("required_staff_hours", required_total),
            ("covered_staff_hours", covered_total),
            ("unmet_staff_hours", unmet_total),
            ("excess_staff_hours", excess_total),
        ):
            checked_total(value, field=name)
        weekly = WeeklyMetric(
            total_transactions,
            required_total,
            scheduled_total,
            covered_total,
            unmet_total,
            excess_total,
            covered_total / required_total,
            total_transactions / scheduled_total if scheduled_total else None,
            sum(staffed_ratios) / len(staffed_ratios) if staffed_ratios else None,
        )
    warnings = (
        tuple(item for item in validate_state(state) if item.severity == "warning")
        + state.import_warnings
    )
    employee_metrics = {item.employee_id: item for item in metrics}
    roster = tuple(
        RosterSlot(
            day,
            shift.id,
            shift.start_hour,
            shift.end_hour,
            tuple(
                employee_metrics[assignment.employee_id]
                for assignment in state.assignments
                if assignment.day == day and assignment.shift_id == shift.id
            ),
        )
        for day in range(7)
        for shift in sorted(
            state.shifts, key=lambda item: (item.start_hour, item.end_hour, item.id)
        )
    )
    return ScheduleResult(state, warnings, tuple(hourly), weekly, metrics, roster)
