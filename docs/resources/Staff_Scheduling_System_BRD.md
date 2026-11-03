# Staff Scheduling System — Business Requirements Document

**Document status:** Implementation-ready baseline  
**Version:** 1.0  
**Source:** *Software Engineer Take-Home Assignment — Staff Scheduling System*, v1.1, 29 October 2026  
**Purpose:** Single source of truth for product behavior, business rules, scheduling decisions, user experience, and acceptance testing.  
**Scope:** A single-store, single-manager application for constructing a reusable, typical Monday–Sunday staff roster from hourly historical transaction demand.

> **Reading convention**
>
> - **[SOURCE]** is explicitly required or described in the assignment.
> - **[DECISION]** is a proposed product rule adopted by this BRD to resolve ambiguity and make behavior testable. It is not a claim about the assignment's original wording.
> - **[OPTIONAL]** is a desirable enhancement, not required for the baseline.
> - **MUST / SHOULD / MAY** indicate normative priority within this BRD. A **[DECISION] MUST** is binding for implementation of this proposed baseline, but remains changeable by the product owner.
>
> If a proposed decision conflicts with an explicit source requirement, the source requirement prevails. Do not silently implement unspecified behavior: add it to the decision log.

---

## 1. Executive Summary

The application helps a retail or food-service store manager build a practical weekly staff schedule. Demand is represented by historical transaction counts per hour and day of week. The manager maintains a staff list with weekly maximum working hours and a set of reusable shift definitions. The application proposes which employees should work which shifts, prioritizing coverage of busy periods, respecting weekly hour limits, and distributing work fairly. The manager can inspect the draft, modify assignments directly, and immediately understand the effect on workforce coverage and staff utilization.

**The essential product outcome is not merely a valid roster.** It is an explainable, editable *best-effort schedule* that shows where staffing meets demand, where it falls short, and why. Inability to meet all demand is a legitimate, visible result—not an unexplained generation failure.

### 1.1 Product goals

1. Turn transaction history into a clear, defensible indication of required hourly staffing.
2. Propose a weekly roster using predefined shifts and available employee capacity.
3. Never violate weekly maximum hours or assign one employee overlapping shifts during automatic generation.
4. Seek useful and proportionate work allocation, without sacrificing critical demand coverage simply to equalize hours.
5. Let non-technical managers adjust the roster quickly, with accurate, immediate feedback.
6. Expose shortages, excess staffing, assumptions, and the limits of the proposed schedule.

### 1.2 Success criteria

A manager can create a schedule, maintain staff and shifts, import the supplied CSV format, generate a plausible draft, inspect it across Monday–Sunday, reassign people, and see correct hourly and weekly metrics. The application handles malformed inputs, inadequate capacity, and conflicting changes without silent data loss or misleading analytics.

### 1.3 Boundaries

**In scope [SOURCE]:** schedule creation; staff add/edit/remove; CSV demand import; configurable shifts seeded with 07:00–15:00 and 15:00–23:00; automatic scheduling; directly editable weekly roster; aggregated hourly and weekly statistics; immediate feedback and warnings.

**Out of scope [SOURCE]:** authentication, multi-user collaboration, and deployment. Payroll, wage costing, labor-law compliance, breaks, overtime compensation, leave approval, and forecasting future calendar dates are not specified and are **not** part of this baseline.

**Optional [SOURCE]:** drag-and-drop editing, coverage visualization, individual availability/days off, skills or supervisor requirements, export. Direct roster editing and meaningful coverage warnings are core requirements regardless of whether drag-and-drop or a dedicated heatmap is built.

---

## 2. Actors, Concepts, and Business Scope

### 2.1 Primary actor

**Store Manager:** creates and maintains a typical-week schedule; provides demand data; sets employee capacity and shift options; generates, reviews, and adjusts the roster; interprets coverage and workload metrics.

There are no separate employee, administrator, or auditor journeys in the baseline.

### 2.2 Business terms

| Term | Business meaning |
|---|---|
| Schedule | A container for one typical Monday–Sunday week and its staff, demand data, shift definitions, and assignments. |
| Transaction | A recorded business transaction in a particular hourly period; used as a proxy for workload, not an exact measure of service time. |
| Hourly demand | The estimated number of employees needed during a one-hour interval. |
| Shift definition | A reusable start–end time interval to which employees may be assigned on individual days. |
| Assignment | One employee working one defined shift on one day of the week. |
| Roster | The complete weekly set of assignments. |
| Weekly maximum | Upper limit on an employee's scheduled working hours across the seven-day template. |
| Scheduled staff-hours | Sum of time allocated to people, not merely hours during which the store is open. |
| Hourly coverage | Number of employees working during a given hourly interval, or their equivalent staff-hours for that interval. |
| Understaffing | Required staff exceeds scheduled coverage for an interval. |
| Overstaffing | Scheduled coverage exceeds modeled requirement for an interval. |
| Utilization | Assigned weekly hours divided by that employee's weekly maximum, when the maximum is positive. |
| Draft | Manager-editable proposal; no publication/approval workflow is included. |

### 2.3 Temporal boundaries [DECISION]

- A schedule is a **typical week**, not a roster tied to an actual start date. Historical file dates do not determine the days used for assignment.
- Week ordering and all views are **Monday through Sunday**, even if imported CSV columns begin with Friday.
- Store hours are **07:00–23:00 daily** for this baseline: 16 one-hour buckets/day, 112 buckets/week.
- A bucket labelled `14:00` means **14:00 inclusive to 15:00 exclusive**. A shift ending at 15:00 does not cover the bucket beginning at 15:00.
- Baseline shifts begin and end on whole hours, have a positive duration, remain inside 07:00–23:00, and do not cross midnight. An importer may recognize alternative textual time labels but maps demand only to the 16 supported buckets.
- All displayed shift durations count as working time. Unpaid breaks, partial-hour shifts, and cross-midnight shifts require separate product decisions and are outside the baseline.

**Rationale:** These decisions align all scheduling and reporting with the provided hourly report and two default eight-hour shifts. They prevent ambiguous fractional coverage calculations within this exercise.

---

## 3. Core End-to-End User Journey

