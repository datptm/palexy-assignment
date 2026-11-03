# Staff scheduling UI — Stage 1 specification

**Task:** `staff-scheduling-ui`  
**Status:** Refined for manager review; no implementation in this stage.  
**Authority:** [Staff Scheduling System BRD](../../resources/Staff_Scheduling_System_BRD.md), especially BR-01–BR-10 and Sections 6–7; [take-home brief](../../resources/SWE_Take-Home_Staff_Scheduling_System.pdf); [approved scheduling spec](../core-scheduling-logic/01-spec.md) and [design](../core-scheduling-logic/02-design.md). Where the BRD's re-import/threshold wording differs, the approved scheduling spec and implemented `ScheduleService` control. The current `ui/app.py` is only a landing scaffold.

## 1. Goal and non-goals

Give a store manager one usable local browser workflow for creating and selecting a typical Monday–Sunday schedule; maintaining staff, shifts, and settings; validating and importing demand; generating and safely replacing a draft; editing assignments directly; and reviewing current coverage, workload, and warnings. The roster is the primary view. UI actions call `ScheduleService` in `src/services/schedules.py`, and render its `ScheduleResult`, `Preview`, `ParsedDemand`, `Violation`, and `SchedulingError` values. Stable IDs, not display names or grid positions, identify records.

This stage specifies the UI and the read-only service preview API it needs. The first UI implementation includes that API and read-only history. It does not change scheduling policy, generation, persistence, authentication, deployment, publication, forecasting, payroll, breaks, availability, skills, exports, drag-and-drop, snapshot restore, or source documents. A draft remains editable; there is no publish step.

## 2. Functional requirements

### FR-1 — Schedule selection and creation (BR-01)

1. On opening `/`, list persisted schedules and show the selected schedule's name. If none exist, show a create-schedule call to action; a new schedule can be created before staff or demand exists. In this browser, reopen the most recently selected schedule by saved ID if it still exists; otherwise select the first schedule returned by `list_schedules` (creation order). The manager can switch schedules at any time. Creating or switching saves the selected ID in browser-scoped storage, loads its current result, and clears transient editors and previews from the prior selection.
2. Create and rename use `create_schedule` and `rename_schedule`. Names may repeat; options remain distinguishable by stable ID. Show field errors for blank or overlong names. A newly created week shows Monday–Sunday, 07:00–23:00, default shifts 07:00–15:00 and 15:00–23:00, threshold 20, daily limit 1, empty staff/demand/roster.
3. Reopening the app or switching back to a schedule shows persisted state from `get_schedule`, not a browser-only copy. A missing or invalid saved ID is ignored and replaced by the fallback selection; it never creates a phantom schedule or exposes another schedule's pending preview.

### FR-2 — Roster-first page and navigation (BR-07; BRD 6.1–6.2)

1. Keep the selected schedule, import state, threshold, daily shift limit, draft/empty status, and Auto-schedule action visible near the top. Show weekly coverage, unmet staff-hours, scheduled staff-hours, and warning count when those values exist.
2. The main roster is one Monday–Sunday grid with configured shifts as rows, ordered by actual start/end time. Each day/shift cell shows the actual time range and assigned employee names, or an explicit unassigned state, and is directly editable. The manager can identify everyone on any shift without visiting separate day pages.
3. Staff, shifts, demand import, hourly analysis, warnings, and read-only history remain reachable from the selected schedule without losing roster context. The layout may use panels/tabs and horizontal scrolling on narrow screens; names and controls must remain readable.

### FR-3 — Staff maintenance (BR-02)

1. Add and edit an employee's name and whole-number weekly maximum through `add_employee`/`edit_employee`; zero is accepted. Show service validation errors next to the input and preserve entered values for correction.
2. Show each employee's assigned/max hours and utilization from `ScheduleResult.employees`. Distinguish duplicate names in pickers and lists using an ID suffix or another stable visible identifier. Show zero assigned hours explicitly, zero-maximum utilization as `N/A`, and an over-maximum warning with exact excess.
3. Removing an employee with assignments requires a confirmation identifying the employee and the count of affected assignments. Cancel does nothing; confirm calls `remove_employee(..., confirmed=True)` and refreshes the full result. An unassigned employee can be removed through the same deliberate control without implying roster impact.

