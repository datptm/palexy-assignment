# Scheduling algorithm v2 — Stage 4 test design and red run

**Task:** `scheduling-algorithm-v2`  
**Inputs:** approved [specification](01-spec.md), [design](02-design.md), and
[plan](03-plan.md).  
**Scope:** tests and test documentation only; do not implement algorithm or UI
behavior in this stage. The request's `{{extra cases I want}}` placeholder did
not specify additional cases; coverage below follows the approved inputs.

## Proposed executable contract for review

The approved documents define required behavior but leave the domain entry-point
names and some result-record field names open. These tests make the following
Python-facing contract explicit:

- `src.domain.generation.generate_roster(state, config=GenerationConfig())`
  is pure and returns an outcome with `blocked_code`, `message`, `draft`, and
  `diagnostics`. A successful outcome has no blocked code and includes a
  generated `ScheduleState` plus diagnostics; a blocked outcome has no draft or
  diagnostics. It begins from an empty roster, regardless of `state.assignments`.
- `GenerationConfig` defaults to `day_count=7`, operating hours `[7,23)`,
  `w_under=3`, `w_over=1`, `w_empty=6`, `max_passes=50`, `max_moves=5000`,
  and `rest_weight=0`. `day_count`, `open_start_hour`, and `open_end_hour`
  parameterize small test instances. Demand threshold and daily shift limit are
  sourced from `ScheduleState`; configuration may override them only if needed
  for deterministic small-instance tests.
- `effective_capacity(maximum, durations, max_shifts)` exposes the exact,
  bounded capacity calculation for direct comparison with a small reference
  recurrence. `rank_add_candidates(state, config=...)` returns only feasible
  negative-`ΔC` additions in the specified deterministic density/tie order.
  `refine_roster(state, config=...)` refines the assignments already carried by
  that state; this phase entry point permits the approved Example E state to be
  tested without changing the generation rule that normal generation starts
  empty. `can_auto_assign(state, employee_id, day, shift_id)` exposes the shared
  H1–H5 feasibility predicate used by automatic placement.
- Diagnostics expose `primary_cost`, `fairness_cost`, `required_hours`,
  `capacity_hours`, `unavoidable_unmet`, `lower_bound_message`, `employees`,
  `shortfalls`, `flags`, `trace`, `rest_violations`, and `refinement_capped`.
  Trace records expose the action, employee and slot IDs, exact `delta_cost`
  and `delta_fairness`, plus source/replaced employee IDs where relevant;
  MOVE records additionally expose `source_day` and `source_shift_id` so a
  trace can be replayed and each intermediate roster checked.
  Slot/hour records use `kind` (`slot` or `hour`), `reason`,
  `unmet_staff_hours`, and their applicable day/hour/shift identifiers.
- Service results and preview drafts expose optional
  `generation_diagnostics`. Ordinary `get_schedule` results and results after
  manual edits or reload have no generation diagnostics. UI labels used as
  test-facing content are “Generation diagnostics”, “Unavoidable shortage
  lower bound”, “Optimizer cost”, “Linear coverage metrics”, “Effective
  capacity”, and “Target hours”; stable diagnostic reason/flag codes remain
  visible.
- Invalid configuration raises `SchedulingError` with code
  `INVALID_GENERATION_CONFIG`; malformed or incomplete demand raises
  `SchedulingError` with code `INVALID_DEMAND`. Pure prerequisite blocks use
  `NO_DEMAND`, `NO_SHIFTS`, and `NO_ELIGIBLE_STAFF`; the service maps these to
  legacy `MISSING_DEMAND`, `MISSING_SHIFTS`, and `NO_ELIGIBLE_EMPLOYEE`.

These are proposed names/shapes, not claims about existing behavior. If review
chooses different names, update this contract and the tests together before
implementation; tests deliberately use `require_symbol` for new entry points
so absent features fail as assertions during execution, not as collection or
import errors.

## Test matrix

Parameterized test functions execute every listed variant. Unit tests use small
in-memory records and no external services. Integration tests use temporary
SQLite databases; the UI tests use the repository's isolated NiceGUI
`manager_page` helper. Existing fixtures are not modified.