1. **Create:** The manager creates and names a schedule. It begins with two default shift definitions, no employees, no imported demand, and an empty roster.
2. **Configure staff:** Add employees and weekly maximum hours; edit or remove them as needed.
3. **Import demand:** Upload a weekly transaction report. See validation results and an intelligible demand preview.
4. **Review shifts:** Keep defaults or create/edit/remove allowed shift definitions.
5. **Generate:** Trigger Auto-schedule. The application checks prerequisites, estimates required staffing, and produces a best-effort draft plus diagnostics.
6. **Inspect:** See which people work each day and shift, each person's assigned hours, and how coverage compares with demand.
7. **Adjust:** Assign, remove, or reassign employees directly in the roster. Changes update the metrics and warnings immediately.
8. **Review outcome:** Check shortages, excess coverage, fairness/utilization, and the distinction between overall and average transactions per staff-hour.
9. **Regenerate if desired:** With an existing draft, confirm before replacing assignments; no silent loss of manual edits.

**No mandatory publication or approval step** is included. The product's terminal state is an editable, reviewable draft.

---

## 4. Functional Requirements and Acceptance Criteria

### BR-01 — Create and select a schedule

**[SOURCE]** A manager can create a schedule containing staff, transaction data, shifts, and the generated roster.

**[DECISION]** A newly created schedule is empty except for default shifts; schedule names are editable and do not need to be unique. Multiple schedules may exist independently. The application must make the currently selected schedule clear. Changes to one schedule do not change another.

**Acceptance criteria**
- Given no schedules, the manager can create one without importing data first.
- The schedule visibly contains Monday–Sunday and the 07:00–23:00 operating window.
- Two default shifts exist: **07:00–15:00** and **15:00–23:00**.
- Generation cannot proceed until valid demand and at least one eligible employee/shift exist; the user receives a specific, actionable explanation.

### BR-02 — Maintain staff and weekly hour limits

**[SOURCE]** Add, edit, and remove employees with at least name and maximum weekly hours.

**[DECISION]**
- Names must not be blank after whitespace trimming; duplicate display names are allowed but each employee must be individually distinguishable in selection and editing (e.g., disambiguating suffix in the UI).
- Maximum hours must be a finite, nonnegative number. For the baseline's whole-hour shifts, accept whole hours only; a value of zero is valid and means no assignments are possible.
- Editing a maximum does not silently delete existing assignments. If the new maximum is below already assigned hours, the change is rejected with a clear explanation and a path to remove or move assignments first. This preserves the invariant that saved rosters never exceed employee maximums.
- Removing an employee who is assigned prompts for confirmation, shows how many assignments will be removed, and updates coverage; removal never leaves dangling assignments.

**Acceptance criteria**
- Employee capacity is visible next to assigned hours, e.g., **24 / 32 h**.
- A person whose weekly maximum is below the shortest available shift remains in the staff list but cannot receive a qualifying assignment.
- Duplicate-name employees can be distinguished when assigning shifts.
- Editing or removing staff cannot make summary totals stale.

### BR-03 — Import historical transaction data

**[SOURCE]** Accept the sample weekly CSV: first column is hour of day, other columns are weekdays, and each cell is the transaction count for that day/hour. The example is Friday–Thursday and runs from 7am through 10pm, with the latter bucket ending at 23:00. Tolerate reasonable variation in week labels and column order; report malformed input gracefully.

**[DECISION]**
- Accept all seven weekday columns in any order, using recognizable full or abbreviated English day names (case-insensitive). A date range or extra file title is metadata, not the day order.
- Accept common whole-hour labels such as `7am`, `7 AM`, `07:00`, `1pm`, `22:00`.
- Each of the **112 expected weekday/hour combinations** must appear exactly once after normalization; missing or duplicate days/hours are validation errors.
- Transaction counts must be finite, nonnegative integers; zero is valid. Negative, blank, nonnumeric, and fractional counts are invalid.
- Reject unexpected time buckets rather than silently discarding them. Report actionable errors indicating row/column or day/hour when possible.
- Validate the entire file before replacing demand. On any error, leave the previously imported data and roster unchanged.
- Successful re-import replaces the prior demand data **without changing assignments**. Recalculate required coverage, reporting, and shortage warnings; clearly explain that the roster now reflects an earlier draft against new demand. The manager can choose to regenerate afterward.
- A demand preview and import success/error state are visible. Do not interpret missing input as zero transactions.

**Acceptance criteria**
- The supplied CSV format imports successfully even though its first day is Friday.
- Reordered weekday columns produce the same normalized week.
- A zero transaction count is not mistaken for a missing value.
- An invalid file never partially overwrites valid data.
- Changing demand refreshes coverage alerts without automatically rewriting assignments.

### BR-04 — Manage shift definitions

**[SOURCE]** Two defaults: 07:00–15:00 and 15:00–23:00. Managers can add, edit, and remove shifts.

**[DECISION]**
- Each shift is defined solely by its start and end times; it applies as a selectable option on any day.
- Shift names such as *Morning* and *Evening* are only display labels, not additional required business attributes.
- Valid shift: start before end, whole-hour times, within operating hours, nonzero duration.
- Different shift definitions **may overlap**. This enables shorter peak-hour shifts; however, an individual cannot work overlapping shifts on the same day.
- Exact duplicate start/end shift definitions are rejected to avoid confusing identical choices.
- Editing a shift already used in assignments requires a preview of impact. The change is allowed only if all existing affected assignments remain within weekly maximums and do not overlap; otherwise the manager must resolve assignments first.
- Deleting a used shift requires confirmation and removes associated assignments across all days. Coverage and hours update immediately.
- A schedule with no shifts remains editable, but generation is disabled with a clear message.

**Acceptance criteria**
- A 10:00–14:00 peak shift can coexist with both defaults.
- Assigning a person to 07:00–15:00 and 10:00–14:00 on the same day is rejected as overlapping.
- 07:00–15:00 and 15:00–23:00 do not overlap at the boundary.
- Removing a used shift does not leave unexplainable phantom staff-hours.

### BR-05 — Estimate required staffing from transactions

**[SOURCE]** Convert hourly transaction counts to hourly required staff using a justified transactions-per-person threshold and a sensible minimum whenever open.

**[DECISION: baseline policy]**

