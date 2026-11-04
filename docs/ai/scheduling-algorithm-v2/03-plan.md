# Scheduling algorithm v2 — Stage 3 implementation plan

> **For implementation after review:** this plan is based on the approved
> [specification](01-spec.md) and [design](02-design.md). It authorizes no source
> changes during Stage 3.

**Task:** `scheduling-algorithm-v2`

## 1. Implementation summary based on the approved design

Replace the current one-pass absolute-benefit generator in
`src/domain/generation.py` with a pure, typed, deterministic four-phase generator:
preparation and validation, feasible-triple construction, fixed-order refinement,
and diagnostics. Preserve the existing `ScheduleService` generation, preview,
confirmation, and refresh workflows as adapters around the new outcome. Keep SQLite
as the only persistence layer, diagnostics transient, and existing BR-10 metrics and
manual-warning behavior unchanged.

Use the approved configuration defaults and ordering; calculate demand, effective
capacity, primary cost `C`, fairness cost `F`, deltas, and density comparisons with
integer arithmetic. Share H1-H5 feasibility predicates between automatic assignment
and state validation without changing manual warning severities. Apply ADD closure,
DROP, MOVE, and mandatory REPLACE in fixed order with deterministic traces and count
caps. Then derive lower-bound, employee, shortfall, flag, and trace diagnostics from
the final draft.

Integrate diagnostics into the matching generated result or read-only preview only.
Show them in the current generation summary and staff workspace; clear them when the
result is reloaded or a manual change replaces it. Keep the existing confirmation
and transaction boundaries. Update the README to explain the new policy and its
limitations. Do not change the database schema, assignment source documents, CSV
fixture, unrelated workflows, or dependencies.

**Implementation sequencing rule:** keep each implementation step independently
verifiable and target fewer than about 200 changed lines per step. If a step grows
beyond that, split it at a tested behavior boundary before proceeding.

## 2. Files to create or modify

| Path | Change | Why |
|---|---|---|
| `src/model/scheduling.py` | Add typed immutable generation config, outcome, diagnostics, employee-capacity, shortfall, flag, and trace records; add an optional generation-diagnostics field to the result carried by a generated result or preview. | Keep domain results typed and carry transient diagnostics through existing service and UI paths. |
| `src/domain/generation.py` | Replace the v1 selection loop with preparation, exact bounded capacity, objective evaluation, construction, refinement, and final diagnostic phases. Preserve a `generate_draft` adapter if needed for existing callers. | Implement the approved algorithm without I/O or mutation while limiting compatibility impact. |
| `src/domain/validation.py` | Extract/reuse H1-H5 predicates for automatic candidate checks and complete-state validation; preserve existing manual warning severities. | Ensure an auto-feasible assignment and state validation use the same hard-rule definitions. |
| `src/services/schedules.py` | Invoke the pure outcome, map prerequisite blocks to legacy `SchedulingError` codes, and return diagnostics for generated, previewed, and actually committed drafts. Preserve version checks and transaction boundaries. | Keep existing lifecycle APIs and ensure shown diagnostics match the proposed or committed roster. |
| `ui/roster.py` | Render the lower bound, optimizer diagnostics, slot/hour reasons, flags, and optional decision trace for the current generation or preview. | Present the generation explanation in the roster context. |
| `ui/demand_panel.py` | Include generation diagnostics in a generated refresh preview, keeping its proposal read-only and version-bound. | Ensure a generated refresh proposal and its explanation refer to the same draft. |
| `ui/staff_panel.py` | Show effective capacity and target hours as secondary information only when current generation diagnostics are available; retain assigned/raw maximum as primary. | Expose the approved fairness context without changing ordinary staff analytics. |
| `ui/session.py` | Adjust transient-state handling only if needed so reloads, stale previews, schedule changes, and manual edits cannot retain generation diagnostics as current. | Enforce the transient lifecycle already used by the page session. |
| `tests/test_generation.py` | Add pure tests for configuration, capacity, costs, ordering, construction, refinement, diagnostics, invariants, and reproducibility. | Make the algorithm's required behaviors independently fail when broken. |
| `tests/test_scheduling_service.py` | Cover prerequisite mapping, no-write behavior, and diagnostic identity across generation and committed results. | Protect the service adapter and persisted-state contract. |
| `tests/test_refresh.py` | Cover diagnostics on refresh preview/confirmation and preservation of existing cancellation, stale-version, and rollback behavior. | Protect the existing atomic refresh lifecycle. |
| `tests/test_ui_presentation.py`, `tests/test_ui_workflows.py`, `tests/test_ui_session.py` | Assert diagnostic content, correct generated-preview presentation, and clearing after reload/manual edit. | Verify user-visible content and transient-state behavior. |
| `tests/test_performance.py` | Extend opt-in local scenarios for the 100-employee/32-shift generator and exact capacity at representative maxima, including `2^31 - 1`. | Verify the stated performance/resource behavior without machine-dependent CI timing assertions. |
| `README.md` | Document the `N`/demand assumption, cost and stop rule, effective-capacity fairness and REPLACE, reproducibility, heuristic limitations/lower bound, and optimizer-cost versus linear-metric distinction. | Keep behavior and operator expectations documented. |
| `tests/test_scripts.py` | Change only if needed to verify the existing generate command remains compatible with the preserved service adapter. | Protect current command-line callers without adding a separate diagnostic workflow. |

