"""Pure whole-state assignment checks."""

from collections import Counter, defaultdict

from src.domain.limits import checked_total
from src.domain.shifts import overlaps, validate_shift_range
from src.model.scheduling import ScheduleState, SchedulingError, Violation


def validate_state(state: ScheduleState) -> tuple[Violation, ...]:
    """Report hard assignment errors and soft capacity warnings."""
    findings: list[Violation] = []
    employees = {employee.id: employee for employee in state.employees}
    shifts = {shift.id: shift for shift in state.shifts}
    seen_ranges: set[tuple[int, int]] = set()
    for shift in state.shifts:
        try:
            validate_shift_range(shift.start_hour, shift.end_hour)
        except SchedulingError:
            findings.append(
                Violation(
                    "INVALID_SHIFT_RANGE",
                    "error",
                    "shift is outside operating hours",
                    {"shift_id": shift.id},
                )
            )
        hours_key = (shift.start_hour, shift.end_hour)
        if hours_key in seen_ranges:
            findings.append(
                Violation(
                    "DUPLICATE_SHIFT_DEFINITION",
                    "error",
                    "shift times are duplicated",
                    {"shift_id": shift.id},
                )
            )
        seen_ranges.add(hours_key)
    seen: set[tuple[int, int, int]] = set()
    by_person_day: dict[tuple[int, int], list] = defaultdict(list)
    hours: Counter[int] = Counter()
    for assignment in state.assignments:
        employee = employees.get(assignment.employee_id)
        shift = shifts.get(assignment.shift_id)
        if employee is None or shift is None or not 0 <= assignment.day <= 6:
            findings.append(
                Violation(
                    "UNKNOWN_REFERENCE",
                    "error",
                    "assignment reference is invalid",
                    {"assignment_id": assignment.id},
                )
            )
            continue
        key = (assignment.employee_id, assignment.day, assignment.shift_id)
        if key in seen:
            findings.append(
                Violation(
                    "DUPLICATE_ASSIGNMENT",
                    "error",
                    "assignment is duplicated",
                    {"assignment_id": assignment.id},
                )
            )
        seen.add(key)
        for other_assignment, other_shift in by_person_day[
            (assignment.employee_id, assignment.day)
        ]:
            if overlaps(
                shift.start_hour, shift.end_hour, other_shift.start_hour, other_shift.end_hour
            ):
                findings.append(
                    Violation(
                        "SHIFT_OVERLAP",
                        "error",
                        "employee shifts overlap",
                        {
                            "assignment_id": assignment.id,
                            "affected_assignment_ids": (other_assignment.id, assignment.id),
                            "employee_id": employee.id,
                            "day": assignment.day,
                        },
                    )
                )
        by_person_day[(assignment.employee_id, assignment.day)].append((assignment, shift))
        hours[employee.id] += shift.end_hour - shift.start_hour
    for employee in state.employees:
        assigned = checked_total(hours[employee.id], field="assigned_hours")
        if assigned > employee.weekly_max_hours:
            findings.append(
                Violation(
                    "OVER_WEEKLY_MAX",
                    "warning",
                    "weekly maximum exceeded",
                    {
                        "employee_id": employee.id,
                        "assigned_hours": assigned,
                        "limit": employee.weekly_max_hours,
                        "excess": assigned - employee.weekly_max_hours,
                    },
                )
            )
    for (employee_id, day), assigned_shifts in by_person_day.items():
        if len(assigned_shifts) > state.daily_shift_limit:
            findings.append(
                Violation(
                    "OVER_DAILY_SHIFT_LIMIT",
                    "warning",
                    "daily shift limit exceeded",
                    {
                        "employee_id": employee_id,
                        "day": day,
                        "count": len(assigned_shifts),
                        "limit": state.daily_shift_limit,
                        "excess": len(assigned_shifts) - state.daily_shift_limit,
                    },
                )
            )
    return tuple(findings)
