# Core Scheduling Logic — Stage 6 Summary

## 1. Outcome and changes made

The approved scheduling engine is present in the repository and matches the implemented scope defined by the accepted specification and design. The implementation is organized around the scheduled-state model, pure domain logic, SQLite persistence, and service-level confirmation flows. No source or test files were changed during this review stage; this summary is a documentation-only trace and review artifact.

The implemented scope covers:

- schedule creation, naming, isolation, and stable ID usage;
- staff lifecycle and weekly maximum validation;
- shift definition validation, overlap checks, and daily-limit policy
- CSV import validation, normalized weekday/hour parsing, and import warnings;
- required-staff estimation using integer arithmetic;
- deterministic draft generation with feasibility checks;
- reconciliation and reporting of coverage, excess, unmet demand, and utilization;
- preview/confirmation safety for refresh operations and stale-version rejection;
- immutable history snapshots for confirmed refresh operations;
- compatibility and migration behavior for existing named schedules.

This was verified by the project’s operative checks rather than by code edits: the suite passes under the project venv and the lint/syntax checks pass without issue.

## 2. Spec traceability

| Spec item | Implementation | Verification | Status |
|---|---|---|---|
| FR-1 — Schedule lifecycle and isolation | `src/services/schedules.py` creates independent schedules with default shifts and settings; `src/db/schedules.py` and `src/db/scheduling.py` keep schedule-scoped state isolated; names continue through `normalize_schedule_name` and `Schedule` records. | Covered by `tests/test_schedule_service.py` and `tests/test_scheduling_service.py`; suite passed. | Pass |
| FR-2 — Staff and weekly capacity | `src/model/scheduling.py` defines `Employee`; `src/domain/limits.py` enforces bounded integer validation; `src/services/schedules.py` adds/edits/removes staff and persists rewrites. | Covered by `tests/test_limits.py`, `tests/test_schedule_service.py`, `tests/test_scheduling_service.py`; all passed. | Pass |
| FR-3 — Shift definitions and daily limit | `src/domain/shifts.py` validates shift ranges; overlap and duplicate checks are enforced by service-level validation and `checked_proposal`; `src/db/scheduling.py` stores shift definitions. | Covered by `tests/test_validation.py`, `tests/test_schedule_service.py`; all passed. | Pass |
| FR-4 — Transaction CSV validation and import | `src/domain/csv_import.py` normalizes CSV headers and cell values, rejects invalid content, and returns structured findings; `src/services/schedules.py` validates imports before writing. | Covered by `tests/test_csv_import.py`; all passed. | Pass |
| FR-5 — Required-staff estimate and settings | `src/domain/demand.py` computes integer-safe required staff; threshold validation and refresh behavior live in the schedule service and preview/confirm flow. | Covered by `tests/test_limits.py`, `tests/test_csv_import.py`, `tests/test_schedule_service.py`; all passed. | Pass |
| FR-6 — Unified validation and manual assignment edits | `src/services/schedules.py` and `src/services/scheduling.py` apply result-state validation for add/remove/reassign operations; `SchedulingError` exposes structured violations and details. | Covered by `tests/test_validation.py`, `tests/test_scheduling_service.py`; all passed. | Pass |
| FR-7 — Deterministic best-effort draft generation | `src/domain/generation.py` implements the greedy score-based assignment algorithm with fixed tie-break ordering and hard validity checks. | Covered by `tests/test_generation.py`, `tests/test_scheduling_service.py`; all passed. | Pass |
| FR-8 — Regeneration safety and refresh semantics | `src/services/previews.py` and `src/services/schedules.py` implement preview/confirm flows and version-bound validation; `src/db/history.py` stores snapshots. | Covered by `tests/test_refresh.py`, `tests/test_scheduling_service.py`; all passed. | Pass |
| FR-9 — Coverage and transaction metrics | `src/domain/metrics.py` calculates hourly, weekly, and per-employee metrics; `src/model/scheduling.py` defines the output types. | Covered by `tests/test_metrics.py`, `tests/test_generation.py`, `tests/test_scheduling_service.py`; all passed. | Pass |
| FR-10 — Compatibility and migration | Existing schedule and `shift_hours` compatibility is maintained in `src/domain/periods.py`, `src/model/schedule.py`, and migration/compatibility checks in the service and DB layers. | Covered by `tests/test_periods.py`, `tests/test_schedule_service.py`; all passed. | Pass |
| NFR — Performance | Pure calculation and import logic is bounded and intended to be effectively immediate; `tests/test_performance.py` is benchmark-only and intentionally skipped in CI. | `pytest` reported 3 skipped benchmark tests; no performance assertions failed. | Pass (benchmark-only, not CI-enforced) |
| NFR — Security and input limits | Inputs are limited and validated at boundaries; integer ranges are bounded and CSV limits are enforced in the domain importer. | Covered by `tests/test_limits.py`, `tests/test_csv_import.py`, `tests/test_scheduling_service.py`; all passed. | Pass |
| NFR — Reliability and atomic writes | Database transaction helpers and preview/confirm flows keep writes atomic; refresh snapshot writes happen in a single transaction. | Covered by `tests/test_refresh.py`, `tests/test_scheduling_service.py`; all passed. | Pass |
| NFR — Determinism | Tie ordering and stable IDs are encoded in `generate_draft`; repeated runs produce the same order and metrics. | Covered by `tests/test_generation.py` and deterministic property-style scheduling tests; all passed. | Pass |
| NFR — Compatibility | Existing named-schedule behavior, generic `shift_hours`, and migration expectations remain intact. | Covered by `tests/test_periods.py` and `tests/test_schedule_service.py`; all passed. | Pass |
| NFR — Error contracts | `SchedulingError` and `Violation` provide structured codes, details, and findings; invalid operations fail cleanly without partial writes. | Covered by validation and import tests; all passed. | Pass |
| Acceptance criteria and invariants | The suite exercises the P0 paths, validation invariants, refresh safety, and deterministic generation patterns described in the specification. | `pytest -q` reported 81 passed, 3 skipped. | Pass |

