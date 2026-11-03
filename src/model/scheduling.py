"""Value records shared by scheduling layers."""

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


@dataclass(frozen=True)
class Preview:
    """Read-only replacement draft bound to a state version."""

    token: str
    baseline_version: int
    draft: ScheduleResult
    removed_assignments: int
    added_assignments: int


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
