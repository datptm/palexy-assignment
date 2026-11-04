# Scheduling algorithm v2 — Stage 1 specification

**Task:** `scheduling-algorithm-v2`  
**Status:** Proposed for review; no implementation in this stage.  
**Authority:** [Algorithm upgrade appendix](../../resources/Staff_Scheduling_System_Alg_Upgrade.md), especially §§2–6, 8, 10–13, as a delta to the [BRD](../../resources/Staff_Scheduling_System_BRD.md). The appendix governs its listed changes; other BRD behavior remains in force.

## 1. Goal and non-goals

Replace the current deterministic, absolute-benefit greedy draft generator with a pure four-phase generator: preparation (Phase 0), feasible-triple construction (Phase 1), deterministic refinement (Phase 2), and diagnostics (Phase 3). A manager should receive a valid, reproducible roster and an explanation of remaining shortage, capacity, and staff utilization. This specification covers required Tiers A and B.

The current `src/domain/generation.py` returns only a `ScheduleState`; `ScheduleService.generate`, `preview_generation`, `confirm_generation`, and refresh previews call it and return existing `ScheduleResult` metrics. The roster UI shows a replacement summary, while the staff panel shows assigned hours against raw maximum. The shared `validate_state` function reports weekly and daily limit breaches as warnings and has no `profile=auto` parameter. `Employee` has a stable ID but no `orderIndex` field. These are integration gaps to resolve in implementation, not claims that v2 exists today.

**Non-goals:** solver libraries; random or nondeterministic search; wall-clock stopping; demand smoothing, forecasting, fractional demand, or transaction-volume weighting; manager-adjustable baseline weights; availability, skills, breaks, days off, or legal rest rules; changes to import, database schema, manual-edit semantics, BR-10 §10.1 linear metric formulas, or regeneration confirmation. Tier C (rest-gap penalty, `N` sensitivity, read-only shift suggestions, and comparison harness) is excluded from required delivery unless separately selected after Tiers A and B. Global optimality is not promised.

## 2. Functional requirements

### FR-1 — Pure input, configuration, and prerequisite outcome

1. Expose a pure, typed generation operation equivalent to `generateRoster(input, config) -> outcome`: no I/O, global-state reads, input mutation, or persistence. The production adapter uses the existing schedule and service lifecycle. Generation starts with an empty roster even when the stored schedule has assignments.
2. Validate complete demand and configuration before search. Default `N=20`, `L=1`, `wUnder=3`, `wOver=1`, `wEmpty=6`, `maxPasses=50`, and `maxMoves=5000`. Config values are integers, with `N,L >= 1`, `wUnder > wOver >= 1`, `wEmpty >= wUnder`, and optional `restWeight >= 0`. Baseline weights are policy constants, not UI controls.
3. Return a pure blocked outcome with an actionable message for `NO_DEMAND`, `NO_SHIFTS`, or `NO_ELIGIBLE_STAFF` (including no employees or no employee able to take the shortest shift). At the existing service boundary, map these to legacy `SchedulingError` codes `MISSING_DEMAND`, `MISSING_SHIFTS`, and `NO_ELIGIBLE_EMPLOYEE`, respectively. A blocked result leaves stored roster, demand, history, and version unchanged. Insufficient aggregate capacity with at least one eligible employee produces a valid partial roster.
4. Internally parameterize day count and operating bounds for small-instance tests; production remains Monday–Sunday, 07:00–23:00. Preserve the distinction between absent demand and valid zero-transaction demand; each valid open hour still requires at least one person.

### FR-2 — Canonical preparation and effective capacity

1. Order employees by creation order, then stable ID; days ascending; shifts by `(start_hour, end_hour, id)`. Apply these orders to scans, ties, assignments, and trace. Precompute shift duration, covered buckets, and pairwise overlap.
2. Derive `req[d,h] = max(1, ceil(transactions[d,h] / N))` using integer arithmetic. For each employee, compute effective capacity `cap_i`: the greatest reachable sum of configured shift durations no greater than `max_i`, using at most `D × L` shifts. This is an upper bound because it may ignore same-day placement and overlap. Preserve the current weekly-maximum API range through `2^31 − 1` while computing this exact value with bounded resources; do not allocate an array proportional to `max_i` or introduce a smaller hidden limit.
3. Calculate `requiredHours = sum(req)`, `capacityHours = sum(cap_i)`, and `unavoidableUnmet = max(0, requiredHours - capacityHours)`. Report the bound as a minimum unavoidable shortage; make no claim that the remainder is avoidable.

### FR-3 — Cost and fair-share objective