| Test name | Spec ref (FR/NFR/edge case) | Type | Expected result |
|---|---|---|---|
| `test_generation_v2.py::test_pure_generator_reports_prerequisite_blocks_in_order` | FR-1; AC-1; edge: missing demand/shifts/staff | unit | Pure outcome blocks with the specific reason and actionable message; no draft/diagnostics. |
| `test_generation_v2.py::test_zero_transactions_are_valid_one_person_demand_and_input_is_unchanged` | FR-1; AC-1; zero is not missing | unit | Zero-count buckets still require one person; input state is unchanged. |
| `test_generation_v2.py::test_demand_uses_integer_ceiling_and_never_treats_zero_as_missing` | FR-1/2; NFR precision; demand boundaries | unit | Counts `0,20,21,40,41` at `N=20` require `1,1,2,2,3` staff respectively. |
| `test_generation_v2.py::test_invalid_generation_configuration_is_rejected_explicitly` | FR-1; NFR security/reliability | unit | Invalid weights, caps, booleans, and fractional bounds raise `INVALID_GENERATION_CONFIG`. |
| `test_generation_v2.py::test_incomplete_or_malformed_demand_is_rejected_before_search` | FR-1; NFR security/reliability | unit | Incomplete configured demand raises `INVALID_DEMAND` before producing output. |
| `test_generation_v2.py::test_effective_capacity_matches_exact_bounded_duration_result` | FR-2; AC-2; zero and `2^31−1` maxima | unit | Example D and the public maximum return exact recurrence values. |
| `test_generation_v2.py::test_effective_capacity_matches_small_reference_recurrence` | FR-2; NFR bounded work | unit | Mixed duration tables match a straightforward bounded reference recurrence. |
| `test_generation_v2.py::test_default_marginals_stop_at_zero_delta_but_custom_policy_can_add` | FR-3/4; AC-3; Example A / AT-32 | unit | Default weights stop after three staff at `ΔC=0`; approved alternate weights add the fourth. |
| `test_generation_v2.py::test_empty_hour_is_preferred_over_a_second_person_on_a_busy_day` | FR-3/4; AC-4; Example B / AT-38 | unit | One worker is placed on each of Monday and Tuesday; no day is double-staffed. |
| `test_generation_v2.py::test_cost_density_ranks_four_hour_peak_before_eight_hour_shift` | FR-4; AC-5; Example C / AT-39 | unit | The 4-hour peak ranks first on Monday, then Tuesday, with exact negative `ΔC`. |
| `test_generation_v2.py::test_canonical_input_order_produces_identical_assignments_metrics_and_trace` | FR-2/4/5/6; AC-8; determinism | unit | Permuted employee/shift input order yields identical draft and complete diagnostics. |
| `test_generation_v2.py::test_generation_starts_empty_and_every_trace_step_preserves_hard_rules` | FR-1/4/5; AC-6/11; H1–H5 | unit | Existing manual assignments are not inherited; generated references, hours, and decisions are valid and improving. |
| `test_generation_v2.py::test_can_auto_assign_uses_weekly_daily_overlap_and_reference_constraints` | FR-4; AC-6; edge: adjacent/overlap/unknown refs | unit | The shared feasibility predicate rejects weekly, overlap, and invalid-reference candidates. |
| `test_generation_v2.py::test_refinement_replaces_overallocated_staff_without_changing_coverage` | FR-3/5; AC-7; Example E / AT-37 | unit | Alice→Diana REPLACE preserves `C` and reduces `F` from 3200 to 1792. |
| `test_generation_v2.py::test_refinement_rejects_fairness_worsening_replacement_and_reports_caps` | FR-5; AC-6/7; cap edge | unit | No accepted action worsens `(C,F)`; a move cap returns a valid draft with `REFINEMENT_CAPPED`. |
| `test_generation_v2.py::test_slot_shortfall_reasons_are_specific_and_lower_bound_is_conservative` | FR-2/6; AC-9; stop/capacity/day constraints | unit | Each constructed shortage receives the expected single reason; lower bound does not exceed actual unmet hours. |
| `test_generation_v2.py::test_uncovered_operating_hour_has_its_own_hour_level_shortfall` | FR-6; AC-9; uncovered hour | unit | An unmet open hour outside shifts has exactly one hour-level `NO_SHIFT_COVERAGE` record. |
| `test_generation_v2.py::test_employee_diagnostics_and_flags_handle_zero_denominators` | FR-6; zero effective capacity | unit | Zero-capacity utilization is `N/A`; costs and Tier A/B rest count are well-defined. |
| `test_generation_v2.py::test_utilization_flags_identify_low_and_near_zero_positive_capacity_staff` | FR-6; informational flags | unit | Low-utilization and near-zero/others-full conditions are surfaced. |
| `test_generation_v2.py::test_shortage_free_result_has_empty_shortfall_report_and_zero_bound` | FR-6; no unmet demand | unit | No shortfall records, zero lower bound, and zero linear unmet hours. |
| `test_scheduling_algorithm_v2_service.py::test_blocked_generation_maps_legacy_error_and_preserves_everything` | FR-1; AC-1/11; no-write failure path | integration | Legacy service error code is raised and schedule state/version/history remain unchanged. |
| `test_scheduling_algorithm_v2_service.py::test_generation_preview_is_read_only_and_confirmed_diagnostics_match_result` | FR-7; AC-10/11; preview/cancel/confirm lifecycle | integration | Preview does not write; confirmed draft diagnostics match; ordinary reload has no transient diagnostics. |
| `test_scheduling_algorithm_v2_service.py::test_competing_generation_previews_reject_stale_confirmation_without_lost_update` | FR-7; AC-11; concurrency/version conflict | integration | Two service instances can preview one version; only the first confirmation commits, the stale one cannot overwrite it. |
| `test_scheduling_algorithm_v2_service.py::test_generated_refresh_preview_and_commit_carry_the_same_draft_diagnostics` | FR-7; AC-10/11; atomic refresh | integration | Refresh preview and committed draft expose the same diagnostics for the actual generated roster. |
| `test_scheduling_algorithm_v2_ui.py::test_generation_summary_explains_shortfalls_and_clears_transient_diagnostics` | FR-6/7; AC-10; UI and transient lifecycle | integration | UI shows lower bound, optimizer details, uncovered-hour reason, effective capacity/target; manual edit and reload clear diagnostics. |
| `test_scheduling_algorithm_v2_ui.py::test_generation_explanation_keeps_linear_metrics_distinct_from_optimizer_cost` | FR-3/7; AC-10; metric compatibility | integration | UI labels optimizer costs separately from existing linear coverage metrics. |

