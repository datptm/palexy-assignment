# Core scheduling logic — Stage 3 implementation plan

> **For implementation after manager review:** execute the checked tasks in order, using the approved [specification](01-spec.md) and [design](02-design.md) as the authority. Use a task-by-task implementation workflow and verify each task before proceeding. This document authorizes no source changes by itself.

**Goal:** Add a browser-independent, persistent weekly scheduling engine with validated demand import, editable assignments, deterministic draft generation, truthful metrics, and atomic, historical refreshes.

**Architecture:** Typed records in `src/model/` cross layers; pure functions in `src/domain/` parse, validate, generate, and calculate; parameterized SQLite in `src/db/` stores active and historical state; services own transaction and confirmation boundaries. The NiceGUI scaffold remains outside this stage.

**Tech stack:** Python 3.10+, standard library, SQLite, existing pytest and Ruff. **No new dependency is planned.**

## Global constraints

- Preserve existing `ScheduleService.create_schedule` / `list_schedules`, name validation, stable IDs, and the generic `shift_hours` contract.
- A typical week has Monday–Sunday days, 112 operating buckets at 07:00–23:00, whole-hour same-day shifts, default shifts 07:00–15:00 and 15:00–23:00, threshold `20`, and daily shift limit `1`.
- Cap every accepted, persisted, or returned integer and resulting integer total at `2^31 − 1`; use wider Python intermediates and reject overflow before commit.
- Cap CSV input at 1 MiB, 256 rows, 32 columns, and 4,096 characters per cell; accept only complete, validated 112-cell demand.
- A confirmed re-import or post-import threshold change snapshots the prior state and analytics, then generates and replaces the active roster in one transaction. This manager decision supersedes the BRD retain-roster rule.
- Use one public `ScheduleService` facade. Invalid operations raise a typed exception carrying structured violations/findings; successful operations return typed results. Record performance targets as local benchmarks, without hard timing assertions in CI.
- Use no new dependencies, UI workflow, unsafe deserialization, dynamic SQL from input, or path-based upload handling. Do not change `docs/resources/` or `data/sample_transaction_interview.csv`.
- Every implementation chat that changes code must append or update one entry in `docs/ai/CHANGELOG.md` and pass applicable repository checks.

## Review focus

The step tests below must also cover these easily missed inputs: a complete all-zero report (valid demand, not unavailable); duplicate weekday names after normalization; an edit to a used shift that conflicts with an assignment on a different day; an over-limit manual assignment whose warning persists after reopening; and stale or altered preview proposals that leave both active rows and history unchanged.

## 1. Implementation summary based on the approved design

Build the schema and typed state first, then pure validation, importer, metrics, and generator. Add service mutations only after their domain rules are testable. Finish with read-only preview and signed confirmation paths, immutable snapshots, fault-injection tests, and performance checks. All writes use explicit transactions with version increments; reads calculate warnings and metrics from one consistent state. The generator starts with an empty draft, repeatedly chooses the highest positive whole-shift score (`3 × shortage removed − excess added`), and resolves ties by added excess, exact utilization, day, shift times, shift ID, then employee ID. It may leave unmet demand.

In scope: FR-1–FR-10 and AC-01–AC-19 at domain, model, database, and service layers. Out of scope: NiceGUI controls, authentication, publishing, snapshot restore/deletion, optimization-weight UI, forecasting, and unrelated refactoring. The existing `Schedule` dataclass can remain the small name/ID record; a separate `ScheduleState` carries the complete week so existing equality assertions remain valid.

The single public `ScheduleService` facade exposes `get_schedule`, `rename_schedule`, employee and shift add/edit/remove, `set_daily_shift_limit`, `set_threshold`, `validate_import`, `import_initial`, assignment add/remove/reassign, `generate` for an empty roster, `preview_generation`/`confirm_generation` for replacement, `preview_refresh`/`confirm_refresh` for re-import or post-import threshold change, and `list_snapshots`/`get_snapshot`. Successful operations return typed results; invalid operations raise a typed exception with code, severity, message, details, and an attached `Violation`/finding list. `validate_import` returns all discoverable findings together for a preview. Confirmation methods take an explicit `confirmed` flag. Pin exact parameter and result types in the first task that introduces each operation, before implementing its body.