1. For a bucket requiring `r >= 1` people with `s` scheduled, define primary cost `c(r,s)` as weighted unmet staff-hours plus `wOver × max(0,s-r)`. The first unmet person weighs `wEmpty`; each further unmet person weighs `wUnder`. `C` is the sum over buckets. Adding a person changes cost by `-wEmpty` when `s=0<r`, `-wUnder` when `0<s<r`, or `+wOver` when `s>=r`; removal uses the inverse marginal.
2. Define `totalHours = sum(hours_i)` and `sumCap = sum(cap_i)`. The proportional target is `totalHours × cap_i / sumCap`. Integer fairness cost is `Fdev = sum_i |hours_i × sumCap - totalHours × cap_i|`; when `sumCap=0`, `F=0`. For required Tiers A/B, `F=Fdev` because rest weighting is disabled. Division is for display only.
3. Compare rosters lexicographically by `(C,F)`: lower `C` always wins; lower `F` matters only when `C` ties. Keep manager-facing covered, unmet, excess, coverage-rate, and transaction ratios on the existing linear BR-10 formulas; label `C` and `F` as optimizer costs if displayed.

### FR-4 — Feasible-triple construction

1. A candidate is `(employee, day, shift)` and enters ranking only if it obeys H1 weekly maximum, H2 daily shift limit, H3 no same-person overlap, H4 no duplicate assignment, and H5 valid employee/shift/day references. `canAutoAssign` and the existing `validate_state` share the underlying H1–H5 predicates, so feasibility is equivalent to no hard-rule breach. Keep `validate_state`'s public manual-warning severities unchanged; do not require a new `profile=auto` parameter. Every accepted intermediate state satisfies H1–H5.
2. At each iteration, evaluate the slot's absolute `ΔC` and `excessAdded` for feasible triples. Ignore any candidate with `ΔC >= 0`. Choose lowest cost density `ΔC / duration`, comparing integer products rather than dividing; then lower `excessAdded`, lower candidate `ΔF`, employee creation order/ID, day, and shift order. Add the winner and repeat until no feasible negative-`ΔC` addition exists.
3. Tied staff choices use effective-capacity fairness, including zero-capacity staff being ineligible. The initial draft contains no inherited manual assignments. Construction must not invent shifts or add work solely to improve fairness.

### FR-5 — Deterministic refinement

1. Run fixed-order passes: ADD closure (rerun construction), DROP, MOVE, REPLACE. Scan assignments and destinations in canonical order. DROP accepts only `ΔC<0`. MOVE accepts `ΔC<0` or `ΔC=0` with `ΔF<0`, selecting its best valid destination by `(ΔC,ΔF,day,shift order)`. REPLACE changes the employee on the same slot, preserving coverage and accepting only `ΔF<0`, selecting the best eligible replacement by `(ΔF,employee order)`.
2. A tentative move must be evaluated on its resulting roster and restored if rejected. Accepted moves strictly decrease `(C,F)` lexicographically; every committed intermediate roster satisfies H1–H5. REPLACE is mandatory so coverage-neutral fairness repair is possible.
3. Stop at a pass with no change or at `maxPasses=50` or `maxMoves=5000` accepted moves. If a cap stops work, return the current valid roster with `refinementCapped=true`. No wall-clock timeout, randomness, or restart is used. Unless capped, the result has no feasible negative-`ΔC` ADD and no feasible negative-`ΔF` REPLACE.

### FR-6 — Generation diagnostics

1. Return the existing linear metrics plus per-employee hours, maximum, effective capacity, raw/effective utilization (`N/A` for a zero denominator), proportional target hours, and deviation hours. Display rounding may use one decimal but cannot affect search decisions.
2. Return one slot shortfall record per configured `(day,shift)` with unmet covered staff-hours. Assign exactly one reason in this order: `NO_ELIGIBLE_STAFF` if no employee has positive capacity; `STOP_RULE` if slot `ΔC>=0`; `CAPACITY` if no employee has enough remaining weekly hours for the shift; otherwise `DAY_CONSTRAINTS` (daily limit, overlap, or already assigned to that shift). Also return one hour-level `NO_SHIFT_COVERAGE` record for each unmet operating hour outside every configured shift. Distinguish slot from hour records, include actionable plain-language meaning, and do not sum overlapping slot shortage records as if they were distinct unmet hours.
3. Return the lower-bound values and a statement that at least `unavoidableUnmet` of actual unmet staff-hours cannot be avoided with current staff capacity. The difference is unexplained by the bound and must not be called an algorithm error.
4. Return informational flags: `LOW_UTILIZATION` when an employee's effective utilization is below one-half the positive mean effective utilization; `NEAR_ZERO_WHILE_OTHERS_FULL` when one positive-capacity employee has hours no greater than the shortest configured shift while another has at least 90% effective utilization; `REFINEMENT_CAPPED` when a cap stops search. Attach the no-feasible-coverage-neutral-reassignment explanation to the near-zero flag only when that condition has been verified.
5. Return an ordered trace of accepted ADD, DROP, MOVE, and REPLACE decisions with sequence, phase, employee and slot IDs, source/replaced ID where relevant, exact integer `ΔC` and `ΔF`, and a short explanation. Return final `C`, `F`, fairness deviation hours, rest violations (zero in required Tiers A/B), and the capped indicator. Trace order and content are reproducible.

