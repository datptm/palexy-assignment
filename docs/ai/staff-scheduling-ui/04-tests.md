# Staff scheduling UI — Stage 4 tests and red run

**Task:** `staff-scheduling-ui`  
**Inputs:** approved [specification](01-spec.md), [design](02-design.md), and [plan](03-plan.md).  
**Scope:** tests only; no feature implementation. The literal `{{extra cases I want}}` supplied no additional cases.

## Executable contract for review

The tests follow the approved service signatures and propose concrete names for the new preview fields: `AssignmentOptionsPreview` has `schedule_id`, `baseline_version`, `day`, and employee-ID-sorted `options`; an option has `employee_id`, `blocked`, `findings`, `current_hours`, `projected_hours`, `weekly_max_hours`, `before_weekly`, and `after_weekly`. `ShiftEditPreview` has `schedule_id`, `baseline_version`, `affected_assignment_ids`, `old_duration`, `new_duration`, `findings`, and `projected_result` (`None` on a hard error). The three preview records are frozen dataclasses. These field names are a reviewable proposed API where the approved design specified values but did not fix names.

Page tests use NiceGUI's built-in simulator and accessible text/control names as their interaction contract. The proposed labels include `Create schedule`, `Staff`, `Shifts`, `Demand import`, `Hourly analysis`, `History`, `Auto-schedule`, and `Threshold`. The concrete presentation phrases in the tests express the required meanings. Review wording and control targeting before implementation if a different accessible label is preferred. Each page test uses the real `/` page and a temporary SQLite-backed `ScheduleService`.

## Test matrix

Each row is an executable test function; the stale-version row runs five parameter values. `AC-*` refers to Section 5 of [01-spec.md](01-spec.md). `NFR-*` are the topic aliases from [03-plan.md](03-plan.md).