## 2. Files to create or modify

| Path | Change | Why |
|---|---|---|
| `src/model/schedule.py` | Keep the existing `Schedule` contract; add only compatible fields if required. | Preserve current callers and tests. |
| `src/model/scheduling.py` (new) | Typed state, employee, shift, demand, assignment, finding, preview, metric, result, and snapshot records. | Share precise contracts without database or UI imports. |
| `src/domain/limits.py` (new) | Strict bounded integer and text validation, aggregate range checks. | Apply one ceiling at every boundary. |
| `src/domain/shifts.py` (new) | Scheduling-specific shift validation and overlap helpers. | Keep generic `periods.shift_hours` unchanged. |
| `src/domain/validation.py` (new) | Whole-state assignment and policy validation with stable violation codes. | Make manual and generated validity consistent. |
| `src/domain/demand.py` (new) | Required-staff integer arithmetic and demand completeness checks. | Separate estimation from CSV parsing. |
| `src/domain/csv_import.py` (new) | Bounded CSV decode, normalization, findings, and 112-cell result. | Treat upload bytes as untrusted. |
| `src/domain/metrics.py` (new) | Hourly, weekly, employee, warning, and grouped-roster projections. | Keep active and historical analytics coherent. |
| `src/domain/generation.py` (new) | Deterministic greedy selection and prerequisite checks. | Generate valid, explainable drafts. |
| `src/db/database.py` | Add idempotent, additive schema migration and explicit write transaction helper. | Preserve old named schedules; guarantee atomic actions. |
| `src/db/schedules.py` | Add scoped schedule read/rename/settings/version queries. | Extend existing persistence without breaking create/list. |
| `src/db/scheduling.py` (new) | Parameterized, schedule-scoped staff, shift, demand, warning, and assignment queries. | Keep SQLite access out of domain and services. |
| `src/db/history.py` (new) | Append and read validated, versioned JSON snapshots. | Preserve immutable prior state and analytics. |
| `src/services/schedules.py` | Extend the single public `ScheduleService` facade and keep existing methods compatible. | Give callers one use-case entry point. |
| `src/services/scheduling.py` (new) | Shared state load, edit, validation, transaction, and result helpers. | Avoid a large monolithic facade. |
| `src/services/previews.py` (new) | Process-key signed proposal tokens and read-only preview/confirmation orchestration. | Bind explicit confirmation to schedule, version, operation, and proposal. |
| `tests/test_schedule_service.py` | Extend compatibility, migration, isolation, and lifecycle tests. | Protect the scaffold contracts. |
| `tests/test_limits.py`, `tests/test_validation.py`, `tests/test_csv_import.py` (new) | Boundary and pure-rule tests. | Fail on invalid fields, overlap, and malformed reports. |
| `tests/test_metrics.py`, `tests/test_generation.py` (new) | Exact metrics, invariants, score, and tie tests. | Prove calculation and deterministic draft behavior. |
| `tests/test_scheduling_service.py`, `tests/test_refresh.py` (new) | Temporary-SQLite mutation, preview, rollback, and history tests. | Prove persistence and atomicity on fresh reads. |
| `tests/test_performance.py` (new) | Reproducible local timing scenarios that report results without hard timing assertions. | Record accepted performance targets without machine-dependent CI failures. |
| `README.md` | Replace stale next-step statements with the implemented backend scope when implementation is complete. | Keep documentation truthful; do not imply UI completion. |
| `docs/ai/CHANGELOG.md` | Append one implementation-chat entry, or update that chat's entry. | Satisfy AGENTS.md; no entry is needed for this documentation-only planning chat. |

## 3. Small, ordered implementation steps

Each numbered step is one reviewable deliverable, targeted at **under about 200 changed lines**, including tests. If the real diff grows, split that step at a testable boundary. For each step, write a behavioral test that fails for the missing behavior, implement only enough to pass, and inspect the diff before continuing. The verification column in Section 4 names the focused gate; every step also runs the full required checks after its focused tests pass.