### FR-4 — Shift definitions and daily limit (BR-04)

1. Display and edit start/end as whole-hour times in 07:00–23:00. Add, edit, and remove through the corresponding shift service methods. Display each shift by times, including overlapping definitions; use ID to distinguish records. Show service errors for invalid, duplicate, or conflict-causing edits.
2. Before editing a used shift, use the read-only preview in FR-13 to show affected days, employees, assignment count, duration/hour changes, projected coverage and workload, and all blocking errors or policy warnings. An overlap or duplicate disables Save with a reason; a policy-only warning permits Save. After saving, show the committed result. If the service rejects a changed/stale proposal, preserve the old shift and require a fresh preview.
3. Before removing a used shift, show the number of assignments that will be removed and require confirmation. Cancel preserves state; confirm calls `remove_shift(..., confirmed=True)`. A schedule with no shifts remains editable and explains why generation cannot proceed.
4. Show and edit the positive whole-number daily shift limit via `set_daily_shift_limit`. Lowering it does not remove assignments; show current over-limit warnings returned by the service.

### FR-5 — Demand upload, validation, and initial import (BR-03)

1. Offer a CSV file picker with concise sample-format guidance: one hour column, seven English weekday columns in any order, 07:00–22:00 bucket starts, and 112 day/hour counts. Read uploaded bytes and pass them to `validate_import`; do not infer file validity from its name or parse scheduling data in the UI.
2. Before committing, show the normalized Monday–Sunday demand preview and all parser findings, with severity and row/column or day/hour where available. A validation error blocks import. Accepted ignored totals/title/empty material appears as warnings, never as transaction demand. A zero count is displayed as `0`; absent demand is labelled unavailable.
3. For a schedule with no demand, commit the validated bytes through `import_initial`. Show success, retained import warnings, and updated required staffing; do not claim a roster was generated. If the service rejects the import, retain the previous displayed and persisted result and show the error.

### FR-6 — Demand re-import and threshold settings (BR-03, BR-05; approved backend override)

1. Display active threshold `N` as the number of transactions per required employee-hour, with the open-hour minimum of one explained briefly. Accept positive whole-number input. Before the first import, save via `set_threshold` without generation or history.
2. With demand already present, a proposed new CSV is validated, then sent to `preview_refresh(csv_bytes=...)`; a threshold proposal goes to `preview_refresh(threshold=...)`. Show the proposed demand/setting, draft roster and coverage, current versus proposed assignment counts, and a clear statement that confirmation replaces **all** current assignments, including manual edits, while saving the prior complete state in read-only history. Do not describe re-import as keeping assignments.
3. Cancel performs no write. Confirm passes the same CSV bytes or threshold and preview token to `confirm_refresh(..., confirmed=True)`. Replace the displayed result with the committed response only on success. A stale, invalid, expired, or mismatched preview requires a fresh preview; do not retry confirmation with a new proposal silently.

### FR-7 — Draft generation and safe regeneration (BR-06, BR-09)

1. Auto-schedule uses `generate` when the roster is empty. For a nonempty roster, call `preview_generation`, then show the proposed draft, coverage, removed/added assignment counts, and explicit replacement confirmation. Cancel keeps the current roster; confirm calls `confirm_generation(..., confirmed=True)` with the signed token. Standalone regeneration changes assignments only and creates no history snapshot.
2. Missing demand, no shifts, or no eligible employee is explained using the service's specific prerequisite error. A valid partial draft is success: show its roster and remaining shortages without labelling generation a failure. The UI must not promise full coverage or fairness that the service did not achieve.
3. While generation or confirmation is running, show progress/busy feedback and prevent accidental repeat submission. Only a committed `ScheduleResult` becomes the active view.

### FR-8 — Direct assignment editing (BR-08; BRD 6.4, 7)

