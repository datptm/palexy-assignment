"""Deterministic best-effort weekly draft generation."""

from dataclasses import replace
from fractions import Fraction

from src.domain.demand import required_staff, validate_demand
from src.domain.metrics import calculate_result
from src.model.scheduling import Assignment, ScheduleState, SchedulingError


def generate_draft(
    state: ScheduleState, *, shortage_weight: int = 3, excess_weight: int = 1
) -> ScheduleState:
    """Greedily add the best positive whole-shift candidate under hard limits."""
    if state.demand is None:
        raise SchedulingError("MISSING_DEMAND", "import a complete transaction report first")
    validate_demand(state.demand, state.threshold)
    if not state.shifts:
        raise SchedulingError("MISSING_SHIFTS", "add at least one shift")
    if not any(
        employee.weekly_max_hours >= shift.end_hour - shift.start_hour
        for employee in state.employees
        for shift in state.shifts
    ):
        raise SchedulingError("NO_ELIGIBLE_EMPLOYEE", "add an employee with enough weekly hours")
    shifts = sorted(state.shifts, key=lambda shift: (shift.start_hour, shift.end_hour, shift.id))
    employees = sorted(state.employees, key=lambda employee: employee.id)
    required = {
        (cell.day, cell.hour): required_staff(cell.transactions, state.threshold)
        for cell in state.demand
    }
    scheduled = {(day, hour): 0 for day in range(7) for hour in range(7, 23)}
    hours = {employee.id: 0 for employee in employees}
    days = {(employee.id, day): [] for employee in employees for day in range(7)}
    assignments: list[Assignment] = []
    while True:
        best_key = None
        best_candidate = None
        for employee in employees:
            for day in range(7):
                if len(days[(employee.id, day)]) >= state.daily_shift_limit:
                    continue
                for shift in shifts:
                    duration = shift.end_hour - shift.start_hour
                    if hours[employee.id] + duration > employee.weekly_max_hours:
                        continue
                    if any(
                        shift.start_hour < other.end_hour and other.start_hour < shift.end_hour
                        for other in days[(employee.id, day)]
                    ):
                        continue
                    shortage = sum(
                        scheduled[(day, hour)] < required[(day, hour)]
                        for hour in range(shift.start_hour, shift.end_hour)
                    )
                    excess = duration - shortage
                    score = shortage_weight * shortage - excess_weight * excess
                    if score <= 0:
                        continue
                    key = (
                        -score,
                        excess,
                        Fraction(hours[employee.id], employee.weekly_max_hours),
                        day,
                        shift.start_hour,
                        shift.end_hour,
                        shift.id,
                        employee.id,
                    )
                    if best_key is None or key < best_key:
                        best_key = key
                        best_candidate = (employee, day, shift)
        if best_candidate is None:
            break
        employee, day, shift = best_candidate
        assignments.append(Assignment(len(assignments) + 1, employee.id, day, shift.id))
        hours[employee.id] += shift.end_hour - shift.start_hour
        days[(employee.id, day)].append(shift)
        for hour in range(shift.start_hour, shift.end_hour):
            scheduled[(day, hour)] += 1
    draft = replace(state, assignments=tuple(assignments))
    calculate_result(draft)
    return draft