1. **Typed state and strict bounds.** Add frozen or otherwise value-oriented records for `Employee`, `ShiftDefinition`, `DemandCell`, `Assignment`, `Violation`, `ScheduleState`, and a coded boundary error. Define day indices `0..6`, integer ceiling, and strict numeric validators that reject `bool`, floats, strings, negatives where forbidden, and overflow. Test accepted `0`/ceiling and rejected ceiling+1, NaN, infinity, and invalid IDs. Keep `Schedule` compatible.
2a. **Additive schema migration.** Extend `schedules` with threshold, daily limit, and version; create scoped child tables, indexes, checks, and composite ownership FKs. Migrate a legacy `schedules(id,name)` database transactionally and idempotently while preserving IDs/names. Test repeat migration, FK enforcement, and old rows after reopen.
2b. **Default schedule state.** Create default shift rows for each migrated or new schedule exactly once, and initialize threshold `20`, daily limit `1`, and version. Check allocated IDs/version against the ceiling. Test reopen, duplicate names, and two-schedule isolation.
3. **Schedule read, rename, and state loading.** Add parameterized scoped queries and `get_schedule(id)`/`rename_schedule(id,name)` with stable ID, one consistent read, one version increment per committed rename, and missing-ID rejection. Test a reopen reproduces defaults, rename preserves children, and invalid/cross-schedule IDs change nothing.
4. **Scheduling-specific shift and staff rules.** Add strict employee name (trimmed 1–100 characters), maximum-hours, shift range, duplicate-time, and overlap validators. Do not alter `periods.shift_hours`. Test whole-hour 07–23 bounds, adjacent shifts, overlapping distinct definitions, duplicate pairs, duplicate employee names, and zero maximum.
5. **Staff and shift creation/deletion.** Add scoped staff and shift inserts and confirmed deletes. Reject duplicate shift definitions; require `confirmed=True` before deleting a used staff/shift record, explicitly remove dependents in the same transaction, and increment version once. Test cancellation, cross-schedule IDs, dependent-assignment removal, and rollback. Staff/shift edits and daily-limit changes follow in Step 6, when the whole-state validator exists.
6a. **Whole-state validation and policy edits.** Validate referenced IDs/day, duplicates, same-person overlap, weekly hours, and daily shift count over the proposed resulting state. Add staff/shift edits and daily-limit changes, checking every affected assignment. Warnings commit, errors do not. Test used-shift overlap rollback, duration/limit policy warnings, and warnings persisting after reopen.
6b. **Manual assignment edits.** Add/remove/reassign assignments against the resulting state in one transaction, using the Step 6a validator. Return structured before/added/after/limit/excess details on an over-maximum add. Test `32 + 8 = 40`, adjacent shifts at daily limit 1, cross-schedule references, reassignment rollback, and exact changed hours on removal.
7. **Demand estimation and integer totals.** Implement `required=max(1,(count+N-1)//N)` with checked threshold, 112-cell completeness, and checked weekly transaction/required totals. Test `0,20,21,48,64` at `N=20`, all-zero valid demand, missing versus zero demand, and aggregate overflow without mutation.
8. **CSV byte/shape boundary.** Decode bounded UTF-8 (allow BOM), cap file bytes/rows/columns/cell length before expensive work, and return distinct resource-limit versus malformed-content findings. Test each cap at and beyond its boundary, malformed bytes, blank content, and that the parser has no database dependency.
9a. **CSV layout and label normalization.** Normalize full/abbreviated English weekdays in arbitrary order and case, date-labelled headers, whole-hour labels, optional title, recognized totals, and empty rows/columns. Collect positioned findings for ignored material and rejected duplicate/unknown labels. Test the supplied sample header, shuffled columns, repeated weekday/hour labels, and title/total/empty warnings without logging sample values.
9b. **CSV cell validation and complete result.** Validate exactly one nonnegative bounded integer for each of 112 normalized cells, collect all discoverable errors with row/column and day/hour, and exclude total values. Test the supplied sample's full normalized demand, shuffled-column equivalence, blank/negative/fractional/text counts, missing cells, combined findings, and weekly aggregate overflow.
10. **Initial import and pre-import threshold edit.** Persist a complete validated report and accepted warnings atomically without generation; allow direct threshold editing before demand exists. Once demand exists, route changes to the preview path in Step 15. Test zero rows versus 112 zero rows, warning persistence, bad import preserving prior rows, version change, and reopened state.
11. **Pure metrics and roster projection.** Compute hourly scheduled/required/covered/unmet/excess, transaction ratio, weekly totals/coverage, employee hours/utilization, diagnostics, and Monday–Sunday grouping by configured shift. Assert all integer totals before returning. Test `(33,3),(48,3),(33,2)` gives `114/8=14.25` overall and `14.5` unweighted average; test undefined ratios, excess, 0–100% coverage, and hour reconciliation. Make active service reads return this projection.
12. **Generator eligibility and scoring.** Add pure prerequisite errors for missing demand, shifts, and eligible staff; implement whole-shift marginal shortage/excess score with configurable policy weight for tests (default `3:1`). Reject zero or below-shift-length maxima; enforce weekly/daily/overlap hard limits. Test missing prerequisites, valid partial drafts, peak coverage, and default-weight `[1,2,2,3,4,4,3,2]` morning example versus `W_under=4`.
13. **Deterministic selection and generator invariants.** Finish the greedy loop with positive-score stop and exact-fraction utilization comparison; tie by excess, utilization, day, start/end, shift ID, employee ID. Test exact assignment sets on repeats, each tie dimension, and varied small weeks for reference/overlap/capacity/metric invariants. Record a local benchmark for the 100-employee/32-shift pure calculation; investigate a miss against the 10-second target without adding a hard CI timing assertion.
14. **Standalone generation and replacement preview.** Permit direct `generate(id)` only for an empty roster. For a nonempty roster, return read-only draft/impact and a signed token; `confirm_generation` requires explicit confirmation, valid token/proposal binding, and matching version within `BEGIN IMMEDIATE`. Replace all assignments atomically without history or input changes. Test cancel, altered/cross-schedule/stale token, repeat deterministic result, and injected storage failure preserving old assignments.
15. **Read-only refresh preview.** `preview_refresh` validates a re-import or post-import threshold proposal and returns normalized input, draft/metrics, replacement impact, baseline version, and token without writing. Test valid and invalid previews, altered proposal bytes, and ineligible staff without any active-state or history change. Confirmation is introduced with its required snapshot in Step 16.
16a. **Snapshot serialization and read contract.** Add versioned canonical JSON of a validated prior name, staff, shifts, settings, complete demand, import warnings, assignments, and calculated hourly/weekly/employee metrics; include UTC time and reason. Add schedule-scoped append/list/read with structure validation and no update/delete route, but keep append private to the service. Test round-trip, retained analytics, snapshot immutability, malformed stored JSON rejection, and cross-schedule access.
16b. **Atomic refresh confirmation.** `confirm_refresh` revalidates the proposal/token/version under the write lock, inserts exactly one Step 16a prior-state snapshot, applies new demand/threshold, generates, and replaces assignments in that same transaction. Test prior manually edited state, stale/altered/cancelled confirmation, no recursive history, and injected failure rollback of snapshot and active rows.
17. **End-to-end acceptance and performance.** Exercise AC-01–AC-19 through public services and fresh SQLite connections, including all P0 paths; use several small valid weeks for invariants and rejected-state equality. Record local timings for valid import plus metric refresh against the 1-second target, pure generation at 100 employees/32 shifts against the 10-second target, and confirmed refresh including snapshot persistence separately. Document the machine, measured values, and any missed target for review; do not turn timings into hard CI assertions or silently weaken targets.
18. **Documentation and final gate.** Update README backend status without presenting the UI scaffold as a completed workflow; append the required single change-log entry for the implementation chat. Inspect the diff for unrelated files, generated artifacts, and source-document changes. Run the complete repository gate and record its exact results in the change log.

