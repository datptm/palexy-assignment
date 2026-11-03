# Core scheduling logic — Stage 4 test design and red run

**Task:** `core-scheduling-logic`  
**Inputs:** approved [specification](01-spec.md), [design](02-design.md), and [plan](03-plan.md).  
**Scope:** tests only. The scheduling feature is not implemented in this stage. The literal `{{extra cases I want}}` in the request did not include any additional case; the cases below follow the approved inputs.

## Proposed executable contract for review

The plan names the facade operations but leaves some signatures and record fields to the implementing step. These tests propose the following concrete contract. Review these names and shapes before implementation; changing them later requires updating the tests and this matrix together.

- `ScheduleService.get_schedule(id)` returns a value-oriented result with `.state`, `.warnings`, `.hourly`, `.weekly`, and `.employees`. State carries `id`, `name`, `version`, `threshold`, `daily_shift_limit`, `employees`, `shifts`, `demand` (`None` before import), and `assignments`. Child records expose the IDs and fields named in the tests.
- Mutators use the positional order `(schedule_id, entity_id or values...)`; `import_initial(schedule_id, csv_bytes)`, `preview_refresh(schedule_id, csv_bytes=... | threshold=...)`, and `confirm_refresh(schedule_id, token, same proposal, confirmed=True)` are the assumed refresh calls. A cancelled confirmation returns `None`. Preview records expose `.token`, `.baseline_version`, and `.draft`.
- `src.domain.limits.bounded_int(value, field=..., minimum=...)`, `src.domain.shifts.validate_shift_range(start,end)`, `src.domain.demand.required_staff(count,threshold)`, and `src.domain.csv_import.parse_transactions_csv(bytes)` are the proposed pure entry points. Parsed cells carry `day` as `0..6`, `hour` as `7..22`, and `transactions`.
- Invalid operations raise `src.model.scheduling.SchedulingError` with `.code`, `.details`, and `.findings` where multiple CSV findings exist. Names such as `INVALID_CSV`, `RESOURCE_LIMIT`, `INVALID_ENCODING`, `INVALID_HOUR`, `DUPLICATE_HOUR`, `DUPLICATE_WEEKDAY`, `INTEGER_OVERFLOW`, `MISSING_DEMAND`, `MISSING_SHIFTS`, `NO_ELIGIBLE_EMPLOYEE`, `STALE_PREVIEW`, and `INVALID_PREVIEW` are proposed stable codes. Codes explicitly fixed in FR-6 retain their specified spelling.
- Equality of a reopened result means the same value-oriented state and metrics. Snapshot reads expose captured `.state`, `.hourly`, `.weekly`, and `.reason`.

`tests/scheduling_support.py` keeps absent planned modules and methods as explicit assertions at **test execution**, so the current red suite collects cleanly. It does not replace behavior assertions. Once an entry point exists, each test proceeds to the observable result or rejected-state comparison.

## Test matrix

Parameterized functions count as one matrix row with all named values executed by pytest. Every row is implemented in the file indicated by its prefix.