1. Selecting a day/shift cell opens a nearby control with current assignees and employee choices labelled with assigned/max weekly hours; provide add, remove, and reassign actions. Use FR-13's service preview to show each choice's eligibility. Disable hard-rule choices with a readable reason; keep policy-warning choices selectable and show projected hours/shift-count and limit before Save. Reassign is one call to `reassign_assignment`, not a remove followed by an add. Each operation passes schedule, employee, shift, day, or assignment IDs to the matching service method.
2. Hard-rule rejection, including duplicate, overlap, or invalid reference, leaves the displayed roster unchanged and shows the service reason at the editing point. A weekly-maximum or daily-limit warning does **not** block a committed manual edit; show it before confirmation of the choice and immediately after commit beside the affected employee/cell and in the warning list. For an over-maximum add, show before + added = after hours and limit; persistent warning displays use assigned/max and excess.
3. After each successful edit, replace all roster, employee-hour, hourly, weekly, and warning views from the returned `ScheduleResult` without a browser reload. Keep focus near the edited cell. An empty cell remains editable; manual assignment can be attempted before demand import, but demand-dependent metrics remain unavailable.

### FR-9 — Current coverage, workload, and diagnostics (BR-05, BR-10; BRD 6–7)

1. Show a Monday–Sunday by hour analysis for all 07:00–22:00 starts. Each bucket displays transactions, required staff, scheduled staff-hours, transactions per staff-hour, and shortage/excess or covered status using `ScheduleResult.hourly`. Display the numeric gap and hour; use text as well as color. An unstaffed ratio is `–`.
2. Show from `ScheduleResult.weekly`: total scheduled staff-hours, total transactions, required and covered staff-hours, coverage percentage, unmet and excess staff-hours, **overall** transactions per staff-hour, and **arithmetic average over staffed cells** as separately labelled values. Ratios are formatted consistently from unrounded service values. When demand is unavailable, transaction/required/coverage values are `–` or “Import demand to see coverage,” rather than `0`.
3. Show employee hours/utilization from `ScheduleResult.employees`; zero-max utilization is `N/A`, and values above 100% retain their warning. Shortages and excess are diagnostics, not blocked states. Clearly distinguish required from actual and shortage from excess.

### FR-10 — Warnings and import findings (BR-03, BR-08, BR-10; BRD 6.3)

1. Present all current service warnings, including weekly max, daily limit, and accepted import warnings, in a persistent schedule-level list with context (person, day, hour, count, or source position as available). Provide a link or control to locate affected roster/analysis content. Do not invent `LOW_UTILIZATION`, `UNDERSTAFFED`, or `OVERSTAFFED` violation codes: derive coverage labels from hourly metrics and show workload values without asserting a backend warning.
2. Show import validation findings as one report, including every finding returned by the parser, and distinguish errors from accepted warnings. Show an action-specific error near its control as well as a non-blocking notification when useful. Clear stale transient errors after a successful retry; persist warnings until the service result no longer contains them.

### FR-11 — Read-only prior-state history in the first UI implementation (approved scheduling spec FR-8/FR-10)

1. List snapshots for the selected schedule using `list_snapshots`, with capture time, reason (`DEMAND_REIMPORT` or `THRESHOLD_CHANGE`), and prior version. `get_snapshot` opens its captured roster, settings, demand, warnings, and analytics clearly labelled **historical/read-only**.
2. Returning to the active view restores the current `get_schedule` result. No restore, delete, or editing control is offered for snapshots; standalone regeneration does not add a snapshot.

### FR-12 — UI state integrity and errors (all BRs; BRD Section 7)

1. Every action is scoped to the currently selected schedule. Switching schedules, closing a proposal, or changing proposed input invalidates the UI's pending preview. Keep the exact proposed CSV bytes or threshold and token together until confirmation; never send a different proposal with an old token.
2. A cancelled, rejected, or failed operation leaves active views on the last committed result; reload with `get_schedule` when the in-memory view may be stale. Show `SchedulingError.code`, message, findings, and relevant structured details in manager-readable terms; never display a raw traceback. A stale preview prompts fresh review. A storage or unexpected failure shows a recoverable error and offers reload, without claiming success.
3. Do not optimistically show a mutation as saved before its service call completes. Prevent duplicate submissions; successful actions render the service response as one coherent version. No manual page refresh is required for ordinary edits.

### FR-13 — Read-only manual-edit preview service API (BR-04, BR-08; BRD 6.4, 7)