For each weekday `d` and hourly bucket `h`:

$$
\operatorname{required}(d,h)=\max\left(1,\left\lceil\frac{\operatorname{transactions}(d,h)}{N}\right\rceil\right)
$$

- Baseline **N = 20 transactions per employee-hour**. It is an explicit modeling assumption—not a productivity rate established by the supplied data.
- The manager can change `N` to a **positive whole number** before generation; display the active value and explain the effect. Changing `N` recalculates demand, shortages, and warnings, **without silently modifying assignments**.
- One employee is the minimum required for each open hour, including zero-transaction hours. A temporary zero-demand period does not mean the store is closed.
- This is a **staffing heuristic**, not a validated forecast of arrivals, service duration, queueing time, or labor productivity.

**Example with N = 20**

| Transactions in one hour | Required staff | Why |
|---:|---:|---|
| 0 | 1 | Open-hour minimum |
| 7 | 1 | Minimum and demand |
| 20 | 1 | Exact threshold |
| 21 | 2 | Ceiling after threshold |
| 48 | 3 | Ceiling of 2.4 |
| 64 | 4 | Ceiling of 3.2 |

**Acceptance criteria**
- Required staff is a whole number of at least one for every supported operating bucket.
- Results adjust predictably when `N` is changed.
- Required staffing is shown separately from actual scheduled coverage.

### BR-06 — Generate a demand-aware weekly draft

**[SOURCE]** Auto-schedule assigns staff to available shifts across the week, concentrates coverage on busier periods, respects each person's weekly maximum, aims for fair and useful allocation, and returns a visible editable draft. Insufficient capacity must be handled gracefully.

**[DECISION: optimization policy]**
1. **Hard feasibility first:** An automatically assigned employee must exist, each shift must exist, weekly maximums must not be exceeded, and the employee must not be on overlapping shifts on the same day.
2. **Primary goal — minimize uncovered staffing need:** Prefer assignments that reduce unmet required staff-hours. Giving an additional employee to an already sufficiently staffed hour has no shortage-reduction value for that hour.
3. **Secondary goal — avoid excess staffing:** Among rosters with equal or comparable unmet need, prefer fewer unnecessary staff-hours. Unused capacity is acceptable.
4. **Tertiary goal — distribute useful work fairly:** Among rosters with comparable coverage and excess, prefer allocations that reduce differences in normalized utilization across employees who can work at least one available shift.
5. **Consistent tie-breaking:** Identical inputs, rules, and staff/shift ordering must produce reproducible results. Do not imply random choice is a fairness guarantee.
6. **Best effort:** If full coverage is not achievable, still produce the best valid draft available and expose unmet demand.

The policy is **lexicographic in intent**: hard constraints must always hold; coverage takes precedence over avoiding excess, which takes precedence over marginal fairness improvements. This resolves otherwise ambiguous trade-offs without pretending every goal can be maximized simultaneously.

#### 6.1 Why shift-level decisions matter

Transactions vary hour by hour, but an assignment commits an employee to an entire shift. With only two non-overlapping 8-hour defaults, staffing within each shift is constant; a noon peak may cause excess morning staffing if the whole 8-hour block is covered to peak level.

**Example (illustrative, not imported data):** A morning shift has hourly required staff `[1, 2, 2, 3, 4, 4, 3, 2]`, totaling 21 required staff-hours. Four people across the full shift provide 32 staff-hours, whereas three provide 24 but leave shortages in two peak hours. Adding a 10:00–14:00 short shift could provide more targeted peak coverage. The scheduler must honor the **actual shifts configured**, not silently invent new ones.

#### 6.2 Coverage versus fairness example

Alice can work 40 hours and Diana 16 hours. Giving both 16 hours is equal in absolute hours but not in opportunity relative to capacity (40% versus 100% utilization). Fairness therefore considers capacity-normalized utilization, not an equal-hours mandate.

**Important exception:** If staff eligibility differs in a future release (availability or roles), utilization parity may not be fully achievable. Do not equalize utilization by knowingly introducing a materially worse staffing shortage.

#### 6.3 When no valid assignment improves coverage

Generation ends with a valid, possibly partial roster. It must not manufacture a full roster by exceeding hour limits. Do not assign additional employees solely to make all utilization figures appear equal if there is no useful coverage benefit, unless an explicit product policy later changes this priority.

#### 6.4 Required generation feedback

Provide: roster; total required staff-hours; scheduled staff-hours; covered staff-hours; unmet staff-hours; coverage percentage; employee allocated/max hours; hourly shortage warnings; and an understandable indication that a result is a *draft*. Describe the adopted demand threshold and fairness approach in accessible language.

**Acceptance criteria**
- High-demand hours receive more coverage **where the configured shifts and available capacity make this possible**; do not promise a strict monotonic relationship at every hour.
- No auto-generated employee exceeds a weekly maximum or works overlapping shifts.
- The same valid inputs produce the same roster and metrics.
- An empty or insufficient-capacity scenario yields actionable feedback rather than a crash or unexplained rejection.
- A partial roster can be edited after generation.

### BR-07 — View the weekly roster

**[SOURCE]** A non-technical manager can see assignments clearly by day and shift.

**[DECISION]**
- Primary view: a week grid with Monday–Sunday across columns and shifts as rows, with assigned employee names visible in each day/shift cell.
- Always label shifts with actual start and end times; do not rely on *Morning/Evening* alone.
- Make empty cells distinguishable from missing data and from *understaffed* cells.
- Display per-employee allocated/max weekly hours in the assignment picker and/or a nearby staff panel.
- Allow straightforward inspection of the complete roster without navigating seven separate pages.
- If there are many shifts or employees, maintain readability using a responsive layout, wrapping/chips, or accessible scrolling rather than clipping names or compressing text excessively.

**Acceptance criteria**
- The manager can answer “Who works Tuesday 15:00–23:00?” from the principal roster view.
- Time ranges, names, and assignment statuses remain readable on typical desktop screens.
- A blank shift/day cell is directly editable.

### BR-08 — Directly edit assignments

**[SOURCE]** Managers can assign, reassign, and remove staff from shifts on any day. Changes must update the aggregated view immediately. Constraints and staffing problems must be explained.