No new source file is currently required. A separate focused test module may be
introduced only if the existing generation tests become too large to review. No
dependency or database-schema change is planned.

## 3. Small, ordered implementation steps

1. **Add generation contracts and boundary validation.** Add config, blocked/success
   outcome, and diagnostic record types, plus pure validation of integer types,
   ranges, complete demand, references, and prerequisite precedence. Keep `N` and
   `L` sourced from the schedule's threshold and daily shift limit unless the
   approved config explicitly overrides them for tests. Test invalid configurations,
   absent versus all-zero demand, blocked outcome order, and no input mutation.
   **Verify:** focused new tests in `tests/test_generation.py`; existing
   `tests/test_generation.py` and `tests/test_scheduling_service.py`.

2. **Implement exact effective capacity.** Add the approved bounded duration-residue
   method, with precomputed distinct durations and a bounded DP independent of the
   weekly maximum. Test against a straightforward recurrence/reference DP on small
   inputs, mixed duration tables and `D × L` bounds; test zero capacity and values
   through `2^31 - 1` without allocating by maximum hours. Record the method's
   time/memory bound. **Verify:** focused capacity tests in
   `tests/test_generation.py`; opt-in capacity benchmark in `tests/test_performance.py`.

3. **Unify hard assignment feasibility.** Extract the H1-H5 checks for candidate
   placement and full-state validation. Preserve warning results for manual weekly
   and daily overages; ensure generated candidates reject both. Cover weekly limits,
   daily count, overlap versus adjacent shifts, duplicate assignments, invalid
   references, and stable existing warning severities.
   **Verify:** `python -m pytest tests/test_generation.py tests/test_validation.py -q`.

4. **Implement integer objective primitives.** Add required-headcount calculation
   for configurable `N`, primary bucket cost and exact `ΔC`, excess delta, total
   fairness cost `F`, and exact `ΔF`. Keep `F=0` when `sumCap=0`; block generation
   before construction when there is no eligible positive-capacity staff. Test
   marginal costs at empty, under-covered, covered, and excess buckets, fairness
   ties, and weights that differ from defaults.
   **Verify:** focused objective tests in `tests/test_generation.py`.

5. **Implement canonical preparation and construction.** Sort employees by creation
   order then stable ID, days ascending, and shifts by `(start_hour, end_hour, id)`;
   precompute coverage and overlap, and maintain staffing and employee state
   incrementally. Construct only feasible triples with negative `ΔC`, choosing the
   exact cost-density and tie chain from the design. Start from an empty assignment
   set. Establish and test the deterministic preflight candidate-work/trace budget
   using the 100-employee/32-shift scenario; reject excessive work explicitly without
   narrowing the maximum-hours API. Test approved Examples A-C, zero-demand hours,
   partial capacity, tie dimensions, and repeatability.
   **Verify:** `python -m pytest tests/test_generation.py -q`; opt-in pure-generation
   benchmark in `tests/test_performance.py`.

