"""Tests-first contracts for the deterministic scheduling algorithm v2."""

from dataclasses import replace
from itertools import product

import pytest

from src.domain.metrics import calculate_result
from src.model.scheduling import Assignment, DemandCell, Employee, ScheduleState, ShiftDefinition
from tests.scheduling_support import require_symbol


def _config(**overrides):
    config_type = require_symbol("src.domain.generation", "GenerationConfig")
    return config_type(**overrides)


def _state(
    *,
    day_count=1,
    start_hour=7,
    end_hour=8,
    employees=(8,),
    shifts=((7, 8),),
    required=None,
    demand_marker=True,
    daily_shift_limit=1,
    threshold=1,
    assignments=(),
):
    employee_records = tuple(
        Employee(index, f"Employee {index}", maximum)
        for index, maximum in enumerate(employees, start=1)
    )
    shift_records = tuple(
        ShiftDefinition(index, start, end) for index, (start, end) in enumerate(shifts, start=1)
    )
    demand = (
        tuple(
            DemandCell(day, hour, (required or {}).get((day, hour), 1))
            for day, hour in product(range(day_count), range(start_hour, end_hour))
        )
        if demand_marker
        else None
    )
    return ScheduleState(
        id=1,
        name="Synthetic",
        version=0,
        threshold=threshold,
        daily_shift_limit=daily_shift_limit,
        employees=employee_records,
        shifts=shift_records,
        demand=demand,
        assignments=tuple(assignments),
    )


def _run(state, config=None):
    generate_roster = require_symbol("src.domain.generation", "generate_roster")
    return generate_roster(state, config=config or _config())


def _diagnostics(outcome):
    assert outcome.blocked_code is None
    assert outcome.draft is not None
    assert outcome.diagnostics is not None
    return outcome.diagnostics


@pytest.mark.parametrize(
    "state,expected_code",
    [
        (_state(demand_marker=False, shifts=()), "NO_DEMAND"),
        (_state(demand_marker=True, shifts=()), "NO_SHIFTS"),
        (_state(demand_marker=True, employees=(), shifts=((7, 8),)), "NO_ELIGIBLE_STAFF"),
        (_state(demand_marker=True, employees=(0,), shifts=((7, 8),)), "NO_ELIGIBLE_STAFF"),
        (_state(demand_marker=True, employees=(7,), shifts=((7, 15),)), "NO_ELIGIBLE_STAFF"),
    ],
)
def test_pure_generator_reports_prerequisite_blocks_in_order(state, expected_code) -> None:
    outcome = _run(state)

    assert outcome.blocked_code == expected_code
    assert outcome.message.strip()
    assert outcome.draft is None
    assert outcome.diagnostics is None


def test_zero_transactions_are_valid_one_person_demand_and_input_is_unchanged() -> None:
    state = _state(day_count=2, employees=(1,), required={(0, 7): 0, (1, 7): 0})
    before = state

    outcome = _run(state, _config(day_count=2))

    assert outcome.blocked_code is None
    assert state == before
    assert outcome.diagnostics.required_hours == 2
    assert len(outcome.draft.assignments) == 1
    assert outcome.draft.assignments[0].day in (0, 1)


def test_demand_uses_integer_ceiling_and_never_treats_zero_as_missing() -> None:
    transactions = (0, 20, 21, 40, 41)
    state = _state(
        start_hour=7,
        end_hour=12,
        employees=(5,),
        shifts=((7, 12),),
        threshold=20,
        required={(0, hour): count for hour, count in zip(range(7, 12), transactions, strict=True)},
    )
    outcome = _run(state, _config(open_end_hour=12))

    assert outcome.diagnostics.required_hours == 9
    assert outcome.blocked_code is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"w_under": 1},
        {"w_over": 0},
        {"w_empty": 2},
        {"max_passes": 0},
        {"max_moves": -1},
        {"rest_weight": -1},
        {"day_count": True},
        {"open_start_hour": 7.5},
        {"w_under": True},
    ],
)
def test_invalid_generation_configuration_is_rejected_explicitly(overrides) -> None:
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        _run(_state(), _config(**overrides))

    assert failure.value.code == "INVALID_GENERATION_CONFIG"


def test_incomplete_or_malformed_demand_is_rejected_before_search() -> None:
    state = _state(day_count=2)
    state = replace(state, demand=state.demand[:-1])
    SchedulingError = require_symbol("src.model.scheduling", "SchedulingError")

    with pytest.raises(SchedulingError) as failure:
        _run(state, _config(day_count=2))

    assert failure.value.code == "INVALID_DEMAND"


