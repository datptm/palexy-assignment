"""Pure whole-state assignment checks."""

from collections import Counter, defaultdict
from collections.abc import Sequence

from src.domain.limits import checked_total
from src.domain.shifts import overlaps, validate_shift_range
from src.model.scheduling import Assignment, ScheduleState, SchedulingError, Violation


def _valid_assignment_references(
    state: ScheduleState,
    employee_id: int,
    day: int,
    shift_id: int,
    *,
    employee_ids: frozenset[int] | None = None,
    shift_ids: frozenset[int] | None = None,
    day_count: int = 7,
) -> bool:
    has_employee = (
        employee_id in employee_ids
        if employee_ids is not None
        else any(employee.id == employee_id for employee in state.employees)
    )
    has_shift = (
        shift_id in shift_ids
        if shift_ids is not None
        else any(shift.id == shift_id for shift in state.shifts)
    )
    return has_employee and has_shift and type(day) is int and 0 <= day < day_count


def _assignment_is_duplicate(
    key: tuple[int, int, int], existing: set[tuple[int, int, int]]
) -> bool:
    return key in existing


def _overlaps_shift(left, right) -> bool:
    return overlaps(left.start_hour, left.end_hour, right.start_hour, right.end_hour)


def _exceeds_weekly_limit(assigned_hours: int, maximum: int) -> bool:
    return assigned_hours > maximum


def _exceeds_daily_limit(assigned_count: int, limit: int) -> bool:
    return assigned_count > limit


def can_place_assignment(
    state: ScheduleState,
    employee_id: int,
    day: int,
    shift_id: int,
    *,
    assignments: Sequence[Assignment] | None = None,
) -> bool:
    """Check all hard automatic-placement rules against a current roster."""
    employee = next((item for item in state.employees if item.id == employee_id), None)
    shift = next((item for item in state.shifts if item.id == shift_id), None)
    if (
        employee is None
        or shift is None
        or not _valid_assignment_references(state, employee_id, day, shift_id)
    ):
        return False
    try:
        validate_shift_range(shift.start_hour, shift.end_hour)
    except SchedulingError:
        return False
    current = state.assignments if assignments is None else assignments
    assigned_hours = 0
    day_shifts = []
    seen: set[tuple[int, int, int]] = set()
    shifts = {item.id: item for item in state.shifts}
    for assignment in current:
        if not _valid_assignment_references(
            state, assignment.employee_id, assignment.day, assignment.shift_id
        ):
            return False
        key = (assignment.employee_id, assignment.day, assignment.shift_id)
        if _assignment_is_duplicate(key, seen):
            return False
        seen.add(key)
        if assignment.employee_id != employee_id:
            continue
        other_shift = shifts[assignment.shift_id]
        assigned_hours += other_shift.end_hour - other_shift.start_hour
        if assignment.day == day:
            day_shifts.append(other_shift)
            if _overlaps_shift(shift, other_shift):
                return False
    if _assignment_is_duplicate((employee_id, day, shift_id), seen):
        return False
    if _exceeds_weekly_limit(
        assigned_hours + shift.end_hour - shift.start_hour, employee.weekly_max_hours
    ):
        return False
    if _exceeds_daily_limit(len(day_shifts) + 1, state.daily_shift_limit):
        return False
    return True


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
        if (
            employee is None
            or shift is None
            or not _valid_assignment_references(
                state, assignment.employee_id, assignment.day, assignment.shift_id
            )
        ):
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
        if _assignment_is_duplicate(key, seen):
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
            if _overlaps_shift(shift, other_shift):
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
        if _exceeds_weekly_limit(assigned, employee.weekly_max_hours):
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
        if _exceeds_daily_limit(len(assigned_shifts), state.daily_shift_limit):
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