### FR-7 — Service, UI, and documentation integration

1. Preserve generation, preview, confirmation, and refresh workflows: previews are read-only and version-bound; stale confirmations fail; confirmed replacement is atomic with any required demand/history write. Generated diagnostics must match the proposed or committed draft that is shown. Keep generation-specific diagnostics transient: show them only with the current generation result or preview, and clear them after reload or manual edit. Do not add persistence for them or present stale results as current.
2. In the current generation summary, show the lower-bound statement, per-slot shortfall reasons, and hour-level `NO_SHIFT_COVERAGE` reasons, grouping adjacent hours only if hour detail remains accessible. In the staff panel, keep assigned/raw maximum hours and show effective capacity and target hours as secondary information only for that current generation result or preview. Show informational flags and optimizer cost in a clearly identified diagnostics area; the decision trace may be exposed through an optional explanation view.
3. Update README with the demand/`N` assumption, cost and stop rule, effective-capacity fairness and REPLACE, reproducibility, limits of the heuristic and lower bound, and the distinction between optimizer cost and reported linear metrics.

## 3. Non-functional requirements

- **Determinism and precision:** Search uses integer arithmetic for `C`, `F`, all deltas, and density comparisons. Identical normalized input and ordering produce identical assignments, metrics, costs, flags, and trace across runs. Test-only seeded random fixtures do not introduce runtime randomness.
- **Performance and bounded work:** Maintain an incremental staffing grid, employee hours, and day assignments; precompute shift coverage and overlap. Refinement has the stated count caps. Keep the current `2^31 − 1` weekly-maximum API range. Capacity computation must return the recurrence's exact value with resource bounds that do not scale linearly with `max_i`; verify representative inputs at the API maximum and document the chosen method's time and memory bounds.
- **Security and reliability:** Treat browser, CSV, config, and persisted state at boundaries as untrusted. Reject invalid types/ranges, malformed demand, invalid references, and excessive resource use explicitly before writes. Never execute or deserialize input as code. Domain generation remains pure; persistence stays in the service/DB layer.
- **Compatibility:** Python 3.10+ and NiceGUI 3.18.0; zero new runtime dependencies or schema changes. Existing BRD metrics, manual edits, CSV import, warnings, previews, and atomic writes retain their contracts except where the appendix explicitly supersedes v1 generation.
- **Verification gate:** Existing pytest suite plus applicable new scenarios, `python -m ruff check .`, `python -m ruff format --check .`, and `python -m compileall -q src ui tests main.py` must pass in the project environment before implementation is done.

## 4. Edge cases and failure behavior

| Case | Required behavior |
|---|---|
| Demand absent, shifts absent, or all staff ineligible | Specific blocked code and actionable message; no state mutation. Define precedence as demand, shifts, then eligible staff. |
| Valid zero transactions | Minimum requirement remains one person per open hour; zero is never treated as missing. |
| Capacity is insufficient but nonzero | Generate a partial valid draft, report shortages and lower bound. |
| Unmet hour outside every configured shift | Emit one hour-level `NO_SHIFT_COVERAGE` diagnostic while retaining the existing hourly shortage metric. |
| Maximum is zero or shorter than every shift | Effective capacity zero, never assigned, utilization `N/A`; all such staff yields `NO_ELIGIBLE_STAFF`. |
| Mixed durations, overlap, or `L > 1` | Rank feasible triples by density; re-check daily limit and overlap after every tentative move. Adjacent shifts do not overlap but still count toward `L`. |
| `ΔC=0` addition or equally ranked choices | Do not ADD at zero; use the exact stated tie chain. Fairness cannot buy worse coverage cost. |
| `sumCap=0` | Blocked before construction; define `F=0` to keep cost functions total. |
| No unmet demand | Empty shortfall report and a zero lower bound; avoid division by zero in utilization and ratios. |
| Refinement cap hit | Return valid best-so-far draft and flag it; do not claim local optimality. |
| Existing manually edited roster | Read-only preview followed by explicit version-bound confirmation; cancellation/stale token preserves prior state. |
| Demand or config invalid / resource limit exceeded | Explicit error or blocked outcome, no partial service write, no silent fallback; valid weekly maxima through `2^31 − 1` are not rejected solely to simplify capacity computation. |