@pytest.mark.parametrize(
    "maximum,durations,max_shifts,expected",
    [
        (20, (8,), 7, 16),
        (12, (8,), 7, 8),
        (7, (8,), 7, 0),
        (60, (8,), 7, 56),
        (20, (8, 4), 7, 20),
        (23, (8, 4), 7, 20),
        (10, (8, 4), 7, 8),
        (2**31 - 1, (8,), 7, 56),
    ],
)
def test_effective_capacity_matches_exact_bounded_duration_result(
    maximum, durations, max_shifts, expected
) -> None:
    effective_capacity = require_symbol("src.domain.generation", "effective_capacity")

    assert effective_capacity(maximum, durations, max_shifts) == expected


@pytest.mark.parametrize(
    "durations,maximum,max_shifts",
    [
        ((2, 3), 9, 4),
        ((3, 5, 8), 18, 3),
        ((1, 4, 6), 13, 6),
        ((4, 7), 21, 5),
    ],
)
def test_effective_capacity_matches_small_reference_recurrence(
    durations, maximum, max_shifts
) -> None:
    effective_capacity = require_symbol("src.domain.generation", "effective_capacity")
    reachable = {0}
    for _ in range(max_shifts):
        reachable |= {
            current + duration
            for current in tuple(reachable)
            for duration in durations
            if current + duration <= maximum
        }

    assert effective_capacity(maximum, durations, max_shifts) == max(reachable)


def test_default_marginals_stop_at_zero_delta_but_custom_policy_can_add() -> None:
    requirements = (1, 2, 2, 3, 4, 4, 3, 2)
    state = _state(
        start_hour=7,
        end_hour=15,
        employees=(8, 8, 8, 8),
        shifts=((7, 15),),
        required={(0, hour): count for hour, count in zip(range(7, 15), requirements, strict=True)},
    )

    default = _run(state)
    custom = _run(state, _config(w_under=4, w_empty=8))

    assert len(default.draft.assignments) == 3
    assert [step.delta_cost for step in default.diagnostics.trace] == [-48, -20, -8]
    assert default.diagnostics.primary_cost == 11
    assert len(custom.draft.assignments) == 4
    assert [step.delta_cost for step in custom.diagnostics.trace] == [-64, -27, -12, -2]


def test_empty_hour_is_preferred_over_a_second_person_on_a_busy_day() -> None:
    state = _state(
        day_count=2,
        start_hour=7,
        end_hour=15,
        employees=(8, 8),
        shifts=((7, 15),),
        daily_shift_limit=1,
        required={
            (day, hour): (2 if day == 0 else 1) for day, hour in product(range(2), range(7, 15))
        },
    )
    outcome = _run(state, _config(day_count=2))

    assert [(item.day, item.shift_id) for item in outcome.draft.assignments] == [(0, 1), (1, 1)]
    assert len({item.day for item in outcome.draft.assignments}) == 2


def test_cost_density_ranks_four_hour_peak_before_eight_hour_shift() -> None:
    rank_add_candidates = require_symbol("src.domain.generation", "rank_add_candidates")
    state = _state(
        day_count=2,
        start_hour=7,
        end_hour=15,
        employees=(16, 16, 8),
        shifts=((7, 15), (10, 14)),
        required={
            (day, hour): (2 if hour < 9 else 3) for day, hour in product(range(2), range(7, 15))
        },
        assignments=(
            Assignment(1, 1, 0, 1),
            Assignment(2, 2, 0, 1),
            Assignment(3, 1, 1, 1),
            Assignment(4, 2, 1, 1),
        ),
    )
    config = _config(day_count=2)

    first = rank_add_candidates(state, config=config)[0]
    after_first = replace(
        state,
        assignments=state.assignments + (Assignment(5, 3, 0, 2),),
    )
    second = rank_add_candidates(after_first, config=config)[0]

    assert (first.employee_id, first.day, first.shift_id, first.delta_cost) == (3, 0, 2, -12)
    assert (second.employee_id, second.day, second.shift_id, second.delta_cost) == (3, 1, 2, -12)


def test_canonical_input_order_produces_identical_assignments_metrics_and_trace() -> None:
    state = _state(
        day_count=2,
        employees=(8, 8, 8),
        shifts=((7, 8), (8, 9)),
        start_hour=7,
        end_hour=9,
        required={(day, hour): 2 for day, hour in product(range(2), range(7, 9))},
        daily_shift_limit=2,
    )
    permuted = replace(
        state, employees=tuple(reversed(state.employees)), shifts=tuple(reversed(state.shifts))
    )
    config = _config(day_count=2, open_end_hour=9)

    first = _run(state, config)
    second = _run(permuted, config)

    assert first.draft.assignments == second.draft.assignments
    assert first.diagnostics == second.diagnostics