6. **Implement ADD closure, DROP, and MOVE refinement.** Run fixed-order passes;
   apply the documented ADD closure, then scan and evaluate DROP and tentative MOVE
   against the resulting roster. Restore rejected moves and accept only the specified
   strict `(C,F)` improvements. Check H1-H5 after each accepted change and append
   deterministic trace records with exact deltas. Test rejected/restored moves,
   destination tie order, monotonic objective, trace order, and feasibility after
   each action. **Verify:** focused refinement and invariant tests in
   `tests/test_generation.py`.

7. **Implement REPLACE and refinement stopping.** Add coverage-neutral employee
   replacement, accepting only `ΔF < 0`; enforce `maxPasses` and `maxMoves` and
   return a valid best-so-far result with an explicit capped indicator. Test the
   approved Example E, rejected fairness-worsening replacement, canonical
   replacement ties, cap boundaries, and that no local-optimality claim is made
   after a cap. **Verify:** focused REPLACE/cap tests in `tests/test_generation.py`.

8. **Implement final diagnostics.** Calculate linear metrics separately from `C`
   and `F`; add lower-bound values and wording, employee utilization/targets,
   exactly one ordered reason per shortfall slot, uncovered-hour records,
   informational flags, and deterministic final trace/cost values. Test every
   reason, overlapping slot semantics, no-shift coverage, zero denominators,
   `unavoidableUnmet <= totalUnmet`, and flag conditions including the verified
   near-zero explanation rule. **Verify:** focused diagnostics tests in
   `tests/test_generation.py`; `tests/test_metrics.py`.

9. **Integrate pure outcomes with service lifecycle.** Adapt `generate`,
   `preview_generation`, `confirm_generation`, and refresh preview/confirmation.
   Map prerequisite blocks to legacy service error codes; leave writes untouched on
   blocked/invalid outcomes. Attach diagnostics only to generated results/previews,
   and ensure committed diagnostics describe the actual committed draft even if
   temporary trace assignment IDs need mapping. Preserve the existing empty-roster
   behavior, version-bound token checks, stale rejection, and atomic refresh.
   **Verify:** `python -m pytest tests/test_generation.py tests/test_scheduling_service.py tests/test_refresh.py -q`.

10. **Present diagnostics and enforce transient UI behavior.** Add current-generation
    and preview presentation to the roster and refresh confirmation, employee
    effective-capacity/target details in the staff workspace, and an optional trace
    view if it fits the existing UI patterns. Confirm ordinary reads/manual edits
    show no stale generation diagnostics. **Verify:**
    `python -m pytest tests/test_ui_presentation.py tests/test_ui_workflows.py tests/test_ui_session.py -q`.

11. **Document, complete acceptance coverage, and run final gates.** Update README
    policy and limitations, complete any uncovered AC-1 through AC-12 tests, confirm
    `scripts/generate.py` remains compatible, and record opt-in benchmark results and
    the capacity method's resource bounds. Run the full repository gate and inspect
    the diff for unrelated files. The implementation chat must append its single
    required change-log entry; this Stage 3 documentation-only chat does not require
    one. **Verify:** full `python -m pytest`; `python -m ruff check .`;
    `python -m ruff format --check .`; `python -m compileall -q src ui tests main.py`;
    `git diff --check`. Run `RUN_SCHEDULING_BENCHMARKS=1 python -m pytest
    tests/test_performance.py -q -s` locally and report timings without hard CI
    thresholds.

## 4. Verification for each step

The focused commands and expected behaviors are listed per implementation step
above. For each source-changing step, also run `python -m ruff check .`,
`python -m ruff format --check .`, and
`python -m compileall -q src ui tests main.py`; run its focused pytest selectors
before proceeding. The final gate in Step 11 additionally requires the full pytest
suite and `git diff --check`. Local performance scenarios are opt-in and report
timings; they must not assert machine-specific elapsed time.

The acceptance tests must establish observable behavior, not merely duplicate
implementation formulas. In particular:

- Capacity tests compare against a reference recurrence for tractable cases and
  exercise the public maximum without maximum-proportional memory.
- Feasibility tests inspect every accepted intermediate action or equivalent
  invariant hooks, not only the final roster.
- Reproducibility tests compare assignments, costs, metrics, flags, and trace.
- Service/UI tests compare the diagnostics against the exact draft shown and verify
  diagnostics disappear after reload or manual editing.