1. Add `preview_assignment_options(schedule_id, day, shift_id, *, replacing_assignment_id=None)` for all employee choices at a target cell, including one-action reassignment, and `preview_shift_edit(schedule_id, shift_id, start_hour, end_hour)` for a proposed shift-definition edit. These operations read the current schedule and reuse its existing boundary checks, whole-state validator, and metric calculator. They never write or increment the schedule version. No scheduling rule or severity changes.
2. Each preview identifies its schedule and baseline version. For each employee choice, return the stable employee ID, whether any hard error blocks the edit, every error/warning with code, severity, message, and details, plus current and projected assigned hours, daily shift count, limits, and affected-hour/weekly coverage changes when allowed. The shift preview returns affected assignment IDs, people/days, old/new duration, all findings, and projected roster/coverage/workload when the proposal has no hard error. A hard-error proposal needs no projected metrics.
3. The UI must use the preview returned by the service, not duplicate eligibility or warning calculations. `add_assignment`, `reassign_assignment`, and `edit_shift` accept an optional `expected_version` from the preview and check it inside their write transaction; if intervening work changed the schedule, reject with `STALE_PREVIEW` and commit nothing. Existing callers without this argument retain their current behavior. The UI then reloads and previews again.

## 3. Non-functional requirements

- **Performance:** Keep roster and hourly views responsive for a 112-cell week. Fetch employee-choice previews in one service read per target cell rather than one database read per employee. Show busy feedback for generation and refresh; avoid rendering all 112 detailed cells in the primary roster. Existing backend acceptance targets are valid import/metrics within 1 second and a 100-employee/32-shift generation within 10 seconds on a local machine; the UI should add no avoidable repeated service calls or full-page reloads. Treat those as targets to measure, not proven current latency.
- **Security:** Treat browser fields, browser-stored schedule IDs, upload bytes, and preview versions/tokens as untrusted. Use NiceGUI's text/value APIs rather than interpolating user content into HTML. Never execute uploaded content or accept an arbitrary browser file path as a server path. Apply the backend's 1 MiB CSV cap before/while reading and surface its 256-row, 32-column, 4,096-character-cell, UTF-8, and `2^31 − 1` range failures. Server validation remains authoritative; UI validation is guidance only. Do not log uploaded contents or customer data. Bind only to `127.0.0.1:8765`; no authentication is implied.
- **Reliability:** Render active state only from committed service results. Preserve current state across validation errors, cancellation, stale previews, and failed atomic writes; re-read after uncertain failures. Distinguish a truly absent demand report from an imported all-zero report. Keep snapshot views separate from editable active state.
- **Accessibility and clarity:** Labels, numeric values, focus handling, and textual statuses carry meaning without color alone. Keyboard users can reach roster cells, dialogs, pickers, confirmation, and analysis. Long names and many shifts remain legible through wrapping or accessible scrolling. Use Monday–Sunday ordering and explicit 24-hour time ranges consistently.
- **Compatibility:** Python 3.10+, NiceGUI 3.18.0, local SQLite through existing services, UI code under `ui/`, no new dependencies, and the existing `main.py` entry point.

## 4. Edge cases and failure behavior

