"""Public facade for weekly schedule actions."""

from dataclasses import replace
from pathlib import Path

from src.db.database import DEFAULT_DATABASE_PATH
from src.db.history import append_snapshot, get_snapshot, list_snapshots
from src.db.schedules import (
    increment_version,
    insert_schedule,
    select_schedules,
    update_name,
    update_setting,
)
from src.db.scheduling import (
    delete_assignment,
    delete_employee,
    delete_shift,
    insert_assignment,
    insert_employee,
    insert_shift,
    load_state,
    mark_defaults_initialized,
    replace_assignments,
    replace_demand,
    update_assignment,
    update_employee,
    update_shift,
)
from src.domain.csv_import import parse_transactions_csv
from src.domain.demand import validate_demand
from src.domain.generation import generate_draft
from src.domain.limits import bounded_int, bounded_name, checked_total
from src.domain.metrics import calculate_result
from src.domain.schedules import normalize_schedule_name
from src.domain.shifts import validate_shift_range
from src.domain.validation import validate_state
from src.model.schedule import Schedule
from src.model.scheduling import (
    Assignment,
    AssignmentOptionPreview,
    AssignmentOptionsPreview,
    Preview,
    ScheduleResult,
    SchedulingError,
    ShiftEditPreview,
)
from src.services.previews import issue_token, proposal_digest, verify_token
from src.services.scheduling import checked_proposal, schedule_connection, valid_id


def _member(items: tuple, member_id: int, field: str):
    item = next((item for item in items if item.id == member_id), None)
    if item is None:
        raise SchedulingError("UNKNOWN_REFERENCE", f"unknown {field}", {field: member_id})
    return item


def _bump(connection, schedule_id: int) -> None:
    if not increment_version(connection, schedule_id):
        raise SchedulingError("INTEGER_OVERFLOW", "schedule version exceeds limit")


def _check_version(state, expected_version: int | None) -> None:
    if expected_version is None:
        return
    version = bounded_int(expected_version, field="expected_version")
    if state.version != version:
        raise SchedulingError(
            "STALE_PREVIEW",
            "schedule changed; review the action again",
            {"expected_version": version, "current_version": state.version},
        )