| Test name (`tests/`) | Spec ref | Type | Expected result |
|---|---|---|---|
| `test_limits.py::test_nonnegative_integer_accepts_zero_and_ceiling_exactly` | FR-2, FR-10; AC-17 | unit | Zero and `2^31−1` remain exact. |
| `test_limits.py::test_nonnegative_integer_rejects_invalid_types_and_range` | FR-2, FR-5; AC-17; security | unit | Bool, float, text, negative, non-finite, and overflow reject with field details. |
| `test_limits.py::test_positive_threshold_rejects_zero_without_float_rounding` | FR-5; AC-06, AC-17 | unit | Exact `1,1,2,3,4` estimate; zero threshold rejects. |
| `test_validation.py::test_scheduling_shift_accepts_operating_bounds_and_adjacent_hours` | FR-3, FR-10; AC-07; compatibility | unit | Scheduling bounds accept; generic `shift_hours(0,1)` stays valid. |
| `test_validation.py::test_scheduling_shift_rejects_outside_or_noninteger_hours` | FR-3; AC-07; edge | unit | Out-of-range, equal, boolean, and fractional endpoints reject. |
| `test_csv_import.py::test_complete_zero_report_is_available_demand_with_112_cells` | FR-4, FR-5; edge | unit | All zero counts form complete, available demand. |
| `test_csv_import.py::test_friday_first_date_headers_normalize_to_monday_first` | FR-4; AC-03 | unit | Shuffled date headers map to correct weekdays; title warns. |
| `test_csv_import.py::test_supplied_report_friday_7am_count_normalizes_to_friday` | FR-4; AC-03 | unit | Supplied sample has Friday 07:00 count 22 after normalization. |
| `test_csv_import.py::test_recognized_totals_are_ignored_with_positioned_warnings` | FR-4; AC-05 | unit | Total row/column do not enter demand and have positioned warnings. |
| `test_csv_import.py::test_multiple_bad_cells_report_all_discoverable_positions` | FR-4; AC-04; failure | unit | Four distinct invalid cells all identify day/hour and source position. |
| `test_csv_import.py::test_duplicate_normalized_weekday_is_rejected` | FR-4; AC-05; edge | unit | `Mon` plus `Monday` is ambiguous and rejects. |
| `test_csv_import.py::test_bad_or_oversized_input_has_distinct_error` | FR-4; NFR security/error; abuse | unit | Oversized bytes, invalid UTF-8, and empty content have distinct failures. |
| `test_csv_import.py::test_weekly_transaction_total_overflow_is_rejected` | FR-4; AC-17; abuse | unit | Individually valid cells with oversized weekly sum reject. |
| `test_csv_import.py::test_csv_shape_caps_reject_rows_columns_and_long_cells` | FR-4; NFR security; abuse | unit | Row, column, and cell limits reject before storing demand. |
| `test_csv_import.py::test_unknown_or_duplicate_hour_is_rejected` | FR-4; AC-04–05; edge | unit | Outside-range or repeated hour labels reject with row. |
| `test_scheduling_service.py::test_new_schedule_defaults_and_second_schedule_are_independent` | FR-1, FR-10; AC-01 | integration | Two same-named schedules get independent defaults and empty state. |
| `test_scheduling_service.py::test_rename_keeps_stable_id_and_children_after_reopen` | FR-1; AC-01 | integration | Rename trims; ID and child staff survive reopen. |
| `test_scheduling_service.py::test_legacy_named_schedule_migrates_once_without_changing_its_id` | FR-10; NFR compatibility/reliability | integration | Old row and ID survive repeated migration; defaults added once. |
| `test_scheduling_service.py::test_duplicate_staff_names_use_ids_and_invalid_maximum_does_not_write` | FR-2; AC-02, AC-17 | integration | Same names have distinct IDs; bool maximum writes nothing. |
| `test_scheduling_service.py::test_manual_over_maximum_add_commits_numeric_warning_and_persists` | FR-2, FR-6; AC-08 | integration | `32+8=40` commits with exact excess and persistent warning. |
| `test_scheduling_service.py::test_lowering_staff_maximum_keeps_assignments_and_adds_warning` | FR-2; AC-02 | integration | Lowering to 4 keeps 8 assigned hours and warns excess 4. |
| `test_scheduling_service.py::test_overlap_rejects_atomically_but_adjacent_shift_warns_on_daily_limit` | FR-3, FR-6; AC-07 | integration | Overlap rejects without write; adjacent shift commits with warning. |
| `test_scheduling_service.py::test_used_shift_edit_checks_other_day_and_rolls_back_all_assignments` | FR-3, FR-6; AC-07 | integration | Overlap introduced on another day rejects whole edit. |
| `test_scheduling_service.py::test_reassignment_and_cross_schedule_reference_reject_without_loss` | FR-6, FR-10; AC-07; security | integration | Foreign employee ID cannot replace an assignment. |
| `test_scheduling_service.py::test_confirmed_staff_removal_deletes_dependents_and_cancel_does_nothing` | FR-2; AC-02 | integration | Cancel preserves state; confirm removes staff and assignments. |
| `test_scheduling_service.py::test_used_shift_removal_requires_confirmation_and_clears_dependents` | FR-3; AC-16 | integration | Cancel preserves used shift; confirm removes its assignments. |
| `test_scheduling_service.py::test_duplicate_shift_times_reject_without_changing_existing_shift` | FR-3, FR-6; AC-07 | integration | Existing time pair cannot be duplicated. |
| `test_scheduling_service.py::test_preimport_threshold_change_persists_without_demand_or_history` | FR-5, FR-8; AC-06 | integration | Setting changes directly before import and creates no history. |
| `test_scheduling_service.py::test_invalid_refresh_preview_preserves_demand_roster_and_history` | FR-4, FR-8; AC-04, AC-15 | integration | Bad re-import preview leaves freshly reread active and history equal. |
| `test_metrics.py::test_no_import_keeps_transaction_and_coverage_metrics_unavailable` | FR-4, FR-9; edge | integration | Missing demand yields undefined metrics. |
| `test_metrics.py::test_ratios_use_total_and_separate_unweighted_staffed_cell_average` | FR-9; AC-13–14 | integration | `114/8=14.25`, staffed-cell mean `14.5`, and excess is separate. |
| `test_metrics.py::test_all_unstaffed_ratios_undefined_and_coverage_zero` | FR-9; AC-13; edge | integration | No staff gives undefined ratios and zero coverage. |
| `test_metrics.py::test_removing_assignment_recomputes_exactly_covered_hours` | FR-6, FR-9; AC-09 | integration | Eight specific hourly buckets lose one scheduled hour. |
| `test_generation.py::test_generation_prerequisites_preserve_current_state` | FR-7; AC-18; failure | integration | Missing demand/shifts/eligible staff each has specific error; no write. |
| `test_generation.py::test_insufficient_capacity_commits_valid_partial_draft` | FR-7; AC-10–11 | integration | One 8-hour worker yields exact partial roster and 104 unmet hours. |
| `test_generation.py::test_equal_candidates_use_stable_employee_id_and_repeated_inputs_match` | FR-7; AC-12, AC-19 | integration | Stable IDs/day/shift order and preview reproduce draft. |
| `test_generation.py::test_generated_roster_obeys_reference_overlap_and_hour_invariants` | FR-7, FR-10; AC-10–11 | integration | Valid IDs, days, distinct assignments, maxima, and hour reconciliation. |
| `test_refresh.py::test_refresh_preview_and_cancel_leave_active_state_and_history_unchanged` | FR-8; AC-15 | integration | Preview/cancel is read-only with no snapshot. |
| `test_refresh.py::test_confirmed_refresh_captures_prior_analytics_and_replaces_roster_once` | FR-8, FR-10; AC-15 | integration | Exactly one prior-state snapshot and one coherent replacement. |
| `test_refresh.py::test_stale_preview_after_intervening_edit_rejects_without_snapshot` | FR-8; AC-15; concurrency | integration | Intervening rename invalidates preview; no refresh write. |
| `test_refresh.py::test_confirmed_threshold_change_snapshots_prior_settings_and_reuses_demand` | FR-5, FR-8; AC-06, AC-15 | integration | Threshold refresh retains demand and snapshots old setting/analytics. |
| `test_refresh.py::test_altered_proposal_cannot_reuse_preview_token` | FR-8; AC-15; security | integration | Changed proposal fails token binding without state/history write. |
| `test_refresh.py::test_two_previews_of_same_version_allow_only_first_confirmation` | FR-8; AC-15; concurrency | integration | Sequential competing clients: second confirmation is stale. |
| `test_refresh.py::test_snapshot_insert_failure_rolls_back_active_changes` | FR-8, FR-10; AC-15; failure | integration | Injected SQLite insert failure rolls back active rows and snapshot. |
| `test_refresh.py::test_standalone_regeneration_cancel_keeps_assignments_without_history` | FR-8; AC-15 | integration | Cancelled regeneration preserves manual roster, no history. |
| `test_refresh.py::test_snapshot_read_is_scoped_to_its_schedule` | FR-10; AC-15; security | integration | Another schedule cannot read a snapshot by ID. |