| Case | UI behavior |
|---|---|
| No schedules, no staff, no shifts, or no demand | Guided next action; roster remains a valid empty week; absent demand is unavailable rather than zero. Explain the specific generation prerequisite. |
| Valid imported all-zero report | Show 112 zero transaction cells and required staffing of one per open hour, as returned by the service. |
| Duplicate employee or schedule names | Display a stable identifier in selections; edit/delete the chosen ID only. |
| Saved browser selection is missing, invalid, or no longer in the schedule list | Fall back to the first schedule in creation order, or the create state if none exist; replace the stored ID. The manager can still switch freely. |
| Bad CSV, oversized file, unsupported encoding, or overflow | Show all available positioned findings or the specific limit/encoding error. Keep prior demand, roster, metrics, and history visible and unchanged. |
| Import warnings only | Allow import; show ignored items before and after commit. |
| No eligible employee versus insufficient total capacity | First is a prerequisite failure with no replacement; second is a committed partial draft with visible shortages. |
| Manual overlap/duplicate versus policy breach | Service preview disables a hard-error choice and explains why; weekly/daily policy breach remains selectable with a numeric pre-action notice, then commits and remains visible. Adjacent shifts may trigger a daily-limit warning without overlap. |
| Used staff/shift deletion or used-shift edit | Show affected assignments before destructive action and service-previewed impact for a shift edit. Cancel changes nothing; a rejected edit leaves existing shift/assignments intact; confirmed deletion updates hours/coverage. |
| Another tab changes the schedule after an edit preview | The version-checked mutation rejects atomically; reload current state and require a fresh preview before saving. |
| Re-import, post-import threshold edit, or nonempty-roster regeneration | Preview replacement and require explicit confirmation. Cancellation changes nothing. Refresh creates a prior-state snapshot; standalone regeneration does not. |
| Schedule changes between preview and confirmation, app restart, or proposal changes | Treat preview as stale/invalid, retain current state, and require a new preview; do not silently overwrite edits. |
| No scheduled staff | Show scheduled hours `0`, coverage `0%` when demand exists, and `–` for undefined transaction ratios. |
| Read/storage failure | Keep the last known committed view labelled as needing reload; show a recoverable message and do not show a false success. |

## 5. Acceptance criteria

Each criterion is a UI interaction test against a temporary SQLite database and real `ScheduleService` behavior unless marked as a visual/keyboard check. Assert both visible results and persisted state after cancellation or failure.