| Test name | Spec ref | Type | Expected result |
|---|---|---|---|
| `test_manual_previews.py::test_preview_contract_records_are_frozen` | FR-13; AC-21–22 | unit | All three typed preview records exist and are immutable. |
| `test_manual_previews.py::test_assignment_options_preview_is_read_only_and_has_stable_ids` | FR-8, FR-13; AC-12 | integration | All choices use stable employee IDs; preview does not change state/version. |
| `test_manual_previews.py::test_assignment_options_preview_uses_one_state_read_for_all_staff` | FR-13; NFR-Performance | integration | Five choices require one schedule-state read. |
| `test_manual_previews.py::test_assignment_options_preview_blocks_overlap_but_allows_policy_warning` | FR-8, FR-13; AC-04, AC-12 | integration | Overlap blocks; adjacent daily/weekly limit warnings remain selectable; no write. |
| `test_manual_previews.py::test_assignment_options_preview_projects_numeric_overage_and_coverage` | FR-8–9, FR-13; AC-12 | integration | A fifth eight-hour shift shows 32→40 hours, limit 32, and coverage 32→40 before save. |
| `test_manual_previews.py::test_shift_preview_reports_impact_without_writing` | FR-4, FR-13; AC-21 | integration | Used-shift edit lists assignment ID, 8→9 hours and projected workload without writing. |
| `test_manual_previews.py::test_shift_preview_conflict_is_blocked_and_keeps_old_definition` | FR-4, FR-13; AC-04, AC-21 | integration | Overlap has an error and no projected result; old state stays intact. |
| `test_manual_previews.py::test_expected_version_rejects_stale_write_atomically` (five operations) | FR-4, FR-8, FR-12–13; AC-22; concurrency | integration | Add, reassign, edit shift, remove employee, and remove shift each reject a stale version and leave complete state unchanged. |
| `test_manual_previews.py::test_assignment_preview_rejects_foreign_employee_reference` | FR-12–13; NFR-Security | integration | A foreign replacement reference is rejected without reading or changing that schedule's roster. |
| `test_ui_session.py::test_selection_empty_page_creates_persisted_default_week` | FR-1–2; AC-01 | integration | Empty page offers creation; new week is selected and has default settings, no demand or roster. |
| `test_ui_session.py::test_selection_duplicate_names_are_distinguished_by_id` | FR-1; AC-01 | integration | Same-name schedule choices show IDs; selecting the second leaves both persisted. |
| `test_ui_session.py::test_selection_invalid_saved_id_falls_back_without_phantom_week` | FR-1, FR-12; AC-01; NFR-Security | integration | Invalid browser-stored ID falls back to the first persisted schedule; no phantom row. |
| `test_ui_session.py::test_action_boundary_rejected_edit_keeps_last_committed_view` | FR-3, FR-12; AC-02 | integration | Bad maximum shows a field error and leaves the committed result unchanged. |
| `test_ui_presentation.py::test_roster_shows_seven_editable_days_and_unassigned_shift_cells` | FR-2, FR-9; AC-01, AC-06 | integration | Weekdays, both actual default times, unassigned cells, and unavailable demand appear. |
| `test_ui_presentation.py::test_roster_displays_both_same_name_assignees_by_stable_id` | FR-2–3; AC-01–02 | integration | Both same-name assignees in one cell have distinguishable IDs. |
| `test_ui_presentation.py::test_analysis_distinguishes_missing_demand_from_imported_zero` | FR-5, FR-9; AC-06 | integration | Missing demand is unavailable; imported zero displays zero transactions and required one. |
| `test_ui_presentation.py::test_analysis_or_warning_shows_numeric_gap_and_overage` | FR-9–10; AC-14 | integration | Required two/scheduled three displays excess one, capped coverage, and over-max warning. |
| `test_ui_presentation.py::test_analysis_or_warning_labels_both_distinct_weekly_ratios` | FR-9; AC-13 | integration | Overall ratio 14.25 and staffed-cell average 14.5 have separate labels. |
| `test_ui_workflows.py::test_staff_edit_invalid_limit_preserves_input_and_same_name_id` | FR-3; AC-02; failure | integration | Invalid maximum reports a field error and does not edit the other same-name employee. |
| `test_ui_workflows.py::test_staff_removal_cancel_then_confirm_removes_dependents` | FR-3, FR-12; AC-03 | integration | Used employee shows assignment count; cancel is inert; confirm removes dependents. |
| `test_ui_workflows.py::test_shift_setting_rejects_invalid_limit_and_persists_valid_shift` | FR-4; AC-17; edge | integration | Zero daily limit rejects; valid 10:00–14:00 shift persists. |
| `test_ui_workflows.py::test_shift_edit_or_removal_conflict_and_cancel_keep_used_shift` | FR-4, FR-12–13; AC-04, AC-21 | integration | Conflict shows a reason without write; used-shift removal shows count and cancel is inert. |
| `test_ui_workflows.py::test_assignment_add_or_remove_updates_hours_without_reload` | FR-8–9; AC-11 | integration | Empty cell accepts manual edit before demand; eight hours appear and disappear on removal. |
| `test_ui_workflows.py::test_reassignment_stale_preview_preserves_original_assignment` | FR-8, FR-12–13; AC-18, AC-22; concurrency | integration | Intervening rename invalidates reviewed reassignment; original assignment remains. |
| `test_ui_workflows.py::test_import_invalid_upload_preserves_demand_and_roster` | FR-5, FR-12; AC-19; NFR-Security | integration | More than 1 MiB is rejected; active demand, roster, and history remain unchanged. |
| `test_ui_workflows.py::test_import_valid_report_shows_findings_then_commits_without_roster` | FR-5, FR-10; AC-05 | integration | Friday-first report normalizes, ignored totals warn, and initial import stores 112 cells without generation/history. |
| `test_ui_workflows.py::test_import_invalid_encoding_shows_error_and_keeps_existing_demand` | FR-5, FR-12; AC-19; NFR-Security | integration | Invalid UTF-8 is reported without replacing existing demand. |
| `test_ui_workflows.py::test_refresh_preview_cancel_preserves_manual_roster_and_history` | FR-6, FR-12; AC-07–08 | integration | Threshold replacement preview is read-only; cancel preserves manual roster/history. |
| `test_ui_workflows.py::test_refresh_preview_preimport_threshold_saves_without_history` | FR-6; AC-17 | integration | Before demand, threshold saves directly with no snapshot. |
| `test_ui_workflows.py::test_generation_missing_demand_shows_specific_prerequisite` | FR-7, FR-12; AC-09 | integration | Auto-schedule reports `MISSING_DEMAND` and writes nothing. |
| `test_ui_workflows.py::test_refresh_confirmation_uses_same_proposal_and_saves_prior_state` | FR-6, FR-11–12; AC-07 | integration | Confirmed threshold change replaces draft, creates one prior-state snapshot, and updates active setting. |
| `test_ui_workflows.py::test_generation_partial_draft_is_success_and_regeneration_cancel_is_inert` | FR-7, FR-12; AC-09–10 | integration | Eight-hour capacity yields 104 unmet hours; regeneration preview can be cancelled with no snapshot. |
| `test_ui_workflows.py::test_history_is_read_only_and_return_reloads_active_result` | FR-11–12; AC-15 | integration | Prior threshold is labelled historical/read-only; no restore control; returning shows current threshold. |

## Test data, fixtures, and mocks