class ScheduleService:
    """Coordinate validation, storage, and confirmation for one schedule."""

    def __init__(self, database_path: Path = DEFAULT_DATABASE_PATH) -> None:
        self.database_path = database_path

    def create_schedule(self, name: str) -> Schedule:
        """Create an independent named week with two default shifts."""
        try:
            name = normalize_schedule_name(name)
        except ValueError as error:
            raise SchedulingError("INVALID_NAME", str(error), {"field": "schedule_name"}) from error
        with schedule_connection(self.database_path, write=True) as db:
            record = insert_schedule(db, name)
            checked_total(record.id, field="schedule_id")
            checked_total(insert_shift(db, record.id, 7, 15), field="shift_id")
            checked_total(insert_shift(db, record.id, 15, 23), field="shift_id")
            mark_defaults_initialized(db, record.id)
            return record

    def list_schedules(self) -> list[Schedule]:
        """List persisted schedule names and stable IDs."""
        with schedule_connection(self.database_path) as db:
            return select_schedules(db)

    def get_schedule(self, schedule_id: int) -> ScheduleResult:
        """Read a consistent state and calculate its metrics."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        with schedule_connection(self.database_path) as db:
            return calculate_result(load_state(db, schedule_id))

    def rename_schedule(self, schedule_id: int, name: str) -> ScheduleResult:
        """Rename a schedule without changing its children."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        try:
            name = normalize_schedule_name(name)
        except ValueError as error:
            raise SchedulingError("INVALID_NAME", str(error), {"field": "schedule_name"}) from error
        with schedule_connection(self.database_path, write=True) as db:
            load_state(db, schedule_id)
            update_name(db, schedule_id, name)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def add_employee(self, schedule_id: int, name: str, weekly_max_hours: int) -> ScheduleResult:
        """Add a schedule-owned worker and weekly limit."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        name = bounded_name(name, field="employee_name")
        maximum = bounded_int(weekly_max_hours, field="weekly_max_hours")
        with schedule_connection(self.database_path, write=True) as db:
            load_state(db, schedule_id)
            checked_total(insert_employee(db, schedule_id, name, maximum), field="employee_id")
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def edit_employee(
        self, schedule_id: int, employee_id: int, name: str, weekly_max_hours: int
    ) -> ScheduleResult:
        """Change worker name or capacity while retaining assignments."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        employee_id = valid_id(employee_id, "employee_id")
        name = bounded_name(name, field="employee_name")
        maximum = bounded_int(weekly_max_hours, field="weekly_max_hours")
        with schedule_connection(self.database_path, write=True) as db:
            _member(load_state(db, schedule_id).employees, employee_id, "employee_id")
            update_employee(db, schedule_id, employee_id, name, maximum)
            checked_proposal(load_state(db, schedule_id))
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def remove_employee(
        self,
        schedule_id: int,
        employee_id: int,
        *,
        confirmed: bool = False,
        expected_version: int | None = None,
    ) -> ScheduleResult | None:
        """Remove a worker and assignments after confirmation."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        employee_id = valid_id(employee_id, "employee_id")
        if not confirmed:
            return None
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            _check_version(state, expected_version)
            _member(state.employees, employee_id, "employee_id")
            delete_employee(db, schedule_id, employee_id)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def add_shift(self, schedule_id: int, start_hour: int, end_hour: int) -> ScheduleResult:
        """Add a distinct operating-hours shift."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        start_hour, end_hour = validate_shift_range(start_hour, end_hour)
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            if any(
                (item.start_hour, item.end_hour) == (start_hour, end_hour) for item in state.shifts
            ):
                raise SchedulingError("DUPLICATE_SHIFT_DEFINITION", "shift times already exist")
            checked_total(insert_shift(db, schedule_id, start_hour, end_hour), field="shift_id")
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def edit_shift(
        self,
        schedule_id: int,
        shift_id: int,
        start_hour: int,
        end_hour: int,
        *,
        expected_version: int | None = None,
    ) -> ScheduleResult:
        """Check all affected assignments before editing shift times."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        shift_id = valid_id(shift_id, "shift_id")
        start_hour, end_hour = validate_shift_range(start_hour, end_hour)
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            _check_version(state, expected_version)
            _member(state.shifts, shift_id, "shift_id")
            if any(
                item.id != shift_id and (item.start_hour, item.end_hour) == (start_hour, end_hour)
                for item in state.shifts
            ):
                raise SchedulingError("DUPLICATE_SHIFT_DEFINITION", "shift times already exist")
            update_shift(db, schedule_id, shift_id, start_hour, end_hour)
            checked_proposal(load_state(db, schedule_id))
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def remove_shift(
        self,
        schedule_id: int,
        shift_id: int,
        *,
        confirmed: bool = False,
        expected_version: int | None = None,
    ) -> ScheduleResult | None:
        """Remove a shift and assignments after confirmation."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        shift_id = valid_id(shift_id, "shift_id")
        if not confirmed:
            return None
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            _check_version(state, expected_version)
            _member(state.shifts, shift_id, "shift_id")
            delete_shift(db, schedule_id, shift_id)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def set_daily_shift_limit(self, schedule_id: int, limit: int) -> ScheduleResult:
        """Change daily policy without removing assignments."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        limit = bounded_int(limit, field="daily_shift_limit", minimum=1)
        with schedule_connection(self.database_path, write=True) as db:
            load_state(db, schedule_id)
            update_setting(db, schedule_id, "daily_shift_limit", limit)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def set_threshold(self, schedule_id: int, threshold: int) -> ScheduleResult:
        """Change threshold directly before first demand import."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        threshold = bounded_int(threshold, field="threshold", minimum=1)
        with schedule_connection(self.database_path, write=True) as db:
            if load_state(db, schedule_id).demand is not None:
                raise SchedulingError("CONFIRMATION_REQUIRED", "preview a threshold refresh")
            update_setting(db, schedule_id, "threshold", threshold)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def validate_import(self, csv_bytes: bytes):
        """Validate a CSV proposal without writing."""
        return parse_transactions_csv(csv_bytes)

    def import_initial(self, schedule_id: int, csv_bytes: bytes) -> ScheduleResult:
        """Store the first validated report without generation."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        parsed = parse_transactions_csv(csv_bytes)
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            if state.demand is not None:
                raise SchedulingError("CONFIRMATION_REQUIRED", "preview demand replacement")
            validate_demand(parsed.cells, state.threshold)
            replace_demand(db, schedule_id, parsed.cells, parsed.findings)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def add_assignment(
        self,
        schedule_id: int,
        employee_id: int,
        day: int,
        shift_id: int,
        *,
        expected_version: int | None = None,
    ) -> ScheduleResult:
        """Add an assignment after checking the complete proposed state."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        employee_id = valid_id(employee_id, "employee_id")
        shift_id = valid_id(shift_id, "shift_id")
        day = bounded_int(day, field="day")
        if day > 6:
            raise SchedulingError("UNKNOWN_REFERENCE", "invalid weekday")
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            _check_version(state, expected_version)
            _member(state.employees, employee_id, "employee_id")
            shift = _member(state.shifts, shift_id, "shift_id")
            by_id = {item.id: item for item in state.shifts}
            before = sum(
                by_id[item.shift_id].end_hour - by_id[item.shift_id].start_hour
                for item in state.assignments
                if item.employee_id == employee_id
            )
            checked_proposal(
                replace(
                    state,
                    assignments=state.assignments + (Assignment(-1, employee_id, day, shift_id),),
                )
            )
            checked_total(
                insert_assignment(db, schedule_id, employee_id, day, shift_id),
                field="assignment_id",
            )
            _bump(db, schedule_id)
            result = calculate_result(load_state(db, schedule_id))
            warnings = tuple(
                replace(
                    item,
                    details={
                        **item.details,
                        "before_hours": before,
                        "added_hours": shift.end_hour - shift.start_hour,
                    },
                )
                if item.code == "OVER_WEEKLY_MAX" and item.details["employee_id"] == employee_id
                else item
                for item in result.warnings
            )
            return replace(result, warnings=warnings)

    def remove_assignment(self, schedule_id: int, assignment_id: int) -> ScheduleResult:
        """Remove one owned assignment and recalculate metrics."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        assignment_id = valid_id(assignment_id, "assignment_id")
        with schedule_connection(self.database_path, write=True) as db:
            _member(load_state(db, schedule_id).assignments, assignment_id, "assignment_id")
            delete_assignment(db, schedule_id, assignment_id)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def reassign_assignment(
        self,
        schedule_id: int,
        assignment_id: int,
        employee_id: int,
        day: int,
        shift_id: int,
        *,
        expected_version: int | None = None,
    ) -> ScheduleResult:
        """Validate removal and addition as one proposed state."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        assignment_id = valid_id(assignment_id, "assignment_id")
        employee_id = valid_id(employee_id, "employee_id")
        shift_id = valid_id(shift_id, "shift_id")
        day = bounded_int(day, field="day")
        if day > 6:
            raise SchedulingError("UNKNOWN_REFERENCE", "invalid weekday")
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            _check_version(state, expected_version)
            _member(state.assignments, assignment_id, "assignment_id")
            _member(state.employees, employee_id, "employee_id")
            _member(state.shifts, shift_id, "shift_id")
            proposed = tuple(
                Assignment(item.id, employee_id, day, shift_id)
                if item.id == assignment_id
                else item
                for item in state.assignments
            )
            checked_proposal(replace(state, assignments=proposed))
            update_assignment(db, schedule_id, assignment_id, employee_id, day, shift_id)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def preview_assignment_options(
        self,
        schedule_id: int,
        day: int,
        shift_id: int,
        *,
        replacing_assignment_id: int | None = None,
    ) -> AssignmentOptionsPreview:
        """Evaluate all employee choices from one consistent read without writing."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        shift_id = valid_id(shift_id, "shift_id")
        day = bounded_int(day, field="day")
        if day > 6:
            raise SchedulingError("UNKNOWN_REFERENCE", "invalid weekday")
        if replacing_assignment_id is not None:
            replacing_assignment_id = valid_id(replacing_assignment_id, "assignment_id")
        with schedule_connection(self.database_path) as db:
            state = load_state(db, schedule_id)
        shift = _member(state.shifts, shift_id, "shift_id")
        affected_keys = {(day, hour) for hour in range(shift.start_hour, shift.end_hour)}
        if replacing_assignment_id is not None:
            replaced = _member(state.assignments, replacing_assignment_id, "assignment_id")
            old_shift = _member(state.shifts, replaced.shift_id, "shift_id")
            affected_keys.update(
                (replaced.day, hour) for hour in range(old_shift.start_hour, old_shift.end_hour)
            )
        before = calculate_result(state)
        current_hours = {item.employee_id: item.assigned_hours for item in before.employees}
        choices = []
        for employee in sorted(state.employees, key=lambda item: item.id):
            assignments = tuple(
                item for item in state.assignments if item.id != replacing_assignment_id
            ) + (Assignment(-1, employee.id, day, shift_id),)
            proposed = replace(state, assignments=assignments)
            findings = validate_state(proposed)
            blocked = any(item.severity == "error" for item in findings)
            projected = None if blocked else calculate_result(proposed)
            current_count = sum(
                item.employee_id == employee.id and item.day == day for item in state.assignments
            )
            projected_count = sum(
                item.employee_id == employee.id and item.day == day for item in assignments
            )
            affected_hours = tuple(
                item for item in before.hourly if (item.day, item.hour) in affected_keys
            )
            after_hours = (
                None
                if projected is None
                else tuple(
                    item for item in projected.hourly if (item.day, item.hour) in affected_keys
                )
            )
            choices.append(
                AssignmentOptionPreview(
                    employee.id,
                    blocked,
                    findings,
                    current_hours[employee.id],
                    None
                    if projected is None
                    else next(
                        item.assigned_hours
                        for item in projected.employees
                        if item.employee_id == employee.id
                    ),
                    employee.weekly_max_hours,
                    current_count,
                    None if blocked else projected_count,
                    state.daily_shift_limit,
                    affected_hours,
                    after_hours,
                    before.weekly,
                    None if projected is None else projected.weekly,
                )
            )
        return AssignmentOptionsPreview(
            schedule_id,
            state.version,
            day,
            shift_id,
            replacing_assignment_id,
            tuple(choices),
        )

    def preview_shift_edit(
        self,
        schedule_id: int,
        shift_id: int,
        start_hour: int,
        end_hour: int,
    ) -> ShiftEditPreview:
        """Evaluate a proposed definition and its affected assignments without writing."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        shift_id = valid_id(shift_id, "shift_id")
        with schedule_connection(self.database_path) as db:
            state = load_state(db, schedule_id)
        old = _member(state.shifts, shift_id, "shift_id")
        start_hour, end_hour = validate_shift_range(start_hour, end_hour)
        proposed = replace(
            state,
            shifts=tuple(
                replace(item, start_hour=start_hour, end_hour=end_hour)
                if item.id == shift_id
                else item
                for item in state.shifts
            ),
        )
        findings = validate_state(proposed)
        blocked = any(item.severity == "error" for item in findings)
        affected = tuple(item for item in state.assignments if item.shift_id == shift_id)
        return ShiftEditPreview(
            schedule_id,
            state.version,
            shift_id,
            old.start_hour,
            old.end_hour,
            start_hour,
            end_hour,
            old.end_hour - old.start_hour,
            end_hour - start_hour,
            tuple(item.id for item in affected),
            tuple((item.employee_id, item.day) for item in affected),
            findings,
            None if blocked else calculate_result(proposed),
        )

    def generate(self, schedule_id: int) -> ScheduleResult:
        """Generate and commit a draft only into an empty roster."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            if state.assignments:
                raise SchedulingError("CONFIRMATION_REQUIRED", "preview roster replacement")
            draft = generate_draft(state)
            replace_assignments(db, schedule_id, draft.assignments)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def preview_generation(self, schedule_id: int) -> Preview:
        """Return read-only generated draft and signed baseline version."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        with schedule_connection(self.database_path) as db:
            state = load_state(db, schedule_id)
            draft = generate_draft(state)
            return Preview(
                issue_token(schedule_id, state.version, "generation", ""),
                state.version,
                calculate_result(draft),
                len(state.assignments),
                len(draft.assignments),
            )

    def confirm_generation(
        self, schedule_id: int, token: str, *, confirmed: bool = False
    ) -> ScheduleResult | None:
        """Replace roster after checking signed preview under a write lock."""
        if not confirmed:
            return None
        schedule_id = valid_id(schedule_id, "schedule_id")
        version = verify_token(token, schedule_id, "generation", "")
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            if state.version != version:
                raise SchedulingError("STALE_PREVIEW", "schedule changed since preview")
            replace_assignments(db, schedule_id, generate_draft(state).assignments)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def _proposal(self, state, csv_bytes, threshold):
        if (csv_bytes is None) == (threshold is None):
            raise SchedulingError("INVALID_PREVIEW", "supply CSV or threshold")
        if state.demand is None:
            raise SchedulingError("MISSING_DEMAND", "import initial demand first")
        if csv_bytes is not None:
            parsed = parse_transactions_csv(csv_bytes)
            validate_demand(parsed.cells, state.threshold)
            return (
                replace(state, demand=parsed.cells, import_warnings=parsed.findings),
                "DEMAND_REIMPORT",
                proposal_digest(csv_bytes),
            )
        threshold = bounded_int(threshold, field="threshold", minimum=1)
        validate_demand(state.demand, threshold)
        return (
            replace(state, threshold=threshold),
            "THRESHOLD_CHANGE",
            proposal_digest(str(threshold).encode()),
        )

    def preview_refresh(
        self, schedule_id: int, *, csv_bytes: bytes | None = None, threshold: int | None = None
    ) -> Preview:
        """Prepare a read-only demand or threshold replacement preview."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        with schedule_connection(self.database_path) as db:
            state = load_state(db, schedule_id)
            proposed, reason, digest = self._proposal(state, csv_bytes, threshold)
            draft = generate_draft(proposed)
            return Preview(
                issue_token(schedule_id, state.version, reason, digest),
                state.version,
                calculate_result(draft),
                len(state.assignments),
                len(draft.assignments),
            )

    def confirm_refresh(
        self,
        schedule_id: int,
        token: str,
        *,
        csv_bytes: bytes | None = None,
        threshold: int | None = None,
        confirmed: bool = False,
    ) -> ScheduleResult | None:
        """Snapshot the prior state and replace inputs and roster atomically."""
        if not confirmed:
            return None
        schedule_id = valid_id(schedule_id, "schedule_id")
        if (csv_bytes is None) == (threshold is None):
            raise SchedulingError("INVALID_PREVIEW", "supply CSV or threshold")
        reason = "DEMAND_REIMPORT" if csv_bytes is not None else "THRESHOLD_CHANGE"
        digest = proposal_digest(csv_bytes if csv_bytes is not None else str(threshold).encode())
        version = verify_token(token, schedule_id, reason, digest)
        with schedule_connection(self.database_path, write=True) as db:
            state = load_state(db, schedule_id)
            if state.version != version:
                raise SchedulingError("STALE_PREVIEW", "schedule changed since preview")
            proposed, _, _ = self._proposal(state, csv_bytes, threshold)
            draft = generate_draft(proposed)
            append_snapshot(db, calculate_result(state), reason)
            if csv_bytes is not None:
                replace_demand(db, schedule_id, proposed.demand, proposed.import_warnings)
            else:
                update_setting(db, schedule_id, "threshold", proposed.threshold)
            replace_assignments(db, schedule_id, draft.assignments)
            _bump(db, schedule_id)
            return calculate_result(load_state(db, schedule_id))

    def list_snapshots(self, schedule_id: int):
        """List saved prior-state summaries for one schedule."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        with schedule_connection(self.database_path) as db:
            load_state(db, schedule_id)
            return list_snapshots(db, schedule_id)

    def get_snapshot(self, schedule_id: int, snapshot_id: int):
        """Read one immutable historical state within its owner schedule."""
        schedule_id = valid_id(schedule_id, "schedule_id")
        snapshot_id = valid_id(snapshot_id, "snapshot_id")
        with schedule_connection(self.database_path) as db:
            load_state(db, schedule_id)
            return get_snapshot(db, schedule_id, snapshot_id)