## Test data, fixtures, and mocks

- `week_csv` in `tests/scheduling_support.py` builds a complete synthetic 112-cell report with literal overrides. Tests vary weekday order, source labels, cell errors, and size/shape limits. It is test-only code; no existing fixture was changed.
- The supplied `data/sample_transaction_interview.csv` is read only for the Friday 07:00 normalization assertion. No customer data or sample contents are logged.
- Integration tests use pytest `tmp_path` for isolated SQLite files and create a new `ScheduleService` for rejected-state comparisons. A legacy one-table SQLite file is created inside `tmp_path` for migration. The concurrency case uses two service instances and a deterministic intervening commit; it does not depend on thread timing.
- No domain, service, clock, or database behavior is mocked. One test installs a SQLite `BEFORE INSERT` trigger in its temporary database to force a real storage failure at snapshot insertion. It asserts the rollback through a fresh service read.

## Spec items not covered in this first reviewable red suite

- The exact 3:1 versus 4:1 morning-shift policy example and every AC-19 tie dimension need a pinned pure generator API and a carefully isolated policy fixture. The current tests cover deterministic ID/day/shift order, partial drafts, and hard invariants, but do not claim full score/tie proof.
- CSV acceptance exactly at every size cap, all accepted time-label spellings, a missing-hour error distinct from an unknown hour, empty row/column warnings, and weekly **required-staff** aggregate overflow need further parser cases. The current tests cover above-cap rejection, date-labelled order, totals, duplicate labels, and transaction overflow.
- A confirmed shift-duration edit that only produces warnings, policy-limit changes with existing assignments, invalid snapshot JSON structure, token expiry across process restart, and standalone **confirmed** regeneration need further integration tests. Current tests cover the corresponding rejection/cancel/refresh paths.
- Full threaded/process races, crash interruption, and quantitative performance targets are not asserted here. The two-preview version test checks the required lost-update outcome without timing races. The approved plan calls for local import/metrics, 100-employee/32-shift pure generation, and confirmed-refresh benchmarks after implementation; no meaningful timing can be measured against absent feature code, and elapsed-time assertions would be machine dependent.
- Future UI behavior, file-path confinement for future path-based upload plumbing, authentication, publishing, restore/deletion, and payroll are outside the approved core backend scope. The importer contract accepts bytes, so there is no path input to exercise in this stage.