- Existing refresh tests continue to prove cancellation, stale-token rejection, and
  transaction rollback for active state and history.

## 5. Spec traceability

| Requirement | Implementation step(s) | Main evidence |
|---|---|---|
| FR-1 — pure input, configuration, prerequisites, lifecycle | 1, 5, 9 | Config and blocked-outcome tests; legacy error mapping; zero-write service rejection; valid zero demand. |
| FR-2 — canonical preparation and effective capacity | 2, 5, 8 | Reference recurrence and API-maximum tests; capacity bound and lower-bound diagnostics. |
| FR-3 — cost and fair-share objective | 4, 5, 6, 7, 8 | Exact marginal, cost-density, lexicographic objective, and REPLACE fairness tests. |
| FR-4 — feasible-triple construction | 3, 5 | H1-H5 shared predicates, Examples A-C, canonical ties, and accepted-state invariants. |
| FR-5 — deterministic refinement | 6, 7 | ADD/DROP/MOVE/REPLACE ordering, monotonic improvements, restoration, and cap tests. |
| FR-6 — generation diagnostics | 8 | Slot/hour reason, employee metrics, flags, bound, cost, cap, and trace assertions. |
| FR-7 — service, UI, and documentation | 9, 10, 11 | Version-bound service tests, UI content/transience tests, and README policy review. |
| NFR — determinism and precision | 4-9, 11 | Integer delta/cross-product tests and repeated complete-output comparisons. |
| NFR — performance and bounded work | 2, 5, 7, 11 | API-maximum capacity tests, preflight-budget tests, and opt-in representative benchmark. |
| NFR — security and reliability | 1-3, 5, 9-11 | Boundary rejection, no mutation on error, H1-H5 invariants, stale-preview and atomicity tests. |
| NFR — compatibility | 3, 9, 11 | Manual warning severity, existing metrics/workflows, service adapter and CLI regression tests. |
| NFR — verification gate | 11 | Full pytest, Ruff lint/format, compileall, and diff check. |

## 6. Implementation risks and assumptions

- **Approved design/spec authority:** Both input document headers still say
  “Proposed for review,” while this request identifies them as approved. This plan
  treats the explicit approval in the task as authoritative and does not edit either
  input document.
- **Capacity proof and bounded resources:** The duration-residue method depends on
  positive whole-hour durations and production's maximum 16-hour shift window.
  Validate it against a simpler recurrence on tractable instances and test the
  `2^31 - 1` input. Do not replace correctness with a lower hidden weekly-hours cap.
- **Creation order:** The current DB loader orders employees by stable ID, matching
  creation order for current inserts. Preserve that order and use ID as the final
  tie-break; do not rely on incidental database iteration order.
- **Search budget:** The design calls for an explicit candidate-work/trace budget
  based on the 100-employee/32-shift benchmark, but does not state its numeric
  threshold. Choose and document a deterministic work-count rule during
  implementation; reject before persistence and do not use wall-clock termination.
  This budget must not narrow the weekly-maximum API.
- **Commit/trace identity:** SQLite assigns committed assignment IDs, while the
  pure trace may use deterministic temporary IDs. Ensure diagnostics returned after
  confirmation refer to the committed roster and remain reproducible; test this
  integration explicitly.
- **Transient diagnostics:** A normal `get_schedule` result has no generation
  diagnostics. Manual edits, reloads, schedule switches, and stale confirmation
  must not show old diagnostics as current. Do not persist diagnostics or trace.
- **UI surface:** The current roster and staff panels display only ordinary
  schedule metrics. Diagnostics must remain secondary to the roster and staff's
  assigned/raw maximum values; avoid turning optimizer costs into manager-facing
  coverage metrics.
- **No conflict/dependency flagged:** No planned step conflicts with the approved
  design or `AGENTS.md`; no new dependency, schema change, resource-document edit,
  or sample-CSV edit is planned.

## 7. Open questions (for me to answer)

None block implementation planning. The design already resolves Tier C exclusion,
the transient diagnostics policy, and the requirement for a measured deterministic
work budget. Its open numeric budget threshold is an implementation measurement,
not a product decision. The proposed-status header mismatch is recorded above; the
explicit approval in this task is assumed authoritative.