## Test data, fixtures, and mocks

- Pure tests construct immutable `ScheduleState`, `Employee`, `ShiftDefinition`,
  `DemandCell`, and `Assignment` records in the test module. The demand count is
  the required headcount because these focused fixtures set the schedule
  threshold to one. Small `day_count` and operating windows keep examples
  bounded and make each expected slot unambiguous.
- Effective-capacity tests use the approved Example D values, a `2^31−1`
  maximum, and a small independent reachable-sum recurrence. The reference
  recurrence is intentionally limited to small inputs; it is not used as the
  production algorithm.
- Existing `tests.scheduling_support.week_csv` builds synthetic complete CSV
  reports for service/UI integration. UI tests reuse `tests.ui_support.manager_page`
  with a temporary SQLite file. No fixture file or supplied transaction data is
  modified.
- No clock, randomness, network, external service, or database calls are mocked.
  SQLite is exercised against per-test temporary files to verify transaction,
  version, and stale-preview behavior. UI tests use the project's local
  NiceGUI user simulation rather than a live browser.

## Spec items not covered by automated tests

- The exact upper bound on memory/time for the capacity method is not measured
  with a machine-specific benchmark. Tests exercise exact values at
  `2^31−1`; code review and the implementation's documented algorithm must
  establish the resource bound.
- The approved design leaves the numeric deterministic candidate-work/trace
  budget to implementation measurement. It is not pinned here to avoid
  inventing a product limit; the chosen limit and explicit rejection behavior
  must be documented and reviewed during implementation.
- `NO_ELIGIBLE_STAFF` is covered as a blocked prerequisite. A successful
  generation cannot have a slot-level `NO_ELIGIBLE_STAFF` reason when the
  prerequisite blocks the whole run first; that diagnostic ordering is
  therefore not asserted as a successful-output case.
- Concurrent preview writers are tested using independent service instances
  and competing version-bound previews, then sequential confirmations. A
  thread-timing stress test is intentionally omitted because it would be
  nondeterministic and would not improve the version-conflict assertion.
- UI wording/content and diagnostic transience are tested, but desktop/narrow
  visual layout, accessibility with assistive technology, and the README's
  explanatory prose still require review/manual walkthrough.
- Tier C rest-gap behavior, `N` sensitivity, shift suggestions, and comparison
  harness are explicitly excluded by the approved scope.

## Failing-test summary

Final full-suite command:
`.venv\Scripts\python.exe -m pytest -q --tb=line -p no:cacheprovider`
reported **48 failed, 136 passed, 3 skipped in 34.96s**. All 48 failures are
intentional red-stage feature-contract failures:

- The 44 cases in `tests/test_generation_v2.py` fail because the v2 domain
  contract is not implemented: `generate_roster`, `GenerationConfig`,
  `effective_capacity`, `rank_add_candidates`, `can_auto_assign`, or
  `refine_roster` is absent. `require_symbol` reports each absence as an
  assertion during test execution.
- `test_generation_preview_is_read_only_and_confirmed_diagnostics_match_result`
  and
  `test_generated_refresh_preview_and_commit_carry_the_same_draft_diagnostics`
  fail because `ScheduleResult.generation_diagnostics` is not present.
- `test_generation_summary_explains_shortfalls_and_clears_transient_diagnostics`
  and
  `test_generation_explanation_keeps_linear_metrics_distinct_from_optimizer_cost`
  fail because the planned diagnostic labels/content are not rendered yet.

The parameterized legacy prerequisite mapping/no-write cases and competing
stale-preview integration case pass. The run collected successfully: there were
no syntax, import, fixture, or collection errors. The three skipped tests are
the repository's opt-in local performance benchmarks. The 48 failures above
are therefore for missing v2 behavior, not test setup defects.
