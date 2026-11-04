"""Value records shared by scheduling layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Violation:
    """A stable, structured validation finding."""

    code: str
    severity: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    row: int | None = None
    column: int | None = None
    day: int | None = None
    hour: int | None = None


class SchedulingError(ValueError):
    """Reject a scheduling action with structured details."""

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        findings: tuple[Violation, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.severity = "error"
        self.details = details or {}
        self.findings = findings


@dataclass(frozen=True)
class Employee:
    """A schedule-owned worker and weekly capacity."""

    id: int
    name: str
    weekly_max_hours: int


@dataclass(frozen=True)
class ShiftDefinition:
    """A reusable same-day shift."""

    id: int
    start_hour: int
    end_hour: int


@dataclass(frozen=True)
class DemandCell:
    """Transactions in one operating hour."""

    day: int
    hour: int
    transactions: int


@dataclass(frozen=True)
class Assignment:
    """One worker assigned to a shift on a weekday."""

    id: int
    employee_id: int
    day: int
    shift_id: int


@dataclass(frozen=True)
class ScheduleState:
    """Complete current schedule state."""

    id: int
    name: str
    version: int
    threshold: int
    daily_shift_limit: int
    employees: tuple[Employee, ...]
    shifts: tuple[ShiftDefinition, ...]
    demand: tuple[DemandCell, ...] | None
    assignments: tuple[Assignment, ...]
    import_warnings: tuple[Violation, ...] = ()


@dataclass(frozen=True)
class ParsedDemand:
    """Validated normalized CSV report."""

    cells: tuple[DemandCell, ...]
    findings: tuple[Violation, ...]


@dataclass(frozen=True)
class HourlyMetric:
    """Coverage and transaction measures for one hour."""

    day: int
    hour: int
    transactions: int | None
    required: int | None
    scheduled: int
    covered: int | None
    unmet: int | None
    excess: int | None
    transactions_per_staff_hour: float | None


@dataclass(frozen=True)
class WeeklyMetric:
    """Whole-week coverage and transaction measures."""

    total_transactions: int | None
    required_staff_hours: int | None
    scheduled_staff_hours: int
    covered_staff_hours: int | None
    unmet_staff_hours: int | None
    excess_staff_hours: int | None
    coverage_rate: float | None
    transactions_per_staff_hour: float | None
    average_staffed_cell_ratio: float | None


@dataclass(frozen=True)
class EmployeeMetric:
    """Assigned hours and utilization for one employee."""

    employee_id: int
    name: str
    assigned_hours: int
    maximum_hours: int
    utilization: float | None


@dataclass(frozen=True)
class RosterSlot:
    """One configured shift on a weekday with assigned worker allocation."""

    day: int
    shift_id: int
    start_hour: int
    end_hour: int
    employees: tuple[EmployeeMetric, ...]


@dataclass(frozen=True)
class ScheduleResult:
    """State with current diagnostics and analytics."""

    state: ScheduleState
    warnings: tuple[Violation, ...]
    hourly: tuple[HourlyMetric, ...]
    weekly: WeeklyMetric
    employees: tuple[EmployeeMetric, ...]
    roster: tuple[RosterSlot, ...] = ()
    generation_diagnostics: GenerationDiagnostics | None = field(default=None, compare=False)


@dataclass(frozen=True)
class GenerationConfig:
    """Deterministic policy and operating bounds for automatic generation."""

    day_count: int = 7
    open_start_hour: int = 7
    open_end_hour: int = 23
    w_under: int = 3
    w_over: int = 1
    w_empty: int = 6
    max_passes: int = 50
    max_moves: int = 5000
    rest_weight: int = 0


@dataclass(frozen=True)
class GenerationEmployeeDiagnostic:
    """Capacity and proportional workload information for one employee."""

    employee_id: int
    assigned_hours: int
    maximum_hours: int
    effective_capacity: int
    raw_utilization: float | str
    effective_utilization: float | str
    target_hours: float
    deviation_hours: float


@dataclass(frozen=True)
class GenerationShortfall:
    """One configured shift-slot or uncovered-hour shortage explanation."""

    kind: str
    reason: str
    unmet_staff_hours: int
    message: str
    day: int
    hour: int | None = None
    shift_id: int | None = None


@dataclass(frozen=True)
class GenerationTrace:
    """One accepted deterministic roster decision."""

    sequence: int
    phase: str
    action: str
    employee_id: int
    day: int
    shift_id: int
    delta_cost: int
    delta_fairness: int
    explanation: str
    source_employee_id: int | None = None
    source_day: int | None = None
    source_shift_id: int | None = None


@dataclass(frozen=True)
class GenerationDiagnostics:
    """Transient optimizer costs, capacity bounds, and decision explanations."""

    primary_cost: int
    fairness_cost: int
    fairness_deviation_hours: float
    required_hours: int
    capacity_hours: int
    unavoidable_unmet: int
    lower_bound_message: str
    employees: tuple[GenerationEmployeeDiagnostic, ...]
    shortfalls: tuple[GenerationShortfall, ...]
    flags: tuple[str, ...]
    flag_messages: tuple[tuple[str, str], ...]
    trace: tuple[GenerationTrace, ...]
    rest_violations: int
    refinement_capped: bool


@dataclass(frozen=True)
class GenerationOutcome:
    """Pure generation result, or a prerequisite block without partial output."""

    blocked_code: str | None
    message: str
    draft: ScheduleState | None
    diagnostics: GenerationDiagnostics | None
    draft_result: ScheduleResult | None


@dataclass(frozen=True)
class AddCandidate:
    """Feasible negative-cost addition in deterministic rank order."""

    employee_id: int
    day: int
    shift_id: int
    delta_cost: int
    delta_fairness: int
    excess_added: int
    duration: int


@dataclass(frozen=True)
class Preview:
    """Read-only replacement draft bound to a state version."""

    token: str
    baseline_version: int
    draft: ScheduleResult
    removed_assignments: int
    added_assignments: int


@dataclass(frozen=True)
class AssignmentOptionPreview:
    """Projected effect of assigning one stable employee ID to a cell."""

    employee_id: int
    blocked: bool
    findings: tuple[Violation, ...]
    current_hours: int
    projected_hours: int | None
    weekly_max_hours: int
    current_daily_shift_count: int
    projected_daily_shift_count: int | None
    daily_shift_limit: int
    before_hourly: tuple[HourlyMetric, ...]
    after_hourly: tuple[HourlyMetric, ...] | None
    before_weekly: WeeklyMetric
    after_weekly: WeeklyMetric | None


@dataclass(frozen=True)
class AssignmentOptionsPreview:
    """All employee choices evaluated from one schedule version."""

    schedule_id: int
    baseline_version: int
    day: int
    shift_id: int
    replacing_assignment_id: int | None
    options: tuple[AssignmentOptionPreview, ...]


@dataclass(frozen=True)
class ShiftEditPreview:
    """Read-only impact of a proposed shift definition."""

    schedule_id: int
    baseline_version: int
    shift_id: int
    old_start_hour: int
    old_end_hour: int
    new_start_hour: int
    new_end_hour: int
    old_duration: int
    new_duration: int
    affected_assignment_ids: tuple[int, ...]
    affected_employee_days: tuple[tuple[int, int], ...]
    findings: tuple[Violation, ...]
    projected_result: ScheduleResult | None


@dataclass(frozen=True)
class HistoricalSnapshot:
    """Immutable prior state and its captured analytics."""

    id: int
    schedule_id: int
    captured_at_utc: str
    reason: str
    state: ScheduleState
    hourly: tuple[HourlyMetric, ...]
    weekly: WeeklyMetric
    employees: tuple[EmployeeMetric, ...]
    warnings: tuple[Violation, ...]


@dataclass(frozen=True)
class SnapshotSummary:
    """Index entry for a saved historical state."""

    id: int
    schedule_id: int
    captured_at_utc: str
    reason: str
    prior_version: int