## 4. Verification for each step

Use the Python environment installed from `requirements.txt`. For **every** numbered step after its focused test, run `python -m pytest`, `python -m ruff check .`, `python -m ruff format --check .`, and `python -m compileall -q src ui tests main.py`; a step is not complete while an applicable gate fails. A normal passing command exits `0`, with pytest reporting all tests passed. Local benchmark runs record timings and machine details for review; they have no hard elapsed-time assertion in CI. Tests for rejected writes must compare a fresh database read before and after, including history where applicable. The focused checks are:

| Step | Focused test / check and expected observation |
|---|---|
| 1 | `python -m pytest tests/test_limits.py -q`: strict type/range boundaries pass; existing `tests/test_schedule_service.py` still passes. |
| 2a | `python -m pytest tests/test_schedule_service.py -q`: legacy IDs/names survive repeat migration; foreign keys reject a cross-schedule child. |
| 2b | `python -m pytest tests/test_schedule_service.py -q`: default shifts appear once, including for legacy rows; schedules remain independent. |
| 3 | `python -m pytest tests/test_schedule_service.py -q`: stable-ID read/rename and version changes pass after reopen. |
| 4 | `python -m pytest tests/test_validation.py tests/test_periods.py -q`: scheduling shift rules pass and the generic helper stays compatible. |
| 5 | `python -m pytest tests/test_scheduling_service.py -q`: staff/shift creation and confirmed deletion pass; cancelled and failed deletes preserve state. |
| 6a | `python -m pytest tests/test_validation.py tests/test_scheduling_service.py -q`: whole-state validation and staff/shift policy edits pass. |
| 6b | `python -m pytest tests/test_validation.py tests/test_scheduling_service.py -q`: assignment edits, exact warning details, and rollback pass. |
| 7 | `python -m pytest tests/test_limits.py tests/test_validation.py -q`: exact integer estimate and aggregate overflow pass. |
| 8 | `python -m pytest tests/test_csv_import.py -q`: byte/shape/decode limits produce distinct positioned errors. |
| 9a | `python -m pytest tests/test_csv_import.py -q`: headers, hour labels, and positioned ignored-material warnings pass. |
| 9b | `python -m pytest tests/test_csv_import.py -q`: sample/shuffled demand matches exactly; all discoverable cell errors have positions. |
| 10 | `python -m pytest tests/test_scheduling_service.py tests/test_csv_import.py -q`: initial import and pre-import setting survive reopen; invalid import is atomic. |
| 11 | `python -m pytest tests/test_metrics.py tests/test_scheduling_service.py -q`: exact ratios, coverage, grouped roster, and reconciliation pass. |
| 12 | `python -m pytest tests/test_generation.py -q`: prerequisites, score policy, and partial drafts pass. |
| 13 | `python -m pytest tests/test_generation.py -q` passes; run `python -m pytest tests/test_performance.py -q -s` locally and record generation time against 10 seconds. |
| 14 | `python -m pytest tests/test_refresh.py -q`: empty/direct and nonempty/confirmed regeneration, token/version protection, and rollback pass. |
| 15 | `python -m pytest tests/test_refresh.py -q`: refresh previews are read-only; invalid and ineligible proposals cannot write. |
| 16a | `python -m pytest tests/test_refresh.py -q`: snapshot JSON round-trip, immutable read, and schedule isolation pass. |
| 16b | `python -m pytest tests/test_refresh.py -q`: exactly one prior-state snapshot and one replacement commit together; stale/altered/cancelled confirmation and injected failure leave neither change. |
| 17 | `python -m pytest tests/test_schedule_service.py tests/test_scheduling_service.py tests/test_csv_import.py tests/test_metrics.py tests/test_generation.py tests/test_refresh.py -q` passes AC-01–AC-19; run `python -m pytest tests/test_performance.py -q -s` locally and record all three scenario timings separately. |
| 18 | Full required gate above; `git diff --check` and `git status --short` show no whitespace error or unrelated changes. |