def test_generation_starts_empty_and_every_trace_step_preserves_hard_rules() -> None:
    state = _state(
        day_count=2,
        start_hour=7,
        end_hour=9,
        employees=(8, 8),
        shifts=((7, 8), (8, 9)),
        daily_shift_limit=2,
        required={(day, hour): 2 for day in range(2) for hour in range(7, 9)},
        assignments=(Assignment(99, 1, 1, 1),),
    )
    before = state
    outcome = _run(state, _config(day_count=2, open_end_hour=9))
    employees = {item.id: item for item in outcome.draft.employees}
    shifts = {item.id: item for item in outcome.draft.shifts}

    assert state == before
    assert 99 not in {item.id for item in outcome.draft.assignments}
    replayed = set()
    for step in outcome.diagnostics.trace:
        destination = (step.employee_id, step.day, step.shift_id)
        if step.action == "ADD":
            assert destination not in replayed
            replayed.add(destination)
        elif step.action == "DROP":
            assert destination in replayed
            replayed.remove(destination)
        elif step.action == "MOVE":
            source = (step.employee_id, step.source_day, step.source_shift_id)
            assert source in replayed
            replayed.remove(source)
            assert destination not in replayed
            replayed.add(destination)
        elif step.action == "REPLACE":
            source = (step.source_employee_id, step.day, step.shift_id)
            assert source in replayed
            replayed.remove(source)
            assert destination not in replayed
            replayed.add(destination)
        else:
            pytest.fail(f"unexpected accepted action {step.action}")

        hours_by_employee = {employee_id: 0 for employee_id in employees}
        by_employee_day = {employee_id: {} for employee_id in employees}
        for employee_id, day, shift_id in replayed:
            assert employee_id in employees
            assert shift_id in shifts
            assert 0 <= day < 2
            shift = shifts[shift_id]
            day_assignments = by_employee_day[employee_id].setdefault(day, [])
            day_assignments.append(shift)
            hours_by_employee[employee_id] += shift.end_hour - shift.start_hour
        for assignments_by_day in by_employee_day.values():
            for day_assignments in assignments_by_day.values():
                assert len(day_assignments) <= outcome.draft.daily_shift_limit
                for index, shift in enumerate(day_assignments):
                    assert all(
                        shift.end_hour <= other.start_hour or other.end_hour <= shift.start_hour
                        for other in day_assignments[index + 1 :]
                    )
        assert all(
            hours_by_employee[employee_id] <= employees[employee_id].weekly_max_hours
            for employee_id in employees
        )
    assert replayed == {
        (item.employee_id, item.day, item.shift_id) for item in outcome.draft.assignments
    }
    assert all(
        left.delta_cost < 0 or (left.delta_cost == 0 and left.delta_fairness < 0)
        for left in outcome.diagnostics.trace
    )


def test_can_auto_assign_uses_weekly_daily_overlap_and_reference_constraints() -> None:
    can_auto_assign = require_symbol("src.domain.generation", "can_auto_assign")
    state = _state(
        day_count=2,
        start_hour=7,
        end_hour=18,
        employees=(8,),
        shifts=((7, 15), (10, 18), (15, 18)),
        daily_shift_limit=2,
        assignments=(Assignment(1, 1, 0, 1),),
    )

    assert not can_auto_assign(state, 1, 1, 1)
    assert not can_auto_assign(state, 1, 0, 2)
    assert not can_auto_assign(state, 1, 0, 1)
    assert not can_auto_assign(state, 999, 0, 1)
    assert not can_auto_assign(state, 1, 0, 999)
    assert not can_auto_assign(state, 1, 9, 1)
    adjacent_state = replace(
        state,
        employees=(Employee(1, "Employee 1", 16),),
    )
    assert not can_auto_assign(adjacent_state, 1, 0, 3)
    assert can_auto_assign(replace(adjacent_state, daily_shift_limit=2), 1, 0, 3)


def test_refinement_replaces_overallocated_staff_without_changing_coverage() -> None:
    refine_roster = require_symbol("src.domain.generation", "refine_roster")
    shifts = ((7, 15),)
    initial = tuple(Assignment(day + 1, 1, day, 1) for day in range(5)) + (Assignment(6, 2, 5, 1),)
    state = _state(
        day_count=6,
        start_hour=7,
        end_hour=15,
        employees=(40, 32, 16),
        shifts=shifts,
        required={(day, hour): 0 for day, hour in product(range(6), range(7, 15))},
        assignments=initial,
    )

    outcome = refine_roster(state, config=_config(day_count=6))

    assert outcome.diagnostics.primary_cost == 0
    assert outcome.diagnostics.fairness_cost == 1792
    assert outcome.diagnostics.trace[0].action == "REPLACE"
    assert outcome.diagnostics.trace[0].source_employee_id == 1
    assert outcome.diagnostics.trace[0].employee_id == 3
    assert outcome.diagnostics.trace[0].delta_cost == 0
    assert outcome.diagnostics.trace[0].delta_fairness == -1408