- `tests/ui_support.py` opens the actual page through NiceGUI `user_simulation`, substitutes only the `ScheduleService` constructor's database path with a pytest `tmp_path` SQLite file, and disables NiceGUI's unused CPU process-pool startup for this simulator. The page callbacks, service methods, SQLite, and thread offload remain real. `sync_test` runs the simulator with `asyncio.run`; no async pytest plugin or new dependency is needed.
- Synthetic weeks are created through the real service. `tests/scheduling_support.py::week_csv` supplies full 112-cell CSV bytes and literal overrides, including Friday-first order, ignored totals, zero demand, invalid UTF-8, and more than 1 MiB input. No existing fixture or supplied sample file was changed.
- Concurrency is a deterministic intervening `rename_schedule` between review and save; it checks the lost-update outcome without timing-sensitive threads. The one-read case counts `load_state` calls but leaves the actual SQLite load in place.
- The upload tests pass `SmallFileUpload` to NiceGUI 3.18.0's `ui.upload.handle_uploads`, exercising its real upload callback. No file path or external server is used.

## Spec items not covered by these automated tests

- FR-1's actual cross-tab browser preference persistence, tab independence, and deleted-ID fallback beyond the simulated invalid-ID case need a real browser storage check. The simulator can replace a JavaScript response but does not persist real browser `localStorage` across browser processes.
- FR-2 and NFR-Accessibility's narrow-screen legibility, horizontal scrolling, keyboard navigation, and focus return require the plan's desktop/narrow manual browser pass; the simulator has no viewport or focus engine.
- FR-4's warning-only used-shift save and stale confirmed deletion, FR-8's successful atomic reassignment and over-limit warning after a committed manual add, and FR-13's complete affected-hour/per-person projected record fields need additional focused cases once the preview shape is approved. The current tests cover their hard-error, stale, and basic projection branches.
- FR-5/FR-10's full multi-finding malformed CSV report, positioned finding navigation, and all upload shape caps are covered in existing backend parser tests but are not all repeated through the page. This suite covers valid normalized/warning import and two high-risk upload failures.
- FR-6's CSV re-import, changed-payload/expired-token rejection, and injected storage rollback are covered by existing backend refresh tests but not yet by page interactions. This suite covers threshold preview/cancel/confirm and prior-state history.
- FR-7's missing-shifts/no-eligible-person messages, repeat-click busy guard, and confirmed regeneration are not exercised through the page. The approved backend generation tests cover the prerequisite and replacement service contracts.
- FR-9/FR-10's every-hour display count, warning-location navigation, zero-maximum `N/A`, and no invented violation codes need more presentation assertions. The existing backend metrics tests protect the numeric calculations; these page tests sample their high-risk distinctions.
- FR-11's cross-schedule snapshot isolation and FR-12's late asynchronous response, uncertain storage failure/reload, and successful error clearing are not yet page-tested. Existing backend tests cover snapshot ownership and atomic storage rollback; a controllable delayed UI action seam is needed for the late-response case.
- NFR-Performance's quantitative 1-second/10-second targets, memory behavior, and full 100-person UI responsiveness are local measurements rather than deterministic CI assertions. NFR-Security's text/HTML escaping and no-logging behavior, and NFR-Compatibility's actual browser rendering on each supported OS, require separate integration or manual checks. Authentication, publishing, payroll, export, and snapshot restore are outside this approved feature.

## Red-run result

Final command: `.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider`, run with writable temporary SQLite fixtures. Result: **37 failed, 81 passed, 3 skipped**. The three skips are existing opt-in local benchmarks. The first sandboxed run with `--basetemp=.test-tmp/stage4` could not clean its temp directory (`PermissionError`); the final run used the approved unsandboxed test process and had no fixture or collection errors.

| Failing group | Count | Confirmed reason |
|---|---:|---|
| Manual preview contracts and behavior | 8 | Missing planned preview dataclasses or `ScheduleService.preview_assignment_options` / `preview_shift_edit`. |
| Version-gated mutations | 5 | The five existing methods lack the approved `expected_version` parameter; tests report this explicitly before invoking them. |
| Page selection/session | 4 | The root page is still the scaffold; creation, stable-ID selection, and staff actions are absent. |
| Page presentation | 5 | The scaffold has no roster cells, selected-schedule data, analysis, or warnings. |
| Page workflows | 15 | The scaffold has no staff/shift/demand/generation/history controls or corresponding callbacks. |

Representative failures were inspected with a focused simulator run: `Create schedule`, `Alex #1`, and `Demand import` are missing from the actual rendered scaffold. Every new test now executes and fails at a missing planned API, version gate, or UI element. There are no import errors, unknown pytest marks, async-runner errors, fixture errors, or source typos in the final run. Downstream assertions after the first missing UI element will be exercised during implementation.

Additional gates: `.venv/Scripts/python.exe -m ruff check . --no-cache` passed; `.venv/Scripts/python.exe -m ruff format --check .` passed; `.venv/Scripts/python.exe -m compileall -q src ui tests main.py` passed. The pytest suite is intentionally red at this stage.
