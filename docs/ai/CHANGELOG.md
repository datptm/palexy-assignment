# Change log

## 2026-11-03 15:30 (UTC) - Add core scheduling red tests
- Task: `core-scheduling-logic` Stage 4 tests first
- Changes: Added a traceable test matrix, synthetic CSV helper, and red-stage tests for validation, import, service edits, metrics, generation, and refresh safety. Production code and existing fixtures were not changed.
- Files: `docs/ai/core-scheduling-logic/04-tests.md`, `tests/scheduling_support.py`, `tests/test_limits.py`, `tests/test_validation.py`, `tests/test_csv_import.py`, `tests/test_scheduling_service.py`, `tests/test_metrics.py`, `tests/test_generation.py`, `tests/test_refresh.py`
- Why: Lock down the approved `01-spec.md`, `02-design.md`, and `03-plan.md` contracts before feature implementation.
- Verification: Baseline pytest: 14 passed. Red-stage `.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider --basetemp=.test-tmp/pytest`: 63 failed for missing planned modules/service operations, 14 passed, with no collection or fixture errors. `pytest --collect-only`: 77 collected. `ruff check --no-cache .`: passed. `ruff format --check .`: 47 files formatted. `compileall -q src ui tests main.py`: passed. `git diff --check`: passed. Production behavior and performance benchmarks were not run because this is the tests-only stage.
- Risks / follow-ups: Proposed method signatures, result fields, and some error codes need manager review. Several specified edge, policy, and performance cases remain listed in `04-tests.md` for the implementation stage.

## 2026-11-03 16:03 (UTC) - Implement core scheduling backend
- Task: `core-scheduling-logic` Stage 5 implementation
- Status: partial
- Changes: Added typed scheduling results and strict domain rules; migrated SQLite storage for staff, shifts, demand, assignments, and immutable snapshots; added CSV import, metrics, deterministic generation, manual edits, signed previews, atomic refresh confirmation, and local performance scenarios. Updated the README backend status. Existing Stage 4 tests were not modified.
- Files: `src/model/scheduling.py`, `src/domain/limits.py`, `src/domain/shifts.py`, `src/domain/validation.py`, `src/domain/demand.py`, `src/domain/csv_import.py`, `src/domain/metrics.py`, `src/domain/generation.py`, `src/db/database.py`, `src/db/schedules.py`, `src/db/scheduling.py`, `src/db/history.py`, `src/services/schedules.py`, `src/services/scheduling.py`, `src/services/previews.py`, `tests/test_performance.py`, `README.md`, `docs/ai/CHANGELOG.md`
- Why: Implement the approved Stage 1–3 backend design while preserving the existing scaffold service and generic time helper.
- Verification: `.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider --basetemp=.test-tmp/stage5-final3`: 77 passed, 3 opt-in benchmarks skipped. Opt-in benchmark run: 3 passed; import plus metrics 0.0087s, pure generation with 100 employees/32 shifts 0.3754s, confirmed refresh 0.0963s on Windows 11 / Intel64 Family 6 Model 191. `.venv/Scripts/python.exe -m ruff check .`: passed. `.venv/Scripts/python.exe -m ruff format --check .`: 60 files formatted. `.venv/Scripts/python.exe -m compileall -q src ui tests main.py`: passed. `git diff --check`: passed. `git status --short`: only planned files plus a pre-existing modification to `03-plan.md`; no generated artifacts.
- Risks / follow-ups: The approved plan asks for additional requirement-specific tests beyond the prewritten Stage 4 suite, but the implementation request forbids modifying those tests. The exact score/tie dimensions, CSV at-cap acceptance, malformed snapshot structures, and standalone confirmed regeneration lack dedicated automated assertions. The NiceGUI page remains a scaffold.

## 2026-11-03 16:29 (UTC) - Add manual scheduling scripts
- Task: Add root `scripts/` tools for manual testing and scheduling actions.
- Changes: Added commands to create, list, and inspect schedules, add an employee, import a bounded CSV, and generate a draft. Existing-roster and re-import replacements show a preview and require an explicit flag. Added path confinement, usage documentation, and SQLite integration tests.
- Files: `scripts/__init__.py`, `scripts/_common.py`, `scripts/schedules.py`, `scripts/import_csv.py`, `scripts/generate.py`, `scripts/README.md`, `tests/test_scripts.py`, `README.md`, `docs/ai/CHANGELOG.md`
- Why: Let a manager exercise the backend and inspect actual schedule state while the NiceGUI page remains a scaffold.
- Verification: `.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider --basetemp=.test-tmp/scripts-full`: 81 passed, 3 opt-in performance benchmarks skipped. `.venv/Scripts/python.exe -m ruff check .`: passed. `.venv/Scripts/python.exe -m ruff format --check .`: 67 files formatted. `.venv/Scripts/python.exe -m compileall -q src ui tests scripts main.py`: passed. All three `python -m scripts.<command> --help` invocations passed. `git diff --check`: passed.
- Risks / follow-ups: The scripts expose selected actions; shift editing and assignment editing still require the service API. CSV files are accepted only inside `data/`.