| ID / mapping | Given / When / Then |
|---|---|
| AC-01 · FR-1, FR-2 | Given no schedules, when a manager creates one, then it becomes selected and shows default shifts/settings and an empty Monday–Sunday week. Given two same-name schedules, switching keeps their data separate; reopening in that browser selects the last used ID, a second browser may retain a different selection, and a missing saved ID falls back to the first available schedule. |
| AC-02 · FR-3 | Given two employees with the same name, when editing one, then only its ID changes; invalid hours show a field error and write nothing; lowering a maximum retains assignments and shows exact overage. |
| AC-03 · FR-3, FR-4 | Given an assigned employee or used shift, when removal is cancelled, then persisted assignments/metrics are unchanged; on confirmation, dependent assignments disappear and the updated result is visible. |
| AC-04 · FR-4, FR-8, FR-13 | Given overlapping shift definitions, when a used shift edit or person assignment would make that person's shifts overlap, then its read-only preview reports the hard error, disables Save/selection with a reason, and leaves old state unchanged; an adjacent second shift remains selectable with a projected daily-limit warning. |
| AC-05 · FR-5, FR-10 | Given the supplied Friday-first CSV with ignorable totals/title rows, when uploaded, then the preview is Monday-first, warnings have positions, and initial import stores 112 cells but no roster; a malformed copy shows all discoverable errors and commits nothing. |
| AC-06 · FR-5, FR-9 | Given no demand versus an imported all-zero report, when viewing analysis, then the former shows unavailable demand and the latter shows zero transactions with required staff 1 in each open hour. |
| AC-07 · FR-6, FR-11 | Given demand and manually edited assignments, when a valid re-import or threshold change is previewed then cancelled, then active state/history are unchanged; when confirmed, the new draft/metrics appear and a read-only snapshot shows the prior state. |
| AC-08 · FR-6, FR-12 | Given a preview followed by an intervening schedule edit or changed proposal, when confirmation is attempted, then no replacement occurs, the stale/invalid error is shown, and the manager is asked to preview again. |
| AC-09 · FR-7 | Given complete demand and eligible staff but insufficient capacity, when Auto-schedule runs on an empty roster, then a partial draft appears with numeric shortages; given no demand, shifts, or eligible person, then the specific prerequisite appears and no roster changes. |
| AC-10 · FR-7, FR-12 | Given a nonempty manually edited roster, when Auto-schedule is clicked, then a replacement preview shows counts and draft; cancel preserves assignments, while confirmation replaces them and does not create a history snapshot. |
| AC-11 · FR-8, FR-9 | Given an assigned 07:00–15:00 shift, when it is removed, then the employee loses eight hours and only its eight covered bucket counts change; roster and weekly summary update without browser reload. |
| AC-12 · FR-8, FR-10, FR-13 | Given 32/32 assigned hours, when an 8-hour manual assignment is previewed, then it remains selectable and shows `32 + 8 = 40 h`, limit `32 h`, and affected-hour coverage changes; on Save it commits and retains the `+8 h` warning. An overlapping choice is disabled with its reason and changes no state. |
| AC-13 · FR-9, FR-10 | Given staffed cells `(33,3)`, `(48,3)`, `(33,2)`, when the summary is shown, then total transactions are 114, staff-hours 8, overall ratio 14.25 before display rounding, and staffed-cell average 14.5; an unstaffed ratio is `–`. |
| AC-14 · FR-2, FR-9, FR-10 | Given required 2 and scheduled 3 in an hour, when analysis is shown, then it says excess 1 and covered 2; coverage does not exceed 100%; the warning and roster remain readable with text alone. |
| AC-15 · FR-11, FR-12 | Given a selected schedule and a historical snapshot, when the manager opens history, then the prior state is labelled read-only and scoped to that schedule; returning shows current state, and no snapshot editing/restoring control exists. |
| AC-16 · FR-2, FR-8, FR-9, FR-12 | Given a desktop and a narrow viewport, when a keyboard user selects a roster cell, edits an assignment, and opens hourly detail, then names, times, focus, action status, and updated metrics remain reachable and legible without a page reload. Visual/keyboard check. |
| AC-17 · FR-1, FR-4, FR-6 | Given a selected schedule before import, when it is renamed, a 10:00–14:00 shift is added, and the threshold/daily limit are changed, then the new values persist after reopening, the new shift appears on all seven days, and no roster or history is created. Invalid or duplicate shift times and nonpositive settings save nothing. |
| AC-18 · FR-4, FR-8, FR-12 | Given two assigned people, when one assignment is moved to another employee/day/shift, then one service reassignment commits and both views update; if the destination overlaps, the original assignment and all metrics remain unchanged. |
| AC-19 · FR-5, FR-10, FR-12 | Given valid existing demand and a file exceeding 1 MiB or with an invalid encoding, when uploaded, then the distinct limit/encoding error appears and existing demand, roster, metrics, and history remain unchanged. |
| AC-20 · FR-6, FR-7, FR-12 | Given a preview and a simulated storage failure during confirmation, when the action fails, then the UI does not claim success; a fresh read shows the prior complete state and no new history entry. |
| AC-21 · FR-4, FR-8, FR-13 | Given a used shift and a proposed time change, when previewed, then the service returns affected people/days, duration, warnings, and projected metrics without changing the schedule/version; a conflicting change returns a blocking finding. The UI shows these before Save and renders the committed result after Save. |
| AC-22 · FR-8, FR-12, FR-13 | Given employee-choice and used-shift previews, when another tab edits the schedule before Save, then `expected_version` makes add/reassign/shift-edit reject with `STALE_PREVIEW`, leaves both changes atomic, and the UI refreshes the choices/impact. Existing service callers without `expected_version` still work. |

## 6. Assumptions

1. The approved core scheduling spec's confirmed-refresh decision supersedes BRD BR-03, BR-05, D-10, INV-15, and AT-18/19. The implemented service has separate first-import and refresh paths, signed process-local preview tokens, and read-only snapshots; this UI follows those paths exactly.
2. The selected schedule ID is stored in that browser across visits. It is not shared through SQLite and does not alter schedule data. The UI checks it against `list_schedules`, falls back to the first schedule in creation order when needed, and always reloads the selected result from the service. Creating or switching schedules updates this browser preference.
3. “Draft” means an editable current roster, including a partial one; there is no backend publication flag. “Empty” means no assignments, even when demand exists.
4. The first UI implementation adds the FR-13 service preview API because current `ScheduleService` offers preview only for generation and refresh. The new operations reuse existing domain rules, return projected effects without writing, and add optional version checks to the three affected mutations; existing mutation callers remain compatible.
5. The UI may format percentages and ratios but never recalculates staffing demand, generation, coverage, or violation severity. The first UI implementation includes a read-only history panel; a snapshot has no restore action.

## 7. Open questions for manager review

None remaining for this stage. The manager approved service-backed manual-edit previews, read-only history in the first UI implementation, and remembering the most recently used schedule per browser; these decisions are incorporated above.