## 5. Spec traceability

| Requirement | Implementation step(s) | Main proof |
|---|---|---|
| FR-1 Schedule lifecycle/isolation | 1–3, 17 | AC-01; defaults, rename, independent schedule IDs. |
| FR-2 Staff/capacity | 1, 4–6b, 11, 17 | AC-02, AC-08, AC-17; exact warning and confirmed deletion. |
| FR-3 Shifts/daily limit | 2a–2b, 4–6b, 17 | AC-07, AC-16; all affected assignments checked. |
| FR-4 CSV/import | 7–9b, 10, 15–17 | AC-03–AC-05, AC-15, AC-17; complete normalization and atomic import. |
| FR-5 Required estimate/settings | 1, 7, 10–11, 15–17 | AC-06, AC-15, AC-17. |
| FR-6 Unified validation/manual edits | 4–6b, 11, 17 | AC-07–AC-09; commit iff no error. |
| FR-7 Deterministic draft | 11–14, 17 | AC-10–AC-12, AC-18–AC-19; exact assignment sets/invariants. |
| FR-8 Regeneration/refresh safety | 2–3, 10, 14–17 | AC-15–AC-18; cancellation, stale version, rollback, snapshot. |
| FR-9 Coverage/transaction metrics | 7, 11–13, 16–17 | AC-09, AC-13–AC-15; reconciled hours and undefined ratios. |
| FR-10 Layers/persistence | 1–3, 5–6b, 10–11, 14–18 | AC-01, AC-15–AC-17; reopen and immutable history. |
| NFR Performance | 9a–9b, 11, 13, 17 | Separate import/metrics, pure generation, and refresh timings. |
| NFR Security/input limits | 1–2b, 4–10, 14–17 | Boundary, ownership, CSV cap, token, JSON, and overflow tests. |
| NFR Reliability | 2a–3, 5–6b, 10, 14–17 | FK, repeat read, cancellation, fault injection, transaction rollback. |
| NFR Determinism | 11–13, 17 | Exact repeated roster/metric sets and ordered ties. |
| NFR Compatibility | 2–4, 18 | Legacy migration and existing name/time-helper tests. |
| NFR Error contracts | 1, 4–10, 12, 14–17 | Stable codes, severity, field/position, and prerequisite details. |