## 2026-11-03 17:45 (UTC) - Add staff scheduling UI red tests
- Task: `staff-scheduling-ui` Stage 4 tests first
- Changes: Added the Stage 4 test matrix and red-run report; added read-only manual-preview, page session, presentation, and workflow tests with a NiceGUI simulator helper. Production code and existing fixtures were not changed.
- Files: `docs/ai/staff-scheduling-ui/04-tests.md`, `tests/ui_support.py`, `tests/test_manual_previews.py`, `tests/test_ui_session.py`, `tests/test_ui_presentation.py`, `tests/test_ui_workflows.py`, `docs/ai/CHANGELOG.md`
- Why: Make the approved `01-spec.md`, `02-design.md`, and `03-plan.md` observable before UI implementation.
- Verification: `.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider`: 37 expected feature failures, 81 passed, 3 opt-in benchmarks skipped; no collection or fixture errors. Ruff check with `--no-cache`, Ruff format check, and compileall all passed. A sandboxed pytest attempt could not clean its workspace temp directory; the final run used a writable test process. No implementation or browser visual check was run.
- Risks / follow-ups: Preview field names and accessible control wording are proposed test contracts for review. The untested cases and manual checks are listed in `04-tests.md`; tests are intentionally red until implementation.

## 2026-11-04 01:35 (UTC) - Implement staff scheduling UI
- Task: `staff-scheduling-ui` Stage 5 implementation
- Changes: Added frozen manual-edit preview records, read-only service projections, and atomic stale-version gates. Replaced the landing scaffold with schedule selection, a weekly roster, staff/shift/assignment editing, bounded CSV import, generation and refresh confirmations, coverage diagnostics, and read-only history. With manager approval, updated UI tests to await asynchronous commit results; added tests for version zero, reassignment impact, schedule isolation, stale previews, and browser fields. Updated setup documentation.
- Files: `src/model/scheduling.py`, `src/services/schedules.py`, `ui/app.py`, `ui/session.py`, `ui/presentation.py`, `ui/roster.py`, `ui/staff_panel.py`, `ui/shift_panel.py`, `ui/demand_panel.py`, `ui/analysis_panel.py`, `ui/history_panel.py`, `tests/test_app.py`, `tests/test_manual_previews.py`, `tests/test_ui_session.py`, `tests/test_ui_workflows.py`, `tests/test_ui_presentation.py`, `README.md`, `docs/ai/CHANGELOG.md`
- Why: Implement the approved `docs/ai/staff-scheduling-ui/03-plan.md` and preserve the approved asynchronous busy/commit behavior.
- Verification: `.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider`: 129 passed, 3 opt-in benchmarks skipped. `ruff check .`, `ruff format --check .`, `compileall -q src ui tests main.py`, and `git diff --check`: passed. Opt-in benchmarks: 3 passed; import+metrics 0.0042s, 100-employee/32-shift generation 0.3792s, confirmed refresh 0.0145s. One 100-employee choice preview took 0.1076s. Local app returned HTTP 200; desktop and narrow Chrome screenshots were inspected; Chrome keyboard Enter reached the roster editor, staff, analysis, history, and active view.
- Risks / follow-ups: Browser `localStorage` persistence across real tabs and behavior on macOS/Linux were not manually verified. The page's synchronous refresh uses a NiceGUI 3.18.0 internal method; review it when upgrading NiceGUI.