## Red-run result

Command: `.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider --basetemp=.test-tmp/pytest`, run with pytest's temporary SQLite directory accessible. Result: **63 failed, 14 passed**. The 14 pre-existing scaffold tests passed. No collection error, test typo, or fixture error appeared in this final run.

| Failing group | Count | First failure and why it is the intended red state |
|---|---:|---|
| `test_csv_import.py` | 15 | Missing planned `src.domain.csv_import` or the `SchedulingError` model used to assert structured rejection. |
| `test_generation.py` | 6 | Missing `ScheduleService.get_schedule` or `import_initial` used to arrange a draft case. |
| `test_limits.py` | 9 | Missing planned `src.domain.limits` and `src.domain.demand`. |
| `test_metrics.py` | 4 | Missing `ScheduleService.get_schedule` or `import_initial`. |
| `test_refresh.py` | 9 | Missing `ScheduleService.add_employee`, the first new operation needed for the refresh fixture. |
| `test_scheduling_service.py` | 14 | Missing `ScheduleService.get_schedule`, `add_employee`, or `set_threshold` at the first unimplemented step. |
| `test_validation.py` | 6 | Missing planned `src.domain.shifts`. |

These are assertion failures naming absent approved-plan modules or facade operations, so they are missing-feature failures rather than accidental import/collection failures. The downstream behavior assertions have **not yet executed**. Their API/field choices are proposed above and need review before the implementation stage; this red run cannot prove they will pass after implementation.