**[DECISION]**
- Clicking a day/shift cell opens an inline picker, popover, or similarly direct control with current assignees and eligible employees.
- Add an assignment, remove one, or reassign from person A to person B with minimal steps. Reassignment is treated as one deliberate action when possible, not a multi-screen workflow.
- **Manual assignments use the same hard rules as automatic generation:** weekly maximums cannot be exceeded and a person cannot work overlapping shifts. Invalid edits are rejected with specific reasons; the prior state remains intact.
- Understaffing and overstaffing are **warnings**, not blockers. A manager can retain a partial roster.
- A rejected edit never silently alters some other day or person's assignments.
- Successful edits immediately refresh employee hours, hourly coverage, weekly totals, ratios, and warnings.
- Managers may explicitly leave employees with zero scheduled hours if demand/capacity does not justify work; this should be visible, not treated as a hard violation.

**Acceptance criteria**
- Removing a person from a 07:00–15:00 shift changes coverage for exactly the applicable hours and decreases the person's weekly hours by eight.
- Attempting to add an overlapping shift gives a clear reason and preserves existing assignments.
- Attempting to exceed maximum hours explains the employee's current allocation, requested shift duration, and limit.
- No page reload is required to see updated metrics.

### BR-09 — Regenerate safely

**[DECISION]**
- If no assignments exist, Auto-schedule generates a draft directly.
- If assignments already exist, show a confirmation that regeneration **replaces current assignments**, including manual edits.
- Cancel preserves all assignments; confirm replaces them as one cohesive operation.
- Demand data, staff, and shift definitions are not replaced by roster regeneration.
- Persisted roster and visible summary must always correspond to the same completed generation/edit operation.

**[OPTIONAL]** Preserve *locked* assignments during generation, or compare alternative drafts. Do not implement either silently as baseline behavior.

### BR-10 — Aggregated summary and operational diagnostics

**[SOURCE]** For every day/hour display transaction count, scheduled staff-hours, and transactions divided by staff-hours; show weekly total staff-hours, total transactions, overall transactions/staff-hour, and arithmetic average of staffed-cell transactions/staff-hour. Avoid dividing by zero.

**[DECISION]** The schedule also exposes hourly **required staffing**, **actual coverage**, **gap**, and a **coverage rate** to help interpret the operational quality of the draft. These are derived from existing information and help meet the source requirement to warn about understaffing.

#### 10.1 Calculation definitions

For a one-hour bucket with whole-hour-aligned shifts:

- `transactions` = imported count for that weekday/hour.
- `scheduled staff-hours` = number of employees assigned to shifts covering the entire bucket, expressed in staff-hours (e.g., 3 staff × 1 hour = 3 staff-hours).
- `transactions per staff-hour` = transactions ÷ scheduled staff-hours, if staff-hours > 0; otherwise display **“–”**, not 0 or infinity.
- `required staff-hours` = required staff × one hour.
- `unmet staff-hours` = `max(0, required − scheduled)` for that bucket.
- `excess staff-hours` = `max(0, scheduled − required)` for that bucket.
- `covered staff-hours` = `min(required, scheduled)` for that bucket.

**Weekly metrics:**

$$
\text{Total Staff Hours}=\sum_{d,h}\text{Scheduled Staff Hours}_{d,h}
$$

$$
\text{Total Transactions}=\sum_{d,h}\text{Transactions}_{d,h}
$$

$$
\text{Overall Txns/Staff-Hour}=\frac{\text{Total Transactions}}{\text{Total Staff Hours}}
$$

$$
\text{Average Txns/Staff-Hour}=\operatorname{mean}_{(d,h):\,\text{StaffHours}_{d,h}>0}\left(\frac{\text{Transactions}_{d,h}}{\text{StaffHours}_{d,h}}\right)
$$

$$
\text{Coverage Rate}=\frac{\sum_{d,h}\min(\text{Required}_{d,h},\text{Scheduled}_{d,h})}{\sum_{d,h}\text{Required}_{d,h}}
$$

- Weekly **overall ratio** is staff-hour-weighted; weekly **arithmetic average** weighs every staffed day/hour cell equally. They must be shown separately, with unambiguous labels.
- If total staff-hours = 0, overall ratio is **“–”**. If no cells have staff, arithmetic average is **“–”**.
- Zero-staff buckets remain included in weekly total transactions, even though their individual ratio is undefined and excluded from the arithmetic average.
- Coverage rate denominator is always positive under the open-hour minimum rule. The rate is capped at 100%: extra employees cannot artificially inflate coverage.
- Staff utilization is calculated only for employees with positive maximum hours. A zero-maximum employee's utilization is **“N/A”**, not an infinity or a zero/zero percentage.
- Keep weekly and, where practical, per-day totals. The source specifically requires the weekly totals and the day/hour grid.

#### 10.2 Arithmetic acceptance example [SOURCE]

| Hour | Transactions | Staff-hours | Txns/staff-hour |
|---|---:|---:|---:|
| 12:00 | 33 | 3 | 11.0 |
| 13:00 | 48 | 3 | 16.0 |
| 14:00 | 33 | 2 | 16.5 |
| **Total / overall** | **114** | **8** | **14.25 (14.3 to 1 decimal)** |

Arithmetic average of the three per-cell ratios is **14.5**, not 14.25. The interface must not conflate them.

#### 10.3 Display and warning policy [DECISION]

- Visually flag buckets where actual coverage is below required coverage.
- Distinguish **shortage** from **excess** rather than labeling both as general errors.
- Show numerical differences, for example: “Tuesday 18:00–19:00: required 3, assigned 2, short 1.”
- If there are many adjacent shortage buckets, grouping a warning by contiguous time range is acceptable as long as individual hour details remain accessible.
- Do not present transactions per staff-hour as a proven measure of employee performance or service quality; its meaning is descriptive.

---

## 5. Scheduling Policy and Trade-off Evaluation

### 5.1 Goals and non-goals

**Goal:** Find a plausible valid assignment set that covers as much modeled demand as practical, avoids unnecessary staffing, and spreads useful hours proportionately.

**Not a goal:** Guarantee a globally optimal solution; predict customer waiting times; guarantee equal absolute weekly hours; force every employee to reach maximum capacity; or satisfy infeasible demand by violating hard rules.