## 6. Implementation risks and assumptions

- **No planned conflict or dependency:** All steps follow the approved design and AGENTS.md; no step needs a new package. The plan uses CSV bytes, so it introduces no upload file-path handling. If a later implementation chooses paths, it must canonicalize and confine them to an allowed base before reading.
- **Migration risk (Step 2):** Existing databases contain only `schedules(id,name)`. SQLite `ALTER TABLE` and default-shift backfill must be idempotent and transactional; a legacy ID or allocated ID above the ceiling needs a clear failure rather than truncation.
- **Transaction risk (Steps 14–16):** `connect_database` currently commits on context exit. The implementation must make explicit `BEGIN IMMEDIATE` compatible with that context manager and ensure one rollback covers snapshot, input, assignments, and version. Preview and confirmation may be in different processes; process-key tokens expire on restart by design.
- **Capacity/performance risk (Steps 12–17):** Unbounded employee and shift counts make worst-case greedy runtime uncertain. The accepted target is 100 employees/32 shifts within 10 seconds. Record a local benchmark and investigate a miss; no hard CI timing assertion is planned. Do not add a hard input cap or optimizer without a separate design decision.
- **Snapshot schema risk (Step 16):** Canonical JSON must be versioned and validated on read. Preserve captured analytics rather than recomputing against current data; avoid recursively copying older snapshots.
- **Assumption on confirmation API:** `confirmed=False` is a no-op for destructive/removal and replacement methods. A signed preview is mandatory for nonempty roster replacement and post-import refresh; confirming a token is not authentication.
- **Resolved error contract:** Use typed exceptions for invalid operations, carrying attached `Violation`/finding lists with fixed codes and consistent field/ID/position details; successful operations return typed results. Settle class names when Step 1 introduces the model; do not scatter ad hoc `ValueError` messages across use cases.
- **Documentation status:** The spec/design headers still say “proposed,” while this task identifies them as approved. Treat the user's approval as authoritative for planning; no source document is edited here.

## 7. Open questions (for manager review)

None. The manager resolved the three implementation choices: use one public `ScheduleService` facade with private helpers, use typed exceptions with attached findings for invalid operations and typed success results, and record the performance targets as local benchmarks rather than hard CI timing assertions.

No implementation step is flagged as conflicting with the approved design or AGENTS.md, and none requires a new dependency.