## 2026-11-04 02:30 (UTC) - Restyle staff roster dashboard
- Task: Rework the UI to follow the design pillars and supplied main-screen reference.
- Changes: Added a calm dashboard shell, compact coverage and workload metrics, a seven-day shift grid, employee capacity indicators, a required-versus-scheduled chart, and semantic warning/shortage styling. Kept schedule actions and service behavior intact; added a presentation regression test.
- Files: `ui/app.py`, `ui/roster.py`, `ui/analysis_panel.py`, `tests/test_ui_presentation.py`, `docs/ai/CHANGELOG.md`
- Why: Make the weekly roster the main workspace and clarify demand, staffing, capacity, and warnings in line with `docs/resources/design-pillars.md`.
- Verification: `.venv/Scripts/python.exe -m pytest -q --tb=short`: 130 passed, 3 opt-in benchmarks skipped. `ruff check .`, `ruff format --check .`, `compileall -q src ui tests main.py`, and `git diff --check`: passed. A synthetic-data local preview returned HTTP 200 and desktop screenshots were visually inspected; the preview server and temporary database were cleaned up.
- Risks / follow-ups: Narrow viewport behavior was not manually inspected; the roster uses horizontal scrolling on constrained widths.

## 2026-11-04 03:21 (UTC) - Move roster workspaces into dialogs
- Task: Place assignment removal on calendar badges and show workspace screens in dialogs.
- Changes: Replaced calendar removal text actions with accessible × buttons on assignee badges; moved cell editing, regeneration review, and staff/shift/demand/analysis/warning/history workspaces into dialogs; moved employee capacity into the Staff dialog and workspace navigation above the roster. Added UI interaction assertions and updated the read-only history test for the modal layout.
- Files: `ui/app.py`, `ui/roster.py`, `tests/test_ui_presentation.py`, `tests/test_ui_workflows.py`, `docs/ai/CHANGELOG.md`
- Why: Match the supplied tab workspace reference while keeping the main roster and chart uncluttered.
- Verification: `.venv/Scripts/python.exe -m pytest -q --tb=short`: 131 passed, 3 opt-in benchmarks skipped. `ruff check .`, `ruff format --check .`, `compileall -q src ui tests main.py`, and `git diff --check`: passed.
- Risks / follow-ups: Narrow-screen modal sizing was not manually inspected; workspace dialogs cap their width and height and scroll their content.

## 2026-11-04 03:40 (UTC) - Redesign scheduling workspace dialogs
- Task: Redesign each tab workspace dialog to follow `docs/resources/tab-screens.png`.
- Changes: Added a shared wide dialog shell; removed the duplicate in-dialog tab row so the main navigation opens each workspace directly. Restyled Staff and Shifts as paired form/list cards, Demand as a bounded upload and data preview, Analysis as summary/chart/hourly table, Warnings as severity cards, and History as a read-only timeline and detail view. Added workspace presentation and dialog-navigation assertions.
- Files: `ui/app.py`, `ui/staff_panel.py`, `ui/shift_panel.py`, `ui/demand_panel.py`, `ui/analysis_panel.py`, `ui/history_panel.py`, `tests/test_ui_presentation.py`, `docs/ai/CHANGELOG.md`
- Why: Match the supplied workspace-screen design while preserving the existing scheduling workflows and read-only history contract.
- Verification: `.venv/Scripts/python.exe -m pytest -q --tb=short`: 132 passed, 3 opt-in benchmarks skipped. `ruff check .`, `ruff format --check .`, `compileall -q src ui tests main.py`, and `git diff --check`: passed. Desktop browser layouts for all six workspaces were visually inspected; focused UI tests confirm the duplicate dialog navigation is absent.
- Risks / follow-ups: Narrow viewport layout was not manually inspected; responsive single-column rules are in place.

## 2026-11-04 04:35 (UTC) - Add scheduling algorithm v2 red tests
- Task: `scheduling-algorithm-v2` Stage 4 tests first
- Changes: Added a spec-traceable matrix and pure algorithm, service lifecycle, and NiceGUI tests for the approved Tiers A/B. Existing fixtures and production code were not changed.
- Files: `docs/ai/scheduling-algorithm-v2/04-tests.md`, `tests/test_generation_v2.py`, `tests/test_scheduling_algorithm_v2_service.py`, `tests/test_scheduling_algorithm_v2_ui.py`, `docs/ai/CHANGELOG.md`
- Why: Lock down the approved specification/design/plan behavior before implementing algorithm v2.
- Verification: Full pytest: 48 expected feature failures, 136 passed, 3 opt-in benchmarks skipped; no import, fixture, syntax, or collection errors. Ruff check, Ruff format check, compileall, and `git diff --check` passed. No implementation or performance benchmark run.
- Risks / follow-ups: The domain function/record names and the diagnostic UI labels are proposed test contracts for review; the chosen deterministic resource-work budget remains an implementation-stage decision.