### 5.2 Candidate scheduling approaches

| Approach | Decision logic | Strength | Weakness | BRD recommendation |
|---|---|---|---|---|
| Peak staffing per shift | Set headcount to the maximum hourly need within that shift. | Simple, protects peaks where capacity allows. | Excess staffing in quieter hours; may consume capacity needed elsewhere. | Useful transparent baseline, not sufficient alone for assignment decisions. |
| Average staffing per shift | Set headcount to rounded average hourly demand. | Efficient on hours. | Can deliberately miss important peak periods. | Not recommended as sole rule. |
| Hourly-first priority, then shift assignment | Rank shortages or high-value shift coverage, allocate eligible staff, then balance hours. | Demand-aware and practical under constraints. | Local decisions can be suboptimal. | **Recommended baseline.** |
| Global constrained optimization | Evaluate assignments jointly under a stated priority policy. | Better consistency for interacting constraints and complex shifts. | More effort to formulate, validate, and explain. | Suitable future refinement, not necessary to meet baseline. |

**The BRD specifies business outcomes and priorities, not a mandated optimization technique.** An implementation may use a heuristic or a formal optimizer, but must satisfy the invariants and evaluation scenarios below.

### 5.3 Prioritization under scarcity

If capacity cannot cover all hours, the scheduler should prioritize the assignment providing the greatest reduction in unmet required staff-hours across its entire shift. Do not merely rank a shift by its single busiest bucket or by raw transaction volume while ignoring already scheduled coverage.

When two alternatives reduce shortages equally, prefer lower excess staffing, then fairer allocation. For exact ties, use a reproducible convention.

**Example:** An additional eight-hour employee assigned to a partially staffed shift may resolve five missing staff-hours; assigning them elsewhere might resolve only one missing staff-hour. The first assignment offers greater coverage benefit, even if the second shift contains one larger isolated transaction count.

### 5.4 Fairness: chosen definition and limitations

**[DECISION]** Fairness is assessed primarily by employee **utilization** = assigned hours ÷ maximum hours. Fairness is a soft objective, not an entitlement to a particular minimum.

| Staff | Weekly maximum | Assigned | Utilization |
|---|---:|---:|---:|
| Alice | 40 h | 32 h | 80% |
| Bob | 32 h | 24 h | 75% |
| Charlie | 24 h | 16 h | 66.7% |
| Diana | 16 h | 8 h | 50% |

A roster concentrating all hours on a few workers while others are eligible and unused is undesirable when alternative assignments preserve coverage and improve balance. Conversely, allocating hours solely to equalize percentages can create excess staffing; avoid presenting it as automatically better.

**[DECISION]** No fixed minimum utilization (e.g., 50%) is guaranteed. The assignment does not mandate one, and some staffing/shift combinations cannot satisfy such a floor. Report low allocation as an informative fairness signal, not a hard error.

### 5.5 Three different capacity concepts

1. **Raw weekly capacity:** sum of employee weekly maximum hours.
2. **Schedulable capacity:** hours employees can actually work using allowed shift durations and other rules.
3. **Required staff-hours:** sum of modeled hourly need.

These are not interchangeable. For example, four employees capped at 24 hours supply 96 raw weekly staff-hours; if the store requires at least one person across 112 open hours, the team is at least 16 staff-hours short. However, having 160 raw hours against 140 required hours **does not guarantee feasibility** when shifts are indivisible or constraints prevent covering particular time periods.

### 5.6 Business assumptions and future alternatives

- Transaction count is a workload proxy, not a complete measure of effort. Different transactions may take different amounts of service time.
- A single fixed N implies uniform productivity across days, employees, transaction types, and service conditions.
- Additional shift definitions may reduce unnecessary hours when demand is concentrated in shorter peaks.
- Future enhancements could allow varying N by store/day/hour, service-level targets, employee skills, availability, breaks, or historical averaging. These are **not** baseline requirements.

---

## 6. User Experience Requirements

### 6.1 UX principles

1. **Roster first:** The principal screen answers who works when.
2. **Direct manipulation:** Editing a day/shift assignment is a quick local action, not a multi-page form workflow.
3. **Visible consequences:** Any assignment edit immediately updates staffing and employee-hour consequences.
4. **Contextual explanations:** Show why an action is invalid and how to resolve it.
5. **Distinct concepts:** Actual staff-hours, modeled required staff, shortage, utilization, and productivity ratios must not be confused.
6. **Progressive detail:** Summary at a glance, hourly detail when needed; do not overwhelm the main roster with every statistic.
7. **Recoverability:** Confirm destructive changes or roster replacement and never silently discard work.

### 6.2 Recommended information hierarchy

**Top:** Schedule name, draft status, staffing threshold N, import state, and Auto-schedule action.

**Overview:** Weekly coverage percentage, uncovered staff-hours, total scheduled staff-hours, and warning count. If transactions are loaded, show relevant transaction totals.

**Main pane:** Monday–Sunday roster grouped by configured shift; names visible within day/shift cells; add/remove/reassign controls.

**Context panel:** Employee workload (assigned/max hours), selected shift details, and eligibility reasons.

**Analysis pane/tab:** Hourly demand-versus-coverage matrix and required transaction/staff-hour summaries; highlight shortages/excess staffing.

**Configuration:** Staff, shifts, and import controls accessible without hiding or interrupting the roster.

### 6.3 Important states

| State | Required experience |
|---|---|
| New schedule | Guided empty state explaining add staff → import data → generate. |
| No staff | Explain that staff are needed; prevent meaningless generation. |
| No valid demand | Explain import requirement and show sample format guidance. |
| No shifts | Explain that valid shifts must be defined. |
| Import failure | Show exact issues; preserve previous valid demand and roster. |
| Generation success | Display draft and clear analysis of coverage and utilization. |
| Generation with shortages | Display usable partial draft plus visible warnings. |
| Invalid manual edit | Explain rule violated; preserve prior assignments. |
| Shift/staff removal | Explain impact and require confirmation if assigned. |
| Existing manual edits + regeneration | Explain replacement; confirm/cancel. |
| No scheduled staff | Show zero hours, zero coverage, and “–” for undefined ratios. |

### 6.4 Interaction details

