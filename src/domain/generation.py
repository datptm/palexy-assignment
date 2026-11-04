"""Pure deterministic roster generation and transient diagnostics."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from fractions import Fraction
from math import lcm

from src.domain.demand import required_staff, validate_demand
from src.domain.limits import bounded_int, checked_total
from src.domain.metrics import calculate_result
from src.domain.shifts import validate_shift_range
from src.domain.validation import (
    _assignment_is_duplicate,
    _exceeds_daily_limit,
    _exceeds_weekly_limit,
    _overlaps_shift,
    _valid_assignment_references,
    can_place_assignment,
    validate_state,
)
from src.model.scheduling import (
    AddCandidate,
    Assignment,
    DemandCell,
    Employee,
    EmployeeMetric,
    GenerationConfig,
    GenerationDiagnostics,
    GenerationEmployeeDiagnostic,
    GenerationOutcome,
    GenerationShortfall,
    GenerationTrace,
    HourlyMetric,
    RosterSlot,
    ScheduleResult,
    ScheduleState,
    SchedulingError,
    ShiftDefinition,
    WeeklyMetric,
)

MAX_CANDIDATE_EVALUATIONS = 50_000_000
MAX_PREFLIGHT_CANDIDATE_SPACE = 100_000
MAX_TRACE_RECORDS = 250_000
COST_DENSITY_SCALE = lcm(*range(1, 17))


@dataclass(frozen=True)
class _Prepared:
    state: ScheduleState
    config: GenerationConfig
    employees: tuple[Employee, ...]
    shifts: tuple[ShiftDefinition, ...]
    required: dict[tuple[int, int], int]
    capacities: dict[int, int]
    employee_order: dict[int, int]
    shift_order: dict[int, int]
    shift_by_id: dict[int, ShiftDefinition]
    employee_ids: frozenset[int]
    shift_ids: frozenset[int]
    covered_hours: dict[int, tuple[int, ...]]
    capacity_total: int
    required_total: int


class _WorkBudget:
    """Count search operations instead of relying on nondeterministic timeouts."""

    def __init__(self) -> None:
        self.evaluations = 0

    def tick(self) -> None:
        self.evaluations += 1
        if self.evaluations > MAX_CANDIDATE_EVALUATIONS:
            raise SchedulingError(
                "GENERATION_WORK_LIMIT",
                "generation exceeded its deterministic candidate-work budget",
                {"limit": MAX_CANDIDATE_EVALUATIONS},
            )


def _validate_config(config: GenerationConfig) -> None:
    if not isinstance(config, GenerationConfig):
        raise SchedulingError("INVALID_GENERATION_CONFIG", "generation config has an invalid type")
    values = (
        ("day_count", config.day_count, 1),
        ("open_start_hour", config.open_start_hour, 0),
        ("open_end_hour", config.open_end_hour, 1),
        ("w_under", config.w_under, 1),
        ("w_over", config.w_over, 1),
        ("w_empty", config.w_empty, 1),
        ("max_passes", config.max_passes, 1),
        ("max_moves", config.max_moves, 1),
        ("rest_weight", config.rest_weight, 0),
    )
    for field, value, minimum in values:
        if type(value) is not int or value < minimum:
            raise SchedulingError(
                "INVALID_GENERATION_CONFIG",
                f"{field} must be an integer >= {minimum}",
                {"field": field},
            )
    if config.day_count > 7:
        raise SchedulingError("INVALID_GENERATION_CONFIG", "day_count cannot exceed 7")
    if not 0 <= config.open_start_hour < config.open_end_hour <= 24:
        raise SchedulingError(
            "INVALID_GENERATION_CONFIG", "operating hours must satisfy 0 <= start < end <= 24"
        )
    if config.w_under <= config.w_over or config.w_empty < config.w_under:
        raise SchedulingError(
            "INVALID_GENERATION_CONFIG",
            "weights must satisfy w_empty >= w_under > w_over >= 1",
        )


def effective_capacity(maximum: int, durations: Iterable[int], max_shifts: int) -> int:
    """Return exact reachable shift hours without allocating by weekly maximum.

    For largest duration ``q``, the residue DP is bounded by
    ``(q - 1) * sum(distinct smaller durations)``.
    """
    maximum = bounded_int(maximum, field="maximum", minimum=0)
    max_shifts = bounded_int(max_shifts, field="max_shifts", minimum=0)
    duration_values = tuple(durations)
    if any(type(duration) is not int or not 1 <= duration <= 16 for duration in duration_values):
        raise SchedulingError(
            "INVALID_GENERATION_INPUT", "shift durations must be whole hours from 1 to 16"
        )
    distinct = tuple(sorted(set(duration_values)))
    if maximum == 0 or max_shifts == 0 or not distinct:
        return 0
    largest = distinct[-1]
    smaller = distinct[:-1]
    bound = (largest - 1) * sum(smaller)
    infinity = max_shifts + 1
    minimum_coins = [infinity] * (bound + 1)
    minimum_coins[0] = 0
    for duration in smaller:
        for total in range(duration, bound + 1):
            candidate_count = minimum_coins[total - duration] + 1
            if candidate_count < minimum_coins[total]:
                minimum_coins[total] = candidate_count

    upper = min(maximum, max_shifts * largest)
    lower = max(0, upper - largest + 1)
    for target in range(upper, lower - 1, -1):
        coin_count = min(
            (
                minimum_coins[base] + (target - base) // largest
                for base in range(min(bound, target) + 1)
                if base % largest == target % largest and minimum_coins[base] <= max_shifts
            ),
            default=infinity,
        )
        if coin_count <= max_shifts:
            return target
    return 0


def _required_counts(state: ScheduleState, config: GenerationConfig) -> dict[tuple[int, int], int]:
    if state.demand is None:
        raise SchedulingError("INVALID_DEMAND", "a complete demand grid is required")
    if type(state.threshold) is not int or state.threshold < 1:
        raise SchedulingError("INVALID_DEMAND", "threshold must be a positive integer")
    expected = {
        (day, hour)
        for day in range(config.day_count)
        for hour in range(config.open_start_hour, config.open_end_hour)
    }
    if expected == {(day, hour) for day in range(7) for hour in range(7, 23)}:
        try:
            validate_demand(state.demand, state.threshold)
        except (SchedulingError, TypeError, AttributeError) as error:
            raise SchedulingError("INVALID_DEMAND", "demand contains invalid values") from error
    counts: dict[tuple[int, int], int] = {}
    transaction_total = 0
    for cell in state.demand:
        if (
            not isinstance(cell, DemandCell)
            or type(cell.day) is not int
            or type(cell.hour) is not int
            or type(cell.transactions) is not int
            or cell.transactions < 0
        ):
            raise SchedulingError("INVALID_DEMAND", "demand cells must contain integer values")
        key = (cell.day, cell.hour)
        if key not in expected or key in counts:
            raise SchedulingError("INVALID_DEMAND", "demand cells are duplicated or out of range")
        try:
            transaction_total += bounded_int(cell.transactions, field="transactions")
        except SchedulingError as error:
            raise SchedulingError(
                "INVALID_DEMAND", "demand count is outside its valid range"
            ) from error
        counts[key] = max(1, (cell.transactions + state.threshold - 1) // state.threshold)
    if counts.keys() != expected:
        raise SchedulingError("INVALID_DEMAND", "demand must cover every configured open hour")
    try:
        checked_total(transaction_total, field="weekly_transactions")
        checked_total(sum(counts.values()), field="weekly_required_staff")
    except SchedulingError as error:
        raise SchedulingError(
            "INVALID_DEMAND", "weekly demand exceeds its supported range"
        ) from error
    return counts


def _prepare(state: ScheduleState, config: GenerationConfig) -> tuple[_Prepared | None, str | None]:
    _validate_config(config)
    if not isinstance(state, ScheduleState):
        raise SchedulingError("INVALID_GENERATION_INPUT", "schedule state has an invalid type")
    if state.demand is None:
        return None, "NO_DEMAND"
    if not state.shifts:
        return None, "NO_SHIFTS"
    if type(state.daily_shift_limit) is not int or state.daily_shift_limit < 1:
        raise SchedulingError("INVALID_GENERATION_INPUT", "daily shift limit must be positive")
    for employee in state.employees:
        if (
            not isinstance(employee, Employee)
            or type(employee.id) is not int
            or type(employee.weekly_max_hours) is not int
        ):
            raise SchedulingError("INVALID_GENERATION_INPUT", "employee data is invalid")
    for shift in state.shifts:
        if (
            not isinstance(shift, ShiftDefinition)
            or type(shift.id) is not int
            or type(shift.start_hour) is not int
            or type(shift.end_hour) is not int
        ):
            raise SchedulingError("INVALID_GENERATION_INPUT", "shift data is invalid")
    employees = tuple(sorted(state.employees, key=lambda item: item.id))
    shifts = tuple(sorted(state.shifts, key=lambda item: (item.start_hour, item.end_hour, item.id)))
    employee_ids: set[int] = set()
    for employee in employees:
        if (
            type(employee.id) is not int
            or employee.id < 1
            or employee.id in employee_ids
            or type(employee.weekly_max_hours) is not int
            or not 0 <= employee.weekly_max_hours <= 2**31 - 1
        ):
            raise SchedulingError("INVALID_GENERATION_INPUT", "employee data is invalid")
        employee_ids.add(employee.id)

    shift_ids: set[int] = set()
    shift_ranges: set[tuple[int, int]] = set()
    for shift in shifts:
        if (
            type(shift.id) is not int
            or shift.id < 1
            or shift.id in shift_ids
            or type(shift.start_hour) is not int
            or type(shift.end_hour) is not int
        ):
            raise SchedulingError("INVALID_GENERATION_INPUT", "shift data is invalid")
        try:
            validate_shift_range(shift.start_hour, shift.end_hour)
        except SchedulingError as error:
            raise SchedulingError("INVALID_GENERATION_INPUT", "shift data is invalid") from error
        key = (shift.start_hour, shift.end_hour)
        if key in shift_ranges:
            raise SchedulingError("INVALID_GENERATION_INPUT", "shift times must be unique")
        shift_ids.add(shift.id)
        shift_ranges.add(key)

    durations = tuple(shift.end_hour - shift.start_hour for shift in shifts)
    max_shifts = config.day_count * state.daily_shift_limit
    capacities = {
        employee.id: effective_capacity(employee.weekly_max_hours, durations, max_shifts)
        for employee in employees
    }
    shortest = min(durations)
    if not any(
        capacities[employee.id] > 0 and employee.weekly_max_hours >= shortest
        for employee in employees
    ):
        return None, "NO_ELIGIBLE_STAFF"

    required = _required_counts(state, config)
    covered_hours = {
        shift.id: tuple(
            range(
                max(config.open_start_hour, shift.start_hour),
                min(config.open_end_hour, shift.end_hour),
            )
        )
        for shift in shifts
    }
    prepared = _Prepared(
        state,
        config,
        employees,
        shifts,
        required,
        capacities,
        {employee.id: index for index, employee in enumerate(employees)},
        {shift.id: index for index, shift in enumerate(shifts)},
        {shift.id: shift for shift in shifts},
        frozenset(employee_ids),
        frozenset(shift_ids),
        covered_hours,
        sum(capacities.values()),
        sum(required.values()),
    )
    _preflight_work(prepared)
    return prepared, None


def _preflight_work(prepared: _Prepared) -> None:
    """Reject oversized candidate and trace workloads before starting search."""
    candidate_space = len(prepared.employees) * prepared.config.day_count * len(prepared.shifts)
    if candidate_space > MAX_PREFLIGHT_CANDIDATE_SPACE:
        raise SchedulingError(
            "GENERATION_WORK_LIMIT",
            "generation candidate space exceeds its deterministic preflight budget",
            {"candidate_space": candidate_space, "limit": MAX_PREFLIGHT_CANDIDATE_SPACE},
        )
    shortest = min(shift.end_hour - shift.start_hour for shift in prepared.shifts)
    daily_bound = prepared.config.day_count * prepared.state.daily_shift_limit
    assignment_bound = sum(
        min(daily_bound, employee.weekly_max_hours // shortest) for employee in prepared.employees
    )
    actions_bound = min(
        prepared.config.max_moves, assignment_bound * 4 * prepared.config.max_passes
    )
    if actions_bound > MAX_TRACE_RECORDS:
        raise SchedulingError(
            "GENERATION_WORK_LIMIT",
            "generation trace exceeds its deterministic preflight budget",
            {"trace_records": actions_bound, "limit": MAX_TRACE_RECORDS},
        )
    estimated_work = (
        candidate_space
        * (
            min(prepared.config.max_moves, max(1, assignment_bound))
            + prepared.config.max_passes
            + 1
        )
        + assignment_bound
        * (prepared.config.day_count * len(prepared.shifts) + len(prepared.employees))
        * prepared.config.max_passes
    )
    if estimated_work > MAX_CANDIDATE_EVALUATIONS:
        raise SchedulingError(
            "GENERATION_WORK_LIMIT",
            "generation estimated work exceeds its deterministic preflight budget",
            {"estimated_work": estimated_work, "limit": MAX_CANDIDATE_EVALUATIONS},
        )


def _blocked(code: str) -> GenerationOutcome:
    messages = {
        "NO_DEMAND": "Import a complete transaction report before generating a roster.",
        "NO_SHIFTS": "Add at least one valid shift before generating a roster.",
        "NO_ELIGIBLE_STAFF": "Add an employee with capacity for at least one configured shift.",
    }
    return GenerationOutcome(code, messages[code], None, None, None)


class _Roster:
    """Mutable per-call search state with incremental hours and coverage counts."""

    def __init__(self, prepared: _Prepared, assignments: Iterable[Assignment] = ()) -> None:
        self.prepared = prepared
        initial_assignments = tuple(assignments)
        self.assignments: list[Assignment] = []
        self.placements: set[tuple[int, int, int]] = set()
        self.hours = {employee.id: 0 for employee in prepared.employees}
        self.day_shifts: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.counts = {
            (day, hour): 0
            for day in range(prepared.config.day_count)
            for hour in range(prepared.config.open_start_hour, prepared.config.open_end_hour)
        }
        self.next_assignment_id = 1
        for assignment in initial_assignments:
            if (
                not isinstance(assignment, Assignment)
                or type(assignment.id) is not int
                or assignment.id < 1
                or not self._references_valid(
                    assignment.employee_id, assignment.day, assignment.shift_id
                )
            ):
                raise SchedulingError("INVALID_GENERATION_INPUT", "assignment reference is invalid")
            if not self._can_add(assignment.employee_id, assignment.day, assignment.shift_id):
                raise SchedulingError(
                    "INVALID_GENERATION_INPUT", "initial roster violates hard limits"
                )
            self._apply_add(assignment, check=False)
            self.next_assignment_id = max(self.next_assignment_id, assignment.id + 1)

    @property
    def total_hours(self) -> int:
        return sum(self.hours.values())

    def _references_valid(self, employee_id: int, day: int, shift_id: int) -> bool:
        return _valid_assignment_references(
            self.prepared.state,
            employee_id,
            day,
            shift_id,
            employee_ids=self.prepared.employee_ids,
            shift_ids=self.prepared.shift_ids,
            day_count=self.prepared.config.day_count,
        )

    def _can_add(self, employee_id: int, day: int, shift_id: int) -> bool:
        if not self._references_valid(employee_id, day, shift_id):
            return False
        if _assignment_is_duplicate((employee_id, day, shift_id), self.placements):
            return False
        shift = self.prepared.shift_by_id[shift_id]
        duration = shift.end_hour - shift.start_hour
        employee = self.prepared.employees[self.prepared.employee_order[employee_id]]
        if _exceeds_weekly_limit(self.hours[employee_id] + duration, employee.weekly_max_hours):
            return False
        day_key = (employee_id, day)
        if _exceeds_daily_limit(
            len(self.day_shifts[day_key]) + 1, self.prepared.state.daily_shift_limit
        ):
            return False
        return not any(
            _overlaps_shift(shift, self.prepared.shift_by_id[other_id])
            for other_id in self.day_shifts[day_key]
        )

    def _apply_add(self, assignment: Assignment, *, check: bool = True) -> None:
        if check and not self._can_add(assignment.employee_id, assignment.day, assignment.shift_id):
            raise SchedulingError("INVALID_GENERATION_INPUT", "assignment violates hard limits")
        shift = self.prepared.shift_by_id[assignment.shift_id]
        self.assignments.append(assignment)
        self.placements.add((assignment.employee_id, assignment.day, assignment.shift_id))
        self.hours[assignment.employee_id] += shift.end_hour - shift.start_hour
        self.day_shifts[(assignment.employee_id, assignment.day)].append(assignment.shift_id)
        for hour in self.prepared.covered_hours[assignment.shift_id]:
            self.counts[(assignment.day, hour)] += 1

    def _remove(self, assignment: Assignment) -> None:
        self.assignments.remove(assignment)
        self.placements.remove((assignment.employee_id, assignment.day, assignment.shift_id))
        shift = self.prepared.shift_by_id[assignment.shift_id]
        self.hours[assignment.employee_id] -= shift.end_hour - shift.start_hour
        self.day_shifts[(assignment.employee_id, assignment.day)].remove(assignment.shift_id)
        for hour in self.prepared.covered_hours[assignment.shift_id]:
            self.counts[(assignment.day, hour)] -= 1

    def _added_cost(self, day: int, shift_id: int) -> tuple[int, int]:
        delta = excess = 0
        for hour in self.prepared.covered_hours[shift_id]:
            count = self.counts[(day, hour)]
            required = self.prepared.required[(day, hour)]
            if count == 0:
                delta -= self.prepared.config.w_empty
            elif count < required:
                delta -= self.prepared.config.w_under
            else:
                delta += self.prepared.config.w_over
            excess += count >= required
        return delta, excess

    def _removed_cost(self, day: int, shift_id: int) -> int:
        delta = 0
        for hour in self.prepared.covered_hours[shift_id]:
            count = self.counts[(day, hour)]
            required = self.prepared.required[(day, hour)]
            if count > required:
                delta -= self.prepared.config.w_over
            elif count == 1:
                delta += self.prepared.config.w_empty
            else:
                delta += self.prepared.config.w_under
        return delta

    def primary_cost(self) -> int:
        cost = 0
        for key, required in self.prepared.required.items():
            scheduled = self.counts[key]
            if scheduled == 0:
                cost += self.prepared.config.w_empty
                cost += (required - 1) * self.prepared.config.w_under
            elif scheduled < required:
                cost += (required - scheduled) * self.prepared.config.w_under
            else:
                cost += (scheduled - required) * self.prepared.config.w_over
        return cost

    def fairness_cost(self) -> int:
        total_capacity = self.prepared.capacity_total
        if total_capacity == 0:
            return 0
        total_hours = self.total_hours
        return sum(
            abs(
                self.hours[employee.id] * total_capacity
                - total_hours * self.prepared.capacities[employee.id]
            )
            for employee in self.prepared.employees
        )

    def state(self) -> ScheduleState:
        ordered = tuple(sorted(self.assignments, key=self.assignment_key))
        return replace(self.prepared.state, assignments=ordered)

    def assignment_key(self, assignment: Assignment) -> tuple[int, int, int]:
        return (
            self.prepared.employee_order[assignment.employee_id],
            assignment.day,
            self.prepared.shift_order[assignment.shift_id],
        )


def _fairness_deltas(roster: _Roster) -> dict[tuple[int, int], int]:
    total_capacity = roster.prepared.capacity_total
    if total_capacity == 0:
        return {}
    old_total = roster.total_hours
    capacities = roster.prepared.capacities
    old_cost = roster.fairness_cost()
    durations = {shift.end_hour - shift.start_hour for shift in roster.prepared.shifts}
    result = {}
    for duration in durations:
        new_total = old_total + duration
        new_term_total = sum(
            abs(roster.hours[employee.id] * total_capacity - new_total * capacities[employee.id])
            for employee in roster.prepared.employees
        )
        for employee in roster.prepared.employees:
            unchanged_term = abs(
                roster.hours[employee.id] * total_capacity - new_total * capacities[employee.id]
            )
            changed_term = abs(
                (roster.hours[employee.id] + duration) * total_capacity
                - new_total * capacities[employee.id]
            )
            result[(employee.id, duration)] = (
                new_term_total - unchanged_term + changed_term - old_cost
            )
    return result


def _rank_candidates(
    prepared: _Prepared, roster: _Roster, budget: _WorkBudget
) -> tuple[AddCandidate, ...]:
    candidates = []
    fairness = _fairness_deltas(roster)
    for employee in prepared.employees:
        if prepared.capacities[employee.id] <= 0:
            continue
        for day in range(prepared.config.day_count):
            for shift in prepared.shifts:
                budget.tick()
                if not roster._can_add(employee.id, day, shift.id):
                    continue
                delta_cost, excess_added = roster._added_cost(day, shift.id)
                if delta_cost < 0:
                    duration = shift.end_hour - shift.start_hour
                    candidates.append(
                        AddCandidate(
                            employee.id,
                            day,
                            shift.id,
                            delta_cost,
                            fairness[(employee.id, duration)],
                            excess_added,
                            duration,
                        )
                    )
    candidates.sort(
        key=lambda candidate: (
            candidate.delta_cost * (COST_DENSITY_SCALE // candidate.duration),
            candidate.excess_added,
            candidate.delta_fairness,
            prepared.employee_order[candidate.employee_id],
            candidate.employee_id,
            candidate.day,
            prepared.shift_order[candidate.shift_id],
        )
    )
    return tuple(candidates)


def rank_add_candidates(
    state: ScheduleState, config: GenerationConfig | None = None
) -> tuple[AddCandidate, ...]:
    """Return feasible negative-cost additions in exact deterministic rank order."""
    prepared, blocked_code = _prepare(state, config or GenerationConfig())
    if prepared is None:
        if blocked_code == "NO_DEMAND":
            raise SchedulingError("INVALID_DEMAND", "a complete demand grid is required")
        return ()
    roster = _Roster(prepared, state.assignments)
    return _rank_candidates(prepared, roster, _WorkBudget())


def can_auto_assign(state: ScheduleState, employee_id: int, day: int, shift_id: int) -> bool:
    """Return whether a candidate satisfies automatic hard assignment rules."""
    return can_place_assignment(state, employee_id, day, shift_id)


def _record(
    trace: list[GenerationTrace],
    phase: str,
    action: str,
    employee_id: int,
    day: int,
    shift_id: int,
    delta_cost: int,
    delta_fairness: int,
    explanation: str,
    *,
    source_employee_id: int | None = None,
    source_day: int | None = None,
    source_shift_id: int | None = None,
) -> None:
    trace.append(
        GenerationTrace(
            len(trace) + 1,
            phase,
            action,
            employee_id,
            day,
            shift_id,
            delta_cost,
            delta_fairness,
            explanation,
            source_employee_id,
            source_day,
            source_shift_id,
        )
    )


def _add_closure(
    prepared: _Prepared,
    roster: _Roster,
    trace: list[GenerationTrace],
    budget: _WorkBudget,
    phase: str,
    refinement_start: int | None = None,
) -> tuple[int, bool]:
    changes = 0
    while True:
        candidates = _rank_candidates(prepared, roster, budget)
        if not candidates:
            return changes, False
        if (
            refinement_start is not None
            and len(trace) - refinement_start >= prepared.config.max_moves
        ):
            return changes, True
        candidate = candidates[0]
        assignment = Assignment(
            roster.next_assignment_id,
            candidate.employee_id,
            candidate.day,
            candidate.shift_id,
        )
        roster.next_assignment_id += 1
        roster._apply_add(assignment)
        _record(
            trace,
            phase,
            "ADD",
            candidate.employee_id,
            candidate.day,
            candidate.shift_id,
            candidate.delta_cost,
            candidate.delta_fairness,
            "Added a feasible shift with negative primary cost.",
        )
        changes += 1


def _drop_pass(
    prepared: _Prepared,
    roster: _Roster,
    trace: list[GenerationTrace],
    budget: _WorkBudget,
    refinement_start: int,
) -> tuple[int, bool]:
    changes = 0
    for assignment in sorted(tuple(roster.assignments), key=roster.assignment_key):
        if assignment not in roster.assignments:
            continue
        before_cost = roster.primary_cost()
        before_fairness = roster.fairness_cost()
        roster._remove(assignment)
        delta_cost = roster.primary_cost() - before_cost
        delta_fairness = roster.fairness_cost() - before_fairness
        budget.tick()
        if delta_cost >= 0:
            roster._apply_add(assignment)
            continue
        if len(trace) - refinement_start >= prepared.config.max_moves:
            roster._apply_add(assignment)
            return changes, True
        _record(
            trace,
            "DROP",
            "DROP",
            assignment.employee_id,
            assignment.day,
            assignment.shift_id,
            delta_cost,
            delta_fairness,
            "Removed a shift that reduced primary cost.",
        )
        changes += 1
    return changes, False


def _move_pass(
    prepared: _Prepared,
    roster: _Roster,
    trace: list[GenerationTrace],
    budget: _WorkBudget,
    refinement_start: int,
) -> tuple[int, bool]:
    changes = 0
    for source in sorted(tuple(roster.assignments), key=roster.assignment_key):
        if source not in roster.assignments:
            continue
        before_cost = roster.primary_cost()
        before_fairness = roster.fairness_cost()
        roster._remove(source)
        removed_cost = roster.primary_cost()
        removed_fairness = roster.fairness_cost()
        fairness_deltas = _fairness_deltas(roster)
        best: tuple[tuple[int, int, int, int], int, int, int, int] | None = None
        for day in range(prepared.config.day_count):
            for shift in prepared.shifts:
                budget.tick()
                if (day, shift.id) == (source.day, source.shift_id):
                    continue
                if not roster._can_add(source.employee_id, day, shift.id):
                    continue
                duration = shift.end_hour - shift.start_hour
                delta_cost = removed_cost - before_cost + roster._added_cost(day, shift.id)[0]
                delta_fairness = (
                    removed_fairness
                    - before_fairness
                    + fairness_deltas[(source.employee_id, duration)]
                )
                if delta_cost < 0 or (delta_cost == 0 and delta_fairness < 0):
                    key = (delta_cost, delta_fairness, day, prepared.shift_order[shift.id])
                    candidate = (key, day, shift.id, delta_cost, delta_fairness)
                    if best is None or candidate[0] < best[0]:
                        best = candidate
        if best is None:
            roster._apply_add(source)
            continue
        if len(trace) - refinement_start >= prepared.config.max_moves:
            roster._apply_add(source)
            return changes, True
        _, day, shift_id, delta_cost, delta_fairness = best
        roster._apply_add(Assignment(source.id, source.employee_id, day, shift_id))
        _record(
            trace,
            "MOVE",
            "MOVE",
            source.employee_id,
            day,
            shift_id,
            delta_cost,
            delta_fairness,
            "Moved a shift to a better feasible slot.",
            source_day=source.day,
            source_shift_id=source.shift_id,
        )
        changes += 1
    return changes, False


def _replace_pass(
    prepared: _Prepared,
    roster: _Roster,
    trace: list[GenerationTrace],
    budget: _WorkBudget,
    refinement_start: int,
) -> tuple[int, bool]:
    changes = 0
    for source in sorted(tuple(roster.assignments), key=roster.assignment_key):
        if source not in roster.assignments:
            continue
        before_fairness = roster.fairness_cost()
        roster._remove(source)
        removed_fairness = roster.fairness_cost()
        fairness_deltas = _fairness_deltas(roster)
        best: tuple[int, int] | None = None
        for employee in prepared.employees:
            budget.tick()
            if not roster._can_add(employee.id, source.day, source.shift_id):
                continue
            shift = prepared.shift_by_id[source.shift_id]
            duration = shift.end_hour - shift.start_hour
            delta_fairness = (
                removed_fairness - before_fairness + fairness_deltas[(employee.id, duration)]
            )
            if delta_fairness < 0:
                candidate = (delta_fairness, prepared.employee_order[employee.id])
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            roster._apply_add(source)
            continue
        if len(trace) - refinement_start >= prepared.config.max_moves:
            roster._apply_add(source)
            return changes, True
        delta_fairness, employee_index = best
        replacement_employee = prepared.employees[employee_index]
        roster._apply_add(
            Assignment(source.id, replacement_employee.id, source.day, source.shift_id)
        )
        _record(
            trace,
            "REPLACE",
            "REPLACE",
            replacement_employee.id,
            source.day,
            source.shift_id,
            0,
            delta_fairness,
            "Replaced the assignee without changing coverage to improve fair share.",
            source_employee_id=source.employee_id,
        )
        changes += 1
    return changes, False


def _refine(
    prepared: _Prepared,
    roster: _Roster,
    trace: list[GenerationTrace],
    budget: _WorkBudget,
) -> bool:
    last_changes = 0
    refinement_start = len(trace)
    for _ in range(prepared.config.max_passes):
        pass_changes = 0
        added, capped = _add_closure(prepared, roster, trace, budget, "ADD", refinement_start)
        pass_changes += added
        if capped:
            return True
        for operation in (_drop_pass, _move_pass, _replace_pass):
            changed, capped = operation(prepared, roster, trace, budget, refinement_start)
            pass_changes += changed
            if capped:
                return True
        last_changes = pass_changes
        if pass_changes == 0:
            return False
    return last_changes > 0


def _shortfalls(prepared: _Prepared, roster: _Roster) -> tuple[GenerationShortfall, ...]:
    result: list[GenerationShortfall] = []
    has_capacity = any(capacity > 0 for capacity in prepared.capacities.values())
    for day in range(prepared.config.day_count):
        for shift in prepared.shifts:
            covered_hours = prepared.covered_hours[shift.id]
            unmet = sum(
                max(0, prepared.required[(day, hour)] - roster.counts[(day, hour)])
                for hour in covered_hours
            )
            if not unmet:
                continue
            delta_cost = sum(
                -prepared.config.w_empty
                if roster.counts[(day, hour)] == 0
                else -prepared.config.w_under
                if roster.counts[(day, hour)] < prepared.required[(day, hour)]
                else prepared.config.w_over
                for hour in covered_hours
            )
            duration = shift.end_hour - shift.start_hour
            if not has_capacity:
                reason = "NO_ELIGIBLE_STAFF"
            elif delta_cost >= 0:
                reason = "STOP_RULE"
            elif not any(
                roster.hours[employee.id] + duration <= employee.weekly_max_hours
                for employee in prepared.employees
            ):
                reason = "CAPACITY"
            else:
                reason = "DAY_CONSTRAINTS"
            messages = {
                "NO_ELIGIBLE_STAFF": "No employee has positive effective shift capacity.",
                "STOP_RULE": "Adding another employee to this shift would not lower optimizer cost.",
                "CAPACITY": "No employee has enough weekly hours remaining for this shift.",
                "DAY_CONSTRAINTS": (
                    "Daily shift limits, overlap, or an existing assignment blocks this slot."
                ),
            }
            result.append(
                GenerationShortfall("slot", reason, unmet, messages[reason], day, shift_id=shift.id)
            )

    covered = {
        hour for shift in prepared.shifts for hour in range(shift.start_hour, shift.end_hour)
    }
    for day in range(prepared.config.day_count):
        for hour in range(prepared.config.open_start_hour, prepared.config.open_end_hour):
            if hour not in covered and roster.counts[(day, hour)] < prepared.required[(day, hour)]:
                result.append(
                    GenerationShortfall(
                        "hour",
                        "NO_SHIFT_COVERAGE",
                        prepared.required[(day, hour)] - roster.counts[(day, hour)],
                        "No configured shift covers this open hour.",
                        day,
                        hour=hour,
                    )
                )
    return tuple(result)


def _has_feasible_replacement(prepared: _Prepared, roster: _Roster) -> bool:
    for assignment in tuple(roster.assignments):
        roster._remove(assignment)
        feasible = any(
            employee.id != assignment.employee_id
            and roster._can_add(employee.id, assignment.day, assignment.shift_id)
            for employee in prepared.employees
        )
        roster._apply_add(assignment)
        if feasible:
            return True
    return False


def _diagnostics(
    prepared: _Prepared,
    roster: _Roster,
    trace: list[GenerationTrace],
    capped: bool,
) -> GenerationDiagnostics:
    total_hours = roster.total_hours
    capacity_total = prepared.capacity_total
    primary = roster.primary_cost()
    fairness = roster.fairness_cost()
    employees = []
    effective_utils: list[Fraction] = []
    for employee in prepared.employees:
        capacity = prepared.capacities[employee.id]
        assigned = roster.hours[employee.id]
        if capacity:
            effective_utils.append(Fraction(assigned, capacity))
        employees.append(
            GenerationEmployeeDiagnostic(
                employee.id,
                assigned,
                employee.weekly_max_hours,
                capacity,
                assigned / employee.weekly_max_hours if employee.weekly_max_hours else "N/A",
                assigned / capacity if capacity else "N/A",
                total_hours * capacity / capacity_total if capacity_total else 0.0,
                abs(assigned - total_hours * capacity / capacity_total) if capacity_total else 0.0,
            )
        )

    flags = []
    flag_messages = []
    if effective_utils:
        mean_utilization = sum(effective_utils, Fraction()) / len(effective_utils)
        if any(value * 2 < mean_utilization for value in effective_utils):
            flags.append("LOW_UTILIZATION")
            flag_messages.append(
                (
                    "LOW_UTILIZATION",
                    "At least one employee is below half the mean effective utilization.",
                )
            )
        shortest = min(shift.end_hour - shift.start_hour for shift in prepared.shifts)
        near_zero = any(
            prepared.capacities[employee.id] > 0
            and roster.hours[employee.id] <= shortest
            and any(
                other.id != employee.id
                and prepared.capacities[other.id] > 0
                and roster.hours[other.id] * 10 >= prepared.capacities[other.id] * 9
                for other in prepared.employees
            )
            for employee in prepared.employees
        )
        if near_zero:
            flags.append("NEAR_ZERO_WHILE_OTHERS_FULL")
            if not _has_feasible_replacement(prepared, roster):
                flag_messages.append(
                    (
                        "NEAR_ZERO_WHILE_OTHERS_FULL",
                        "No feasible coverage-neutral reassignment remains under current limits.",
                    )
                )
    if capped:
        flags.append("REFINEMENT_CAPPED")
        flag_messages.append(
            (
                "REFINEMENT_CAPPED",
                "Search stopped at a deterministic cap; this is the current valid draft.",
            )
        )

    unavoidable = max(0, prepared.required_total - capacity_total)
    message = (
        f"At least {unavoidable} of the actual unmet staff-hours cannot be avoided "
        "with current staff capacity."
    )
    return GenerationDiagnostics(
        primary,
        fairness,
        fairness / capacity_total if capacity_total else 0.0,
        prepared.required_total,
        capacity_total,
        unavoidable,
        message,
        tuple(employees),
        _shortfalls(prepared, roster),
        tuple(flags),
        tuple(flag_messages),
        tuple(trace),
        0,
        capped,
    )


def _custom_result(state: ScheduleState, diagnostics: GenerationDiagnostics) -> ScheduleResult:
    demand = {(item.day, item.hour): item.transactions for item in state.demand or ()}
    shift_by_id = {shift.id: shift for shift in state.shifts}
    employee_hours: Counter[int] = Counter()
    coverage: Counter[tuple[int, int]] = Counter()
    for assignment in state.assignments:
        shift = shift_by_id[assignment.shift_id]
        employee_hours[assignment.employee_id] += shift.end_hour - shift.start_hour
        for hour in range(shift.start_hour, shift.end_hour):
            coverage[(assignment.day, hour)] += 1

    hourly = []
    totals = [0, 0, 0, 0, 0]
    staffed_ratios = []
    for day in range(7):
        for hour in range(7, 23):
            scheduled = coverage[(day, hour)]
            transactions = demand.get((day, hour))
            if transactions is None:
                hourly.append(
                    HourlyMetric(day, hour, None, None, scheduled, None, None, None, None)
                )
                continue
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
            totals[0] += transactions
            totals[1] += required
            totals[2] += covered
            totals[3] += unmet
            totals[4] += excess
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
    scheduled_total = checked_total(sum(coverage.values()), field="scheduled_staff_hours")
    weekly = WeeklyMetric(
        totals[0],
        totals[1],
        scheduled_total,
        totals[2],
        totals[3],
        totals[4],
        totals[2] / totals[1] if totals[1] else None,
        totals[0] / scheduled_total if scheduled_total else None,
        sum(staffed_ratios) / len(staffed_ratios) if staffed_ratios else None,
    )
    metrics_by_id = {item.employee_id: item for item in metrics}
    roster = tuple(
        RosterSlot(
            day,
            shift.id,
            shift.start_hour,
            shift.end_hour,
            tuple(
                metrics_by_id[assignment.employee_id]
                for assignment in state.assignments
                if assignment.day == day and assignment.shift_id == shift.id
            ),
        )
        for day in range(7)
        for shift in sorted(
            state.shifts, key=lambda item: (item.start_hour, item.end_hour, item.id)
        )
    )
    warnings = tuple(item for item in validate_state(state) if item.severity == "warning")
    warnings += state.import_warnings
    return ScheduleResult(state, warnings, tuple(hourly), weekly, metrics, roster, diagnostics)


def _make_result(
    draft: ScheduleState, prepared: _Prepared, diagnostics: GenerationDiagnostics
) -> ScheduleResult:
    if (
        prepared.config.day_count == 7
        and prepared.config.open_start_hour == 7
        and prepared.config.open_end_hour == 23
    ):
        return replace(calculate_result(draft), generation_diagnostics=diagnostics)
    return _custom_result(draft, diagnostics)


def _run(
    state: ScheduleState,
    config: GenerationConfig,
    *,
    start_empty: bool,
) -> GenerationOutcome:
    prepared, blocked_code = _prepare(state, config)
    if prepared is None:
        return _blocked(blocked_code or "NO_ELIGIBLE_STAFF")
    roster = _Roster(prepared, () if start_empty else state.assignments)
    trace: list[GenerationTrace] = []
    budget = _WorkBudget()
    if start_empty:
        _, capped = _add_closure(prepared, roster, trace, budget, "CONSTRUCTION")
    else:
        capped = False
    if not capped:
        capped = _refine(prepared, roster, trace, budget)
    diagnostics = _diagnostics(prepared, roster, trace, capped)
    draft = roster.state()
    draft_result = _make_result(draft, prepared, diagnostics)
    return GenerationOutcome(None, "", draft, diagnostics, draft_result)


def generate_roster(
    state: ScheduleState, config: GenerationConfig | None = None
) -> GenerationOutcome:
    """Generate an empty-start roster without mutating state or persistence."""
    return _run(state, config or GenerationConfig(), start_empty=True)


def refine_roster(
    state: ScheduleState, config: GenerationConfig | None = None
) -> GenerationOutcome:
    """Refine the assignments already present in a valid schedule state."""
    return _run(state, config or GenerationConfig(), start_empty=False)


def generate_draft(
    state: ScheduleState, *, shortage_weight: int = 3, excess_weight: int = 1
) -> ScheduleState:
    """Compatibility adapter returning only the generated schedule state."""
    config = GenerationConfig(
        w_under=shortage_weight,
        w_over=excess_weight,
        w_empty=max(shortage_weight * 2, shortage_weight),
    )
    outcome = generate_roster(state, config)
    if outcome.blocked_code is not None:
        legacy_codes = {
            "NO_DEMAND": "MISSING_DEMAND",
            "NO_SHIFTS": "MISSING_SHIFTS",
            "NO_ELIGIBLE_STAFF": "NO_ELIGIBLE_EMPLOYEE",
        }
        raise SchedulingError(legacy_codes[outcome.blocked_code], outcome.message)
    if outcome.draft is None:
        raise SchedulingError("GENERATION_FAILED", "generation produced no draft")
    return outcome.draft