## 3. Full-suite commands and results

Commands executed in the project venv:

1. `python -m pytest -q`
   - Result: `81 passed, 3 skipped in 5.13s`
   - Notes: the skipped tests are the local benchmark-only checks in `tests/test_performance.py`.

2. `python -m ruff check .`
   - Result: `All checks passed!`

3. `python -m ruff format --check .`
   - Result: `67 files already formatted`

4. `python -m compileall -q src ui tests main.py`
   - Result: exit code 0 (no syntax errors)

Additional setup step performed to satisfy the project dependency baseline:

- `python -m venv .venv` and `.venv\Scripts\python -m pip install -r requirements.txt`
  - Result: dependencies installed successfully; this was required because the base interpreter lacked `nicegui`.

Not run / not applicable:

- A separate application build step: not applicable because this is a Python-interpreted app, not a compiled package.
- A full benchmark run beyond the repository’s local-only performance tests: not run because `tests/test_performance.py` is explicitly marked as local benchmark only and was intentionally skipped in the project CI path.

## 4. Known limitations, risks, and follow-ups

- The project remains a local, self-contained scheduling engine with no production deployment, authentication, or browser UI integration beyond the scaffold.
- The performance target is “effective immediate” and benchmark-local rather than hard CI-enforced; it is documented but not a blocking runtime assertion.
- Refresh and preview logic are implemented and tested, but the actual UI confirmation flow still sits outside the core engine and must be wired carefully to avoid stale preview misuse.
- The specification explicitly excludes forecasting, payroll, availability, skills, breaks, and overnight shifts; those remain out of scope for this stage.
- The repo’s tests cover the required deterministic and safety cases; broader fuzzing or adversarial malformed-input campaigns would be a useful next step before broader rollout.

## 5. Lessons learned and proposed AGENTS.md Known pitfalls lines

Lessons learned:

- Boundary validation must happen before any persisted write; the import path and threshold-change path both defend against partial mutation.
- Determinism matters: stable IDs and ordered tie-breaks are essential for confirmable assignment generation and reproducible outputs.
- “Zero demand” is valid demand, not “missing demand”; the system must distinguish absent data from a real zero-transaction bucket.
- Refresh actions are safer when previewed with version checks and immutable state snapshots; stale confirmations are a common operational failure mode.
- Integer-bound checks should be centralized and enforced consistently to protect the service from overflow and malformed external values.

Proposed AGENTS.md lines for review (not applied):

- Known pitfalls: Treat CSV and integer inputs as untrusted; validate range, type, and structure before every write.
- Known pitfalls: Zero transactions are valid demand; missing demand is not zero, and the system must keep those cases distinct.
- Known pitfalls: Refresh previews must be version-bound and stale confirmations must be rejected; never mutate active state during a preview.
- Known pitfalls: Generator tie-breaks are deterministic and rely on stable IDs; do not add randomness or database-order-dependent logic.
- Known pitfalls: Keep state changes atomic across history snapshots, demand updates, and roster replacement; partial writes are rejected.

No AGENTS.md changes were made as requested.