- Employee options should indicate assigned/max hours and preferably disable invalid choices *with explanations* rather than merely omitting them.
- After an edit, keep the manager near the edited cell; avoid page jumps or modal chains.
- Use textual signals in addition to color: “Short 1,” “Covered,” “Excess 1.” Do not rely solely on red/green.
- Format all ratios consistently (e.g., one decimal in the visible grid) while calculating from unrounded values.
- The weekly roster and hourly analytics are related views of the **same current assignments**; no manual refresh should be necessary.
- A dedicated heatmap or drag-and-drop may improve usability, but is not a prerequisite to fulfilling direct editing and real-time feedback.

---

## 7. Business Invariants

These are non-negotiable properties of every saved baseline schedule unless explicitly labeled as a diagnostic rather than a strict rule.

| ID | Invariant | Enforcement |
|---|---|---|
| INV-01 | Each assignment refers to an existing employee and shift. | Hard rule |
| INV-02 | Each assignment applies to exactly one day of the typical week. | Hard rule |
| INV-03 | One employee cannot be assigned twice to the same day/shift. | Hard rule |
| INV-04 | One employee cannot work overlapping shifts on the same day. | Hard rule |
| INV-05 | Assigned weekly hours for an employee do not exceed their maximum. | Hard rule |
| INV-06 | Shift end is later than shift start and is within supported operating hours. | Hard rule |
| INV-07 | Demand is either a complete valid 112-cell report or not accepted; missing is not zero. | Hard rule |
| INV-08 | An unsuccessful import or edit leaves the prior valid state unchanged. | Hard rule |
| INV-09 | Displayed staff-hours equal time represented by current assignments. | Calculation invariant |
| INV-10 | Overall and average transaction-per-staff-hour metrics follow distinct formulas. | Calculation invariant |
| INV-11 | Ratio with zero staff-hours is undefined and displayed as “–”. | Calculation invariant |
| INV-12 | Covered demand in any bucket never exceeds its required demand. | Calculation invariant |
| INV-13 | Understaffing and overstaffing are permitted schedule states and are visible. | Soft diagnostic |
| INV-14 | Re-running generation never silently destroys existing manual assignments. | UX invariant |
| INV-15 | Editing demand or the threshold changes demand diagnostics but not assignments without explicit regeneration. | Workflow invariant |
| INV-16 | Automatic generation is reproducible for identical inputs and policies. | Quality invariant |

---

## 8. Edge Cases and Pitfalls

| Scenario | Expected behavior / risk avoided |
|---|---|
| Hourly transactions = 0 | Still require one employee while store is open. |
| Missing transaction count | Reject report; do not interpret as zero. |
| Negative, decimal, blank, or nonnumeric transactions | Reject with a specific validation error. |
| Weekday columns reordered | Normalize to Monday–Sunday; do not misattribute demand. |
| Duplicate or missing hour | Reject; do not double count or silently omit. |
| File uses different historical date labels | Accept recognizable weekdays independently of historical date range. |
| Import fails after a previously successful import | Preserve prior demand, assignments, and summary. |
| Demand replaced after generation | Retain roster; recompute gaps and explain the roster is not regenerated. |
| Threshold N changed after generation | Recompute requirements and warnings; retain assignments until regenerated. |
| No employee or no shift | Disable/decline generation with actionable explanation. |
| Weekly capacity below minimum opening coverage | Generate partial roster where possible and quantify shortages. |
| Total capacity exceeds total demand but shift composition is restrictive | May still have shortage; do not equate aggregate hours with feasibility. |
| An employee has 0 maximum hours | They remain visible but cannot receive assignments; utilization is N/A. |
| An employee's maximum is shorter than any shift | They cannot be scheduled under available shifts. |
| Two shifts start/end at same boundary | Treat `[start, end)` intervals as nonoverlapping. |
| Two shift definitions overlap | Allowed globally; not allowed for same employee on same day. |
| Manager edits a used shift to create conflicts | Reject that change with affected assignments identified. |
| Manager deletes an assigned shift | Confirm and remove dependent assignments, then recompute. |
| Manager deletes an assigned employee | Confirm and remove dependent assignments, then recompute. |
| Employee display names are identical | Keep employee options distinguishable. |
| Manager attempts to exceed maximum hours | Reject and show assigned + proposed vs limit. |
| Manager removes staff from a busy hour | Accept edit, show resulting shortage. |
| A cell has zero scheduled employees | Show “–” for its transaction/staff-hour ratio. |
| All cells have zero scheduled employees | Both overall and average ratios are “–”; coverage is 0%. |
| Adding extra employees beyond required coverage | Coverage rate does not exceed 100%; excess is visible. |
| Two possible schedules have similar coverage | Prefer lower excess, then fairer utilization; be consistent. |
| Manual edits exist before regeneration | Show explicit replace/cancel confirmation. |
| All demand can be covered with fewer than all available hours | Leave unused capacity rather than staffing purposelessly. |

### 8.1 Common analytical pitfalls

1. **Optimizing transaction ratio instead of coverage:** Fewer staff always increases transactions/staff-hour mathematically, even when customer service deteriorates. It is a descriptive metric, not the optimization objective.
2. **Averaging incorrectly:** `sum(transactions)/sum(staff-hours)` is not the unweighted mean of staffed-cell ratios.
3. **Counting shifts rather than people:** Two employees in one eight-hour shift contribute 16 weekly staff-hours, not eight.
4. **Boundary double-counting:** A 07:00–15:00 shift must not count in the 15:00–16:00 bucket.
5. **Mistaking available hours for assignable hours:** Shift indivisibility and overlap can leave apparently sufficient capacity unusable.
6. **Fairness without coverage:** A schedule where everyone works zero hours may be perfectly equal but operationally useless.
7. **Peak-only staffing:** Covering the maximum hour by assigning staff to every hour of a long shift can create avoidable excess.
8. **Silent mutation:** A shift edit, deletion, re-import, or regeneration must not implicitly erase other business decisions without explanation.
9. **Treating low-utilization staff as a violation:** Fairness is a goal to improve, not permission to create unnecessary shifts.
10. **Confusing insufficient demand data with zero demand:** The first is a data-quality failure, the second is a valid observation.