## 5. Acceptance criteria

| ID / maps to | Given / When / Then |
|---|---|
| AC-1 · FR-1 | Given each missing prerequisite, when calling the pure generator, then the matching blocked code/message is returned; through `ScheduleService`, the matching legacy error code is raised; persisted state is unchanged and zero transaction demand remains valid. |
| AC-2 · FR-2 | Given Example D's duration/max table, `max=0`, and representative maxima through `2^31 − 1`, then exact capacities match the recurrence without memory proportional to `max_i`; given Example G, the bound is 16 for 112 required hours and 154 for 250. (AT-40, AT-41) |
| AC-3 · FR-3, FR-4 | Given Example A, then the fourth default-weight employee has `ΔC=0` and is rejected; at `(wUnder,wEmpty)=(4,8)`, the fourth is accepted. (AT-32) |
| AC-4 · FR-3, FR-4 | Given Example B, then one person is assigned Monday and another on a different day, with no double-staffed day. (AT-38) |
| AC-5 · FR-4 | Given Example C's fixed pre-populated state, then the 4-hour peak shift ranks above the 8-hour shift and the two peak assignments are Monday then Tuesday. (AT-39) |
| AC-6 · FR-4, FR-5 | Given generated and sampled feasible states, then H1–H5 hold after each accepted move, `canAutoAssign` agrees with shared hard-rule predicates, manual warnings retain their severity, and `C_refined <= C_constructed`; every accepted move decreases `(C,F)`. (AT-34, AT-36, AT-43; INV-19, INV-20) |
| AC-7 · FR-5 | Given Example E's imbalanced roster, then a valid Alice-to-Diana REPLACE preserves `C` and reduces `F` from 3200 to 1792; a fairness-worsening replacement is rejected. (AT-37) |
| AC-8 · FR-1, FR-4, FR-5, FR-6 | Given identical input twice, then assignments, metrics, optimizer costs, flags, and trace are identical, with no runtime randomness or time-based termination. (AT-35; INV-21) |
| AC-9 · FR-2, FR-6 | Given shortages caused by each reason, including an uncovered operating hour, and sampled generated drafts, then every shortfall slot has exactly one correct slot reason, every unmet hour outside all shift windows has exactly one `NO_SHIFT_COVERAGE` record, and `unavoidableUnmet <= totalUnmet`. (AT-41; INV-22, INV-23) |
| AC-10 · FR-6, FR-7 | Given a current generated partial draft or preview, then summary and staff UI display the bound, slot and uncovered-hour reasons, effective capacity/target, flags, and distinguish optimizer costs from unchanged linear metrics; after reload or manual edit, generation-specific diagnostics are absent; the README explains the policy and limits. |
| AC-11 · FR-1, FR-7 | Given existing assignments, when previewing and cancelling or confirming with a stale version, then the committed roster is unchanged; a valid confirmation replaces assignments atomically. Existing AT-09/10/11/25 and regeneration/refresh tests remain green. |
| AC-12 · FR-1–FR-7 | All applicable project checks pass; tests prove behavior rather than only reproducing implementation formulas. |

AT-42 tests the optional Tier C rest-gap feature and is **not** a baseline pass condition. AT-44/45 are optional informational/oracle and Tier C scenarios respectively. Tier C remains an optional follow-up after Tiers A and B.

## 6. Assumptions

1. The appendix's Tiers A and B define this implementation target; Tier C remains a separate decision.
2. The Python-facing entry point may retain `generate_draft`/service methods as adapters, provided the new domain operation has an outcome carrying diagnostics and the same input yields the same output.
3. Existing employee tuple order represents creation order because the model and database expose stable IDs but no `orderIndex`; ties use ID. An explicit order field is only needed if persistent creation order can differ from that tuple order.
4. Shortfall reasons describe configured shift slots containing unmet hourly buckets, as in Appendix §6.2. An uncovered operating hour outside all configured shift windows receives its own hour-level `NO_SHIFT_COVERAGE` record; hourly shortage remains visible in existing metrics.
5. Generation diagnostics are derived for the current generation result or preview and are transient. They disappear after page reload or manual edits; current-state linear metrics remain visible.
6. Default rest penalty is zero. No rest gap is enforced as a hard limit or represented as a legal-compliance claim.

## 7. Open questions for review

The six decisions raised in the first draft are resolved above. No product-scope question is currently blocking Stage 2. Implementation planning still needs to choose and benchmark an exact, resource-bounded capacity method that preserves the current API maximum; that choice does not change the accepted behavior.