def test_refinement_rejects_fairness_worsening_replacement_and_reports_caps() -> None:
    refine_roster = require_symbol("src.domain.generation", "refine_roster")
    initial = tuple(
        [Assignment(day + 1, 1, day, 1) for day in range(3)]
        + [Assignment(day + 4, 2, day, 1) for day in range(3, 5)]
        + [Assignment(6, 3, 5, 1)]
    )
    state = _state(
        day_count=6,
        start_hour=7,
        end_hour=15,
        employees=(40, 32, 16),
        shifts=((7, 15),),
        required={(day, hour): 0 for day, hour in product(range(6), range(7, 15))},
        assignments=initial,
    )

    outcome = refine_roster(state, config=_config(day_count=6))

    assert all(
        step.delta_cost < 0 or (step.delta_cost == 0 and step.delta_fairness < 0)
        for step in outcome.diagnostics.trace
    )
    assert outcome.diagnostics.fairness_cost <= 384
    capped = _run(
        _state(day_count=2, employees=(8, 8)),
        _config(day_count=2, max_moves=1),
    )
    assert capped.diagnostics.refinement_capped is True
    assert "REFINEMENT_CAPPED" in capped.diagnostics.flags


@pytest.mark.parametrize(
    "state,config_overrides,expected_reason",
    [
        (
            _state(
                start_hour=7,
                end_hour=11,
                employees=(4, 4, 4, 4),
                shifts=((7, 11),),
                required={(0, 7): 4, (0, 8): 1, (0, 9): 1, (0, 10): 1},
            ),
            {"day_count": 1, "open_end_hour": 11},
            "STOP_RULE",
        ),
        (
            _state(
                day_count=2,
                start_hour=7,
                end_hour=11,
                employees=(4,),
                shifts=((7, 11),),
            ),
            {"day_count": 2, "open_end_hour": 11},
            "CAPACITY",
        ),
        (
            _state(
                start_hour=7,
                end_hour=15,
                employees=(8,),
                shifts=((7, 11), (11, 15)),
                daily_shift_limit=1,
            ),
            {"day_count": 1, "open_end_hour": 15},
            "DAY_CONSTRAINTS",
        ),
    ],
)
def test_slot_shortfall_reasons_are_specific_and_lower_bound_is_conservative(
    state, config_overrides, expected_reason
) -> None:
    outcome = _run(state, _config(**config_overrides))
    diagnostics = _diagnostics(outcome)

    matching = [item for item in diagnostics.shortfalls if item.reason == expected_reason]

    assert matching
    assert all(item.kind == "slot" and item.unmet_staff_hours > 0 for item in matching)
    assert diagnostics.unavoidable_unmet <= calculate_result(outcome.draft).weekly.unmet_staff_hours
    assert diagnostics.lower_bound_message


def test_uncovered_operating_hour_has_its_own_hour_level_shortfall() -> None:
    state = _state(
        start_hour=7,
        end_hour=16,
        employees=(8,),
        shifts=((7, 15),),
    )
    outcome = _run(state, _config(open_end_hour=16))
    records = [
        item
        for item in outcome.diagnostics.shortfalls
        if item.kind == "hour" and item.reason == "NO_SHIFT_COVERAGE"
    ]

    assert [(item.day, item.hour) for item in records] == [(0, 15)]
    assert len(records) == 1


def test_employee_diagnostics_and_flags_handle_zero_denominators() -> None:
    state = _state(
        day_count=2,
        employees=(8, 8, 0),
        shifts=((7, 15),),
        start_hour=7,
        end_hour=15,
    )
    outcome = _run(state, _config(day_count=2))
    employee_reports = {item.employee_id: item for item in outcome.diagnostics.employees}

    assert employee_reports[3].effective_capacity == 0
    assert employee_reports[3].effective_utilization == "N/A"
    assert outcome.diagnostics.rest_violations == 0
    assert outcome.diagnostics.primary_cost >= 0
    assert outcome.diagnostics.fairness_cost >= 0


def test_utilization_flags_identify_low_and_near_zero_positive_capacity_staff() -> None:
    state = _state(
        employees=(8, 8, 8),
        shifts=((7, 15),),
        start_hour=7,
        end_hour=15,
    )
    outcome = _run(state)

    assert "LOW_UTILIZATION" in outcome.diagnostics.flags
    assert "NEAR_ZERO_WHILE_OTHERS_FULL" in outcome.diagnostics.flags


def test_shortage_free_result_has_empty_shortfall_report_and_zero_bound() -> None:
    state = _state(
        day_count=1,
        employees=(1,),
        shifts=((7, 8),),
        start_hour=7,
        end_hour=8,
    )
    outcome = _run(state)

    assert outcome.diagnostics.shortfalls == ()
    assert outcome.diagnostics.unavoidable_unmet == 0
    assert outcome.draft_result.weekly.unmet_staff_hours == 0