---

## 9. Acceptance Test Strategy

Testing must establish **business correctness**, not simply that the Auto-schedule button returns a nonempty roster. Validation should distinguish strict invariants from optimization quality, which may have more than one defensible answer.

### 9.1 Testing layers by behavior

**Input and configuration tests:** week/day normalization, time labels, complete 112-cell imports, invalid counts, duplicate/missing buckets, replacement rollback, staff/hour validation, and shift modification behavior.

**Scheduling invariant tests:** for every generated draft, no maximum-hours breach, no overlapping assignment, valid references, reproducible output, and correct assignment durations.

**Scheduling quality tests:** compare coverage, excess and fairness for deliberately constructed scenarios, without requiring one exact roster unless a unique result is implied. Confirm that adding a candidate who resolves more uncovered staff-hours is preferred when other relevant considerations are equal.

**Calculation tests:** known hourly/weekly totals, zero denominators, ratio distinction, and capped coverage rates.

**User journey tests:** complete creation → import → generation → inspect → edit → observe live changes → regenerate/cancel workflow.

**Usability review:** a non-technical manager should identify assignees, shortages, and remaining staff capacity without understanding the optimization logic.

### 9.2 Mandatory scenario checklist

| ID | Scenario | Expected result |
|---|---|---|
| AT-01 | Create a new schedule | Monday–Sunday scope and two default shifts are present. |
| AT-02 | Add, edit, remove staff | Changes are reflected consistently; assigned removal is confirmed. |
| AT-03 | Import CSV with Friday-first columns | Successful Monday–Sunday demand mapping. |
| AT-04 | Import with shuffled weekday columns | Same normalized transaction values. |
| AT-05 | Import CSV with malformed count | Clear error, previous state preserved. |
| AT-06 | Import CSV with one missing hour | Error explicitly identifies missing data. |
| AT-07 | Default threshold with 48 transactions | Required staff = 3 for that bucket. |
| AT-08 | 0 transactions during open hour | Required staff = 1. |
| AT-09 | Auto-schedule under adequate capacity | Valid demand-aware draft; coverage diagnostics accurate. |
| AT-10 | Auto-schedule under insufficient capacity | Valid partial draft and explicit shortage report. |
| AT-11 | Auto-schedule with employee maximum = 0 | No assignment to that person. |
| AT-12 | Try same-person overlapping manual assignment | Edit rejected; prior roster preserved. |
| AT-13 | Try manual assignment above max hours | Edit rejected with numeric explanation. |
| AT-14 | Remove a person from an 8-hour shift | Employee hours fall by eight; relevant coverage cells update. |
| AT-15 | Add an overlapping peak shift definition | Definition accepted; same-person overlap still prohibited. |
| AT-16 | Delete used shift | Warning/confirmation; affected assignments removed if confirmed. |
| AT-17 | Edit used shift causing weekly-hour violation | Change rejected without partial state changes. |
| AT-18 | Re-import different demand | Assignments stay; required staffing and warnings refresh. |
| AT-19 | Change threshold after generation | Coverage diagnostics change; assignments remain unchanged. |
| AT-20 | Regenerate existing edited roster and cancel | Manual assignments preserved. |
| AT-21 | Regenerate and confirm | Draft assignments replaced in one cohesive update. |
| AT-22 | No staff hours in a bucket | Ratio displays “–”. |
| AT-23 | Use the 33/48/33 sample | Overall = 14.25; arithmetic average = 14.5. |
| AT-24 | Add staff beyond a bucket's requirement | Excess increases; coverage percentage does not exceed 100%. |
| AT-25 | Same input, run generator twice | Identical assignment outcome under the chosen deterministic policy. |

### 9.3 Acceptance of optimization quality

The assignment does not prescribe an objectively optimal roster. Evaluate proposed outputs using the following order:

1. **Hard validity:** Zero violations.
2. **Demand coverage:** Lower unmet required staff-hours is better.
3. **Excess staffing:** For equivalent coverage, fewer excess staff-hours is better.
4. **Fairness:** For comparable coverage/excess, more balanced utilization is better.
5. **Transparency:** All remaining shortages and noteworthy allocation imbalances are visible.

**Important qualification:** This order describes the desired policy; a heuristic may not always discover the best global outcome. The baseline acceptance bar is a defensible, plausible, demand-aware roster—not a proof of global optimality. A quality test should flag obvious avoidable shortages, not falsely claim one exact optimal assignment is mandatory.

### 9.4 Property-style invariants

Across many generated, valid input scenarios, verify:

- Assigned hours for each person never exceed their maximum.
- No employee occupies two overlapping shift intervals on the same day.
- Every assignment has a valid employee, shift and day.
- All scheduled hours summed over employees equal scheduled staff-hours summed over the hourly coverage grid under the baseline whole-hour rules.
- `covered <= required` in every bucket and total coverage rate is within 0–100%.
- All ratios are finite or explicitly undefined as “–”; never display NaN or infinity.
- Invalid changes are atomic and cannot corrupt previously valid schedule state.

Avoid false assertions such as “more transaction demand always creates greater actual coverage”: staffing capacity may be fixed, and the roster may retain shortages.

### 9.5 Human usability acceptance

Ask a reviewer unfamiliar with the implementation to complete the following without instructions beyond normal on-screen guidance:

- Identify all people working Tuesday 15:00–23:00.
- Find the highest-priority understaffed period.
- Determine whether Alice can be assigned another eight-hour shift.
- Replace one person on a selected shift.
- Verify the change in weekly hours and hourly shortage.
- Explain why “overall transactions per staff-hour” differs from the arithmetic average.

Confusing navigation, hidden warnings, or misleading ratio labels are product defects even if the underlying calculations are correct.

---

## 10. Decisions, Open Questions, and Change Control

### 10.1 Adopted baseline decisions

| Decision ID | Selected rule | Reason |
|---|---|---|
| D-01 | Typical, reusable week rather than dated weekly instances | Mirrors the assignment's scheduling period. |
| D-02 | 07:00–23:00 every day, 1-hour buckets | Aligns with CSV and defaults. |
| D-03 | Whole-hour, same-day shifts only | Keeps calculation and editing semantics unambiguous. |
| D-04 | 20 transactions per employee-hour by default, configurable | Explicit and transparent demand proxy. |
| D-05 | Minimum one employee per open hour | Basic staffing floor. |
| D-06 | Cover demand, then reduce excess, then improve fairness | Avoids sacrificing operation for cosmetic equality. |
| D-07 | Fairness measured by normalized utilization | Accounts for different hour limits. |
| D-08 | Max hours and same-person overlaps are hard rules for generation and manual edits | Prevents intrinsically invalid saved rosters. |
| D-09 | Shortage and excess are visible warnings | Supports best-effort scheduling. |
| D-10 | Valid new demand replaces old demand while retaining roster | Separates observation updates from manager assignments. |
| D-11 | Editing an in-use shift cannot introduce assignment invalidity | Maintains coherent saved state. |
| D-12 | Regeneration replaces assignments after confirmation | Simple and predictable lifecycle. |
| D-13 | No minimum utilization guarantee | Avoids infeasible or wasteful staffing mandates. |
| D-14 | Reproducible generation for identical inputs | Supports trust and repeatable evaluation. |

### 10.2 Explicitly unresolved / future product decisions

These questions are **not answered by the source assignment** and should not be silently implemented in the baseline:

- Are staff breaks paid or unpaid, and do they count as floor coverage?
- Are overnight shifts, fractional hours, and variable store operating hours required?
- Are there legal rest-period, overtime, or consecutive-day restrictions?
- Should staff availability, leave, skills, minimum days off, or supervisor coverage become mandatory?
- Does the business value peak-hour shortages more heavily than other unmet staff-hours?
- Should managers be able to override weekly maximums with an explicit exception?
- Should locked assignments survive regeneration?
- Is scheduling intended for actual calendar weeks, holidays, or multiple stores?
- Does historical demand represent a single observed week or an average across many weeks?
- What employee service capacity can be empirically justified, and should it vary by role or hour?
- Are approval, publication, export, notifications, payroll, or audit histories required?

Do not treat the absence of these features as defects against this BRD. Record any additions as deliberate scope changes.

---

## 11. Delivery Definition of Done

The baseline is complete when all conditions below are met:

- [ ] A manager can create and identify an independent typical-week schedule.
- [ ] Staff can be added, edited and removed with clear maximum-hour rules.
- [ ] The supplied Friday-first, 07:00–22:00-hour CSV structure imports correctly and robustly.
- [ ] Both default shifts exist, and shifts can be safely created, edited and removed.
- [ ] The transaction-to-required-staff assumption is visible and applied consistently.
- [ ] Auto-schedule produces a plausible demand-aware draft without violating hard constraints.
- [ ] Insufficient capacity creates a readable partial result and shortage diagnostics.
- [ ] Roster is clear by weekday, shift, and assigned employees.
- [ ] Manager can directly assign, reassign and remove employees.
- [ ] Summary, coverage and warnings update immediately after relevant changes.
- [ ] Hourly and weekly transaction/staff-hour metrics use the specified formulas, including undefined-value handling.
- [ ] Invalid imports and edits never silently corrupt or partially overwrite state.
- [ ] Regeneration does not silently destroy manual changes.
- [ ] Core scenario and invariant tests pass, including numerical summary examples.
- [ ] Assumptions and optimization trade-offs are documented and consistent with actual product behavior.

### Delivery constraints carried over from the assignment

The assignment also expects a runnable GitHub repository, clear getting-started instructions, a brief explanation of the scheduling approach and assumptions, and an honest note on how AI assistance was used and verified. These are delivery obligations, not additional functional business rules. The suggested effort is approximately **4–6 hours**; prioritize a coherent end-to-end baseline over optional breadth.

---

## 12. Reference Examples for Demonstration

### Example A — A transaction-heavy bucket

- Day/hour: Friday 13:00–14:00.
- Imported transactions: 64 (from the assignment's illustrative CSV extract).
- Threshold: 20 transactions per employee-hour.
- Required staffing: `ceil(64 / 20) = 4`.
- If three employees cover the bucket, unmet staff-hours = 1 and transactions per staff-hour = `64 / 3 ≈ 21.3`.
- If five cover it, unmet = 0, excess = 1, and transactions per staff-hour = `64 / 5 = 12.8`.

These ratios alone do not indicate whether the customer experience is good; the coverage comparison indicates whether the model's chosen target has been met.

### Example B — Morning shift trade-off

- Configured shift: 07:00–15:00 (8 hours).
- Modeled hourly need: `[1, 2, 2, 3, 4, 4, 3, 2]`.
- Total required staff-hours: 21.
- Four full-shift employees contribute 32 scheduled staff-hours: zero shortages, 11 excess.
- Three full-shift employees contribute 24 scheduled staff-hours: two unmet staff-hours at the two buckets requiring four employees, and five excess staff-hours elsewhere.
- A shorter overlapping peak shift can potentially better target coverage, but the scheduler may only use configured shifts.

### Example C — Capacity shortfall

- Store open: 16 hours × 7 days = 112 hourly periods.
- Minimum staffing rule: one person in every open hour.
- Employees: four, each capped at 24 hours/week.
- Raw capacity: 96 staff-hours.
- At least 16 staff-hours of minimum demand cannot be met; the actual shortage may be larger after shift constraints are considered.
- Correct product behavior: valid partial roster, explicit shortage summary, and visible affected periods.

### Example D — Summary arithmetic

- 12:00: 33 transactions / 3 staff-hours = 11.0.
- 13:00: 48 transactions / 3 staff-hours = 16.0.
- 14:00: 33 transactions / 2 staff-hours = 16.5.
- Total = 114 transactions and 8 staff-hours.
- Overall ratio = 114 / 8 = 14.25 (display may round to 14.3).
- Mean of staffed cells = `(11 + 16 + 16.5) / 3 = 14.5`.

**Both metrics must appear with distinct labels.**

---

## 13. Final Product Principle

**Build a demand-driven, constraint-aware, explainable staff scheduler that leaves the manager in control.**

The proposed schedule must be understandable, editable, operationally useful, and honest about its limitations. A clean draft with explicit unmet demand is more valuable than a falsely “complete” roster that exceeds staff limits, hides errors, or cannot be meaningfully adjusted.
