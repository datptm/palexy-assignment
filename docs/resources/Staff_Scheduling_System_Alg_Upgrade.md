# Appendix A — Scheduling Algorithm v2 (Delta to BRD v1.0)

| | |
|---|---|
| **Applies to** | *Staff Scheduling System — Business Requirements Document*, v1.0 |
| **Appendix version** | 1.0 |
| **Status** | Implementation-ready delta |
| **Audience** | Coding agent / engineers updating an existing codebase |
| **Supersedes** | BR-06 optimization policy items 2–4; BRD §5.3 (prioritization under scarcity); amends D-06 and D-07 |
| **Extends** | BRD §5.4 (fairness definition), BR-06 §6.4 (required generation feedback), BR-10 (diagnostics), BRD §7 (invariants), BRD §9.2 (acceptance scenarios) |
| **Does not change** | Everything not listed in §13 of this appendix, in particular: CSV import, demand model (BR-05), validation model and severity table, manual editing, metric formulas of BR-10 §10.1, regeneration lifecycle (BR-09), UI structure |

> **Reading convention.** This appendix reuses the BRD tags **[SOURCE]**, **[DECISION]**, **[OPTIONAL]**, the keywords **MUST / SHOULD / MAY**, and the priorities **[P0] / [P1] / [P2]**. Additionally, each change is labelled **[UNCHANGED]**, **[CHANGED]**, or **[NEW]** relative to the BRD, and each implementation unit is assigned a **Tier**:
>
> - **Tier A — Core:** required for this appendix to be considered implemented.
> - **Tier B — Refinement:** required; builds on Tier A.
> - **Tier C — Optional:** implement only after Tiers A and B are complete and tested.
>
> **Cross-reference convention.** The BRD numbers some sub-sections twice (BR-06 has its own §6.1–6.4 and BR-10 its own §10.1–10.3, while the BRD also has top-level §6 and §10). To avoid ambiguity, BRD references in this appendix are always prefixed (`BRD §…`, `BR-06 §…`, `BR-10 §…`). A bare `§n` or `Appendix §n` refers to this appendix.

---

## 0. Instructions for the coding agent

1. **Read the BRD first.** This appendix is a delta. Where this appendix and the BRD conflict on an item listed in §13, **this appendix wins**. Everywhere else the BRD wins.
2. **Inspect the existing codebase before editing.** Locate and note: (a) the current auto-schedule generator, (b) the `validate` function / violation policy table, (c) the metrics module (hourly and weekly aggregates), (d) the types for schedule, employee, shift, assignment, (e) the settings/config object holding `N` and `dailyShiftLimit`, (f) the UI component that shows generation feedback, (g) the test layout. Adapt names in this document to repository conventions; keep public function signatures stable where practical.
3. **Implement in the order of §11.** Every step must leave the existing test suite green. Commit after each step with a message referencing the step number.
4. **No new runtime dependencies.** No solver libraries. No randomness. No wall-clock time limits (see §8).
5. **Pseudo-code is language-neutral.** Types are written TypeScript-style purely for clarity. Use the repository's language and idioms. All arithmetic in the generator MUST be integer arithmetic (see §8).
6. **Do not change behaviour that this appendix does not mention.** If you find a conflict or an ambiguity not resolved here, record it in the decision log (BRD header rule: *do not silently implement unspecified behavior*) and choose the most conservative option.
7. **Keep the generator a pure function**: `generateRoster(input, config) → outcome`. No I/O, no mutation of inputs, no reading of global state.

---

## 1. Summary of the delta

| # | Area | BRD v1.0 | Algorithm v2 | Why | Tier |
|---|---|---|---|---|---|
| 1 | Candidate unit | Pick best (day, shift) slot first, then pick an employee for it | Candidate is the triple **(employee, day, shift)**; only feasible triples are ever evaluated | Removes dead-ends (a top-ranked slot with no eligible employee) that BRD leaves unspecified | A |
| 2 | Ranking | Highest absolute *net benefit* | Rank by **density = ΔC ÷ shift duration**; stop rule remains on absolute ΔC | Correct under scarcity when shifts have different lengths (e.g. a 4 h peak shift next to 8 h defaults) | A |
| 3 | Shortage cost | Linear: every unmet staff-hour weighs `W_under` | The first person in an hour (hour with nobody) weighs `W_empty = 2·W_under`; further people weigh `W_under` | Under scarcity, an empty store-hour must be preferred over a second person in a busy hour; BRD ties these | A |
| 4 | Fairness | Utilization on raw maximum; tertiary tie-break; swap pass is "MAY" and unspecified | Fairness cost **F** on **effective capacity** against a proportional target share; used in tie-breaks (Tier A) and in a **mandatory** coverage-neutral refinement (Tier B) | Source requires a defined, consistently applied notion of "enough hours" and forbids near-zero hours while others are maxed | A + B |
| 5 | Refinement | None | Deterministic local search (ADD closure, DROP, MOVE, REPLACE) | Greedy has blind spots (overlapping shifts, imbalance) that cannot be corrected by ordering alone | B |
| 6 | Diagnostics | Shortage list, allocated/max | Adds capacity **lower bound**, per-slot **shortfall reasons**, per-employee **target vs actual**, decision **trace** | Separates unavoidable from avoidable shortage; satisfies "surface the outcome" | A |
| 7 | Rest gap | Out of scope | Optional soft term penalising evening→morning pairs, cyclic over the typical week | Human-quality rosters | C |
| 8 | N sensitivity, shift suggestions | None | Optional read-only analyses | Justify `N`; show the value of extra shift definitions without silently inventing them | C |
| 9 | Stop-rule semantics | Add while net benefit > 0 | **Unchanged in meaning** (add while ΔC < 0). AT-32 still holds | Compatibility | — |

---

## 2. Problem model

### 2.1 Sets and indices

| Symbol | Meaning | Default |
|---|---|---|
| `D` | Number of days in the typical week, indexed `d = 0..D-1` (Mon = 0 … Sun = 6) | 7 |
| `Hrs` | Operating hour buckets `h = open .. close-1`; bucket `h` spans `[h, h+1)` | 07..22 (16 buckets) |
| `S` | Shift definitions; shift `s` has whole-hour `start(s) < end(s)`, `dur(s) = end(s) − start(s)`; `cover(s,h) = [start(s) ≤ h < end(s)]` | two defaults |
| `E` | Employees in stable creation order, `i = 0..|E|-1`; `max_i` is a non-negative whole number of hours | — |
| slot | A pair `(d, s)` | — |
| assignment | A triple `(i, d, s)` | — |

**[DECISION D-19]** The internal model MUST take `D`, `open`, and `close` as parameters (defaults 7, 7, 23) rather than hard-coding them. The product behaviour is unchanged; this exists so that tests (§12) can run exhaustive oracles on tiny instances. The user interface continues to expose only the fixed Monday–Sunday, 07:00–23:00 week.

### 2.2 Parameters

| Name | Default | Meaning | Status |
|---|---|---|---|
| `N` | 20 | Transactions per employee-hour | [UNCHANGED] BR-05 |
| `L` | 1 | Daily shift limit | [UNCHANGED] |
| `wUnder` | 3 | Weight of one unmet staff-hour (second and later person in an hour) | [UNCHANGED value, refined use] |
| `wOver` | 1 | Weight of one excess staff-hour | [UNCHANGED] |
| `wEmpty` | `2·wUnder` = 6 | Weight of the **first** unmet person in an hour (hour with zero staff) | [NEW] |
| `restWeight` (μ) | 0 (disabled) | Penalty, in hour-equivalents, per rest violation. Recommended value when enabled: 8 | [NEW] Tier C |
| `restMinGapHours` (G) | 10 | Minimum hours between the end of a shift and the start of the next day's shift | [NEW] Tier C |
| `lowUtilizationRatio` | 1/2 | Threshold for the informational LOW_UTILIZATION flag (Appendix §6.4) | [CHANGED] |
| `maxPasses` | 50 | Maximum refinement passes | [NEW] |
| `maxMoves` | 5000 | Maximum accepted refinement moves (safety cap) | [NEW] |

**Constraints on parameters (MUST be validated at construction):** all integers; `wUnder > wOver ≥ 1`; `wEmpty ≥ wUnder`; `L ≥ 1`; `N ≥ 1`; `restWeight ≥ 0`.

**[DECISION D-20]** The weights are policy constants, not manager-facing settings, in the baseline. This resolves, for this release, the last item of the BRD §10.2 *Explicitly unresolved* list ("Should the trade-off weights … be adjustable by the manager, or remain fixed policy constants?"). Here BRD §10.2 means the top-level section, not BR-10's sub-heading 10.2. (Optional presets are described in §14 for a later release.)

### 2.3 Decision variables

`x[i,d,s] ∈ {0,1}` — employee `i` works shift `s` on day `d`.

### 2.4 Derived quantities

```
req[d,h]      = max(1, ceil(transactions[d,h] / N))                 // BR-05, UNCHANGED
staff[d,h]    = Σ_i Σ_s x[i,d,s] · cover(s,h)
hours[i]      = Σ_d Σ_s x[i,d,s] · dur(s)
totalHours    = Σ_i hours[i]
```

### 2.5 Hard constraints (generation)

A roster produced by generation MUST satisfy all of the following. In the current Python code, `validate_state` reports `OVER_WEEKLY_MAX` and `OVER_DAILY_SHIFT_LIMIT` as warnings for manual edits. Keep that public behavior. Extract or share the hard-rule predicates used by validation and `canAutoAssign`, and test that automatic feasibility accepts exactly the states with no H1–H5 breach. The conceptual `validate(profile=auto)` below means this equivalence; it does not require a new public validator profile.

| ID | Constraint |
|---|---|
| H1 | `hours[i] ≤ max_i` for every employee |
| H2 | `Σ_s x[i,d,s] ≤ L` for every employee and day |
| H3 | `x[i,d,s] + x[i,d,s'] ≤ 1` for every pair of overlapping shifts `s ≠ s'` (intervals `[start,end)`; touching boundaries do not overlap) |
| H4 | `x` is binary (no duplicate assignment) |
| H5 | Every assignment references an existing employee, shift, and day |

### 2.6 Objective part C — coverage cost (primary)

Define the weight of the *k*-th person required in an hour:

```
w_1 = wEmpty
w_k = wUnder            for k ≥ 2
```

Per-bucket cost for requirement `r = req[d,h]` and staffing `s = staff[d,h]`:

```
c(r, s) =  Σ_{k = s+1 .. r} w_k      if s < r        // weighted shortage
        +  wOver · max(0, s − r)                     // weighted excess
C(x)    =  Σ_{d,h} c(req[d,h], staff[d,h])
```

**Marginal cost of adding one person** to a bucket at staffing level `s`:

```
m(r, s) = −w_{s+1}   if s < r          // = −wEmpty when s = 0, −wUnder otherwise
        = +wOver     if s ≥ r
```

**Marginal cost of removing one person** from a bucket at staffing level `s ≥ 1`:

```
mRemove(r, s) = −m(r, s−1) = +w_s       if s ≤ r
                             −wOver     if s > r
```

**Slot deltas** (the only quantities the search needs):

```
slotAddDelta(d, s)    = Σ_{h : cover(s,h)} m(req[d,h], staff[d,h])
slotRemoveDelta(d, s) = Σ_{h : cover(s,h)} mRemove(req[d,h], staff[d,h])
excessAdded(d, s)     = #{ h : cover(s,h) and staff[d,h] ≥ req[d,h] }
```

Important properties (relied upon by the strategy in §4):

1. `m(r, ·)` is **non-decreasing** in `s` (−6, −3, −3, …, +1, +1 with defaults). Each additional person in a bucket therefore has diminishing value; `C` is convex per bucket.
2. `slotAddDelta` depends only on the slot and the current staffing grid — **not on which employee** is added. "Which slot" and "who" are separable decisions, but feasibility couples them (§4).
3. **Stop-rule threshold.** Adding one person to a full shift of `D_s` hours, of which `u` hours have a shortage weighted `wUnder` and `D_s − u` hours would be excess, has `ΔC = −wUnder·u + wOver·(D_s − u)`. This is negative iff `u > D_s · wOver / (wUnder + wOver)`. With defaults the person must be genuinely needed for **more than 25 %** of the shift. Hours in which the person would be the first on duty are weighted `wEmpty` and make the person more valuable.

   *Scope note.* `wEmpty` differentiates by **staffing level** (hour with nobody vs. hour with somebody), not by **demand intensity**. It therefore does **not** answer the BRD §10.2 question "Does the business value peak-hour shortages more heavily than other unmet staff-hours?", which remains unresolved; do not weight shortages by transaction volume.

### 2.7 Objective part F — fairness and softness (secondary)

**Effective capacity** `cap_i` — the largest sum of configured shift durations within `max_i` using at most `D·L` shifts (computed in §3.5). It is an upper bound on hours that can actually be placed because it ignores day and overlap constraints. Utilization is measured against `cap_i`, not `max_i`, because a person with `max = 20` and only 8-hour shifts can never exceed 16 h; 16/20 is "full", not "80 %".

**Target share.** With `Σcap = Σ_i cap_i` and `totalHours` the current total, the proportional target is:

```
target_i = totalHours · cap_i / Σcap
```

Equal utilization against `cap_i` means every employee sits at `target_i`.

**Fairness deviation** (integer-scaled by `Σcap` to avoid fractions):

```
Fdev(x) = Σ_i | hours[i]·Σcap − totalHours·cap_i |            // = Σcap × Σ_i |hours_i − target_i|
```

**Rest violations** (Tier C; zero when `restWeight = 0`):

```
restGap(a, b) = (24 − end(a)) + start(b)           // hours between shift a ending and shift b starting next day
R(x) = #{ (i, d, a, b) : x[i,d,a] = 1 ∧ x[i,(d+1) mod D,b] = 1 ∧ restGap(a,b) < G }
```

The modulo makes the week **cyclic**: Sunday→Monday counts, because the schedule is a reusable typical week. If `D = 1`, `R = 0`.

**Total secondary cost:**

```
F(x) = Fdev(x) + restWeight · Σcap · R(x)
```

If `Σcap = 0`, define `F = 0` (no employee can be auto-scheduled anyway). For display, `fairnessDeviationHours = Fdev / Σcap`.

### 2.8 Lexicographic comparison and acceptance rules

Solutions are compared by the pair **(C, F) in lexicographic order**: lower `C` always wins; `F` only breaks ties in `C`.

**[DECISION D-21]** Lexicographic rather than a weighted sum, because:
- it preserves the BRD stop-rule semantics exactly (AT-32 keeps passing) — fairness can never "buy" an assignment with no coverage value, and cannot cost even one unit of coverage cost;
- it removes a calibration parameter (λ) whose scale would otherwise interact with `wOver`;
- it keeps behaviour explainable: *coverage first, then excess, then fairness.*
- it follows BR-06 §6.2: utilization parity must not be bought by knowingly introducing a materially worse staffing shortage.

| Move | Accept iff |
|---|---|
| ADD | `ΔC < 0` |
| DROP | `ΔC < 0` |
| MOVE | `ΔC < 0`, or `ΔC = 0 ∧ ΔF < 0` |
| REPLACE (swap assignee) | `ΔC = 0` (always true) `∧ ΔF < 0` |

Because `C` and `F` are integers bounded below, and every accepted move strictly decreases `(C, F)` lexicographically, refinement **terminates** (§5.4).

### 2.9 Reported metrics versus optimizer cost

- All metrics shown to the manager (unmet, excess, covered, coverage rate, ratios) keep the **linear** definitions of BR-10 §10.1. [UNCHANGED]
- `C` and `F` are *optimizer costs*. They MAY be shown in a diagnostics/"how this was generated" panel, labelled "optimizer cost", but MUST NOT replace or be confused with the BRD metrics. The README MUST state in one sentence that the optimizer weights the first person in an empty hour more heavily than reported metrics do.

---

## 3. Phase 0 — Preparation

**Purpose.** Validate prerequisites, precompute immutable lookup tables, compute effective capacities and the capacity lower bound.

**Inputs.** Schedule demand, employees, shifts, config. **Outputs.** `req`, `cover` masks, `dur`, ordering, `cap_i`, `Σcap`, `lowerBound`, or a *blocked* outcome.

### 3.1 Prerequisite checks [UNCHANGED, restated]

Return `blocked` with an actionable message (BR-01, BR-06, and the top-level BRD §6.3 "Important states" table) if any of:
- no valid demand imported → `NO_DEMAND`
- no shift definitions → `NO_SHIFTS`
- no employee with `cap_i > 0` → `NO_ELIGIBLE_STAFF` (message distinguishes "no employees" from "all employees have a maximum below the shortest shift")

These are pure-generator outcome codes. The existing `ScheduleService` boundary continues to raise `SchedulingError` with `MISSING_DEMAND`, `MISSING_SHIFTS`, and `NO_ELIGIBLE_EMPLOYEE`, respectively; the adapter maps the pure blocked outcome to those legacy codes and preserves the current state on failure.

### 3.2 Canonical ordering

- Employees ordered by creation order (`orderIndex`), ties by id.
- Days ascending 0..D-1.
- Shifts ordered by `(start, end, id)`.

All iteration, tie-breaking, and trace output MUST use these orders (see §8).

### 3.3 Demand

Compute `req[d,h]` exactly as BR-05. No smoothing, no fractional demand. **[DECISION D-22]** Smoothing is deliberately omitted: with 8-hour shifts, the shift-level cost already averages hourly noise.

### 3.4 Shift tables

Precompute for each shift: `dur(s)`, the list of covered bucket indices, and a pairwise `overlaps[s][s']` boolean matrix.

### 3.5 Effective capacity

```
function effectiveCapacity(maxHours, durations, maxShifts):
    // minShifts[h] = fewest shifts whose durations sum to exactly h (∞ if impossible)
    minShifts = array(maxHours + 1, ∞);  minShifts[0] = 0
    for h in 1..maxHours:
        for dur in durations:
            if h ≥ dur and minShifts[h − dur] + 1 < minShifts[h]:
                minShifts[h] = minShifts[h − dur] + 1
    best = 0
    for h in 0..maxHours:
        if minShifts[h] ≤ maxShifts: best = h
    return best
```

Call with `maxShifts = D · L`. This ignores same-day overlap structure, therefore `cap_i` is a valid **upper bound** on achievable hours (which is all that Phase 3's lower bound and the fairness target need). The pseudo-code describes the result, not a required allocation strategy: the current API accepts weekly maxima through `2^31 − 1`, and implementation MUST retain that range without allocating `maxHours + 1` entries or imposing a smaller silent cap. Use an exact resource-bounded method for the same `cap_i` value and validate it against this recurrence on tractable inputs. Its performance and memory bounds must be stated and tested for the API maximum.

### 3.6 Capacity lower bound

```
requiredHours   = Σ_{d,h} req[d,h]
capacityHours   = Σ_i cap_i
unavoidableUnmet = max(0, requiredHours − capacityHours)
```

Validity: each scheduled person-hour covers at most one required staff-hour, so `covered ≤ min(requiredHours, capacityHours)` and `unmet ≥ requiredHours − capacityHours` for **any** feasible roster. This is reported in Phase 3.

### 3.7 Strategy notes

- *Why compute `cap_i`:* fairness against raw `max_i` mislabels people who cannot take another shift as "under-used" (BRD §5.5 names the concept of *schedulable capacity* but does not operationalise it).
- *Failure modes:* all `cap_i = 0` → blocked (3.1); `Σcap` small relative to `requiredHours` → generation proceeds, partial roster, lower bound explains the gap.

---

## 4. Phase 1 — Construction (greedy over feasible triples)

**Purpose.** Build a demand-aware starting roster quickly, deterministically, and explainably.

**Strategy.** Repeatedly add the single most valuable *feasible* assignment until no feasible assignment reduces coverage cost `C`. Value is measured **per hour of employee capacity consumed**, and the stop rule is measured in absolute cost.

### 4.1 State

Maintain incrementally (never recompute from scratch inside loops):

```
staff[d][hIdx]            int grid
hours[i]                  int
totalHours                int
assigned[i][d][s]         boolean
shiftsOn[i][d]            list of shift indices
```

Operations: `add(i,d,s)`, `remove(i,d,s)` (both update all of the above in `O(dur)`), `slotAddDelta`, `slotRemoveDelta`, `excessAdded`, `canAutoAssign`, `computeF`, `deltaF`.

### 4.2 Feasibility

```
function canAutoAssign(state, i, d, s):
    return  not assigned[i][d][s]                                  // H4
        and hours[i] + dur(s) ≤ max_i                              // H1
        and len(shiftsOn[i][d]) + 1 ≤ L                            // H2
        and not any(overlaps[s][t] for t in shiftsOn[i][d])        // H3
```

This function MUST be equivalent to the shared H1–H5 hard-rule predicates used by `validate_state` (guarded by test AT-43, §12). Keep the existing manual-warning severity behavior; an incremental implementation is allowed (and expected) for speed.

### 4.3 Candidate selection

Per iteration, evaluate **slots** that have at least one feasible employee and a strictly negative `slotAddDelta`:

```
function constructStep(state):
    slots = []
    for d in days:
        for s in shiftsOrdered:
            feasible = [i in employeesOrdered if canAutoAssign(state, i, d, s)]
            if feasible is empty: continue
            dC = slotAddDelta(state, d, s)
            if dC ≥ 0: continue                   // per-slot stop rule
            slots.push({d, s, dC, dur: dur(s), ex: excessAdded(state, d, s), feasible})
    if slots is empty: return null                // global stop rule

    // Key 1: density.  a beats b  ⇔  a.dC · b.dur  <  b.dC · a.dur   (integer cross-multiplication)
    // Key 2: lower excessAdded.
    bestSlots = all slots tying with the minimum on (density, excessAdded)

    // Key 3: ΔF of the concrete (employee, slot) pair.   Key 4+: fixed order.
    pick = argmin over (slot in bestSlots, i in slot.feasible) of
               (deltaF(state, i, slot.d, slot.s), employeeOrder(i), slot.d, shiftOrder(slot.s))
    return pick
```

```
function construct(state, cfg, trace):
    added = 0
    while (pick = constructStep(state)) != null:
        add(state, pick.i, pick.d, pick.s)
        trace.push({phase: construct, move: ADD, ..., deltaC: pick.dC, deltaF: pick.dF})
        added += 1
    return added
```

`ΔF` is computed only for the (small) tied set, by temporarily applying the add, recomputing `F` in `O(|E| + rest-check)`, and reverting.

### 4.4 Why each design choice

| Choice | Reason | Failure mode it prevents |
|---|---|---|
| Triples instead of slot-then-employee | Feasibility couples slot and person | A top slot with nobody eligible stalls or mis-orders the algorithm |
| Density ranking | Under scarcity, the scarce resource is contract hours, not assignments | An 8 h shift always beating a 4 h shift of higher value per hour; see Example C |
| `wEmpty = 2·wUnder` | Concavity: first person in an hour is most valuable | An empty quiet slot tied with a second person in a busy slot; see Example B |
| Stop on `ΔC ≥ 0` (absolute) | Preserves BRD stop rule | Over-staffing to fill capacity |
| ΔF as tie-break | Spreads work proportionally from the very first assignment | Staff at the top of the list collecting all early (busiest) slots |
| Fixed order as last key | Reproducibility | Nondeterminism |

### 4.5 Complexity

Iterations ≤ total feasible assignments `≈ Σ_i max_i / minDur ≤ |E|·D·L`. Per iteration `O(D·|S|·dur + |E|·D·|S|)` plus ΔF on the tied set. For 50 employees × 7 days × 10 shifts this is on the order of 10⁶–10⁷ elementary operations in total (well under a second; typically milliseconds).

### 4.6 Postconditions

- All hard constraints H1–H5 hold.
- No *feasible* addition with `ΔC < 0` exists (construction local optimality with respect to ADD).
- Unused capacity is allowed and expected.

---

## 5. Phase 2 — Refinement (deterministic local search)

**Purpose.** Repair what greedy construction cannot see: imbalance between employees (the source requirement "nobody near-zero while others are maxed"), assignments made obsolete by later overlapping shifts, and badly positioned assignments.

**Strategy.** First-improvement hill-climbing on the lexicographic `(C, F)` objective, over a small set of moves evaluated in a **fixed order**, with every move checked by the same feasibility function as construction. No randomness, no restarts, no annealing — chosen for reproducibility (INV-16) and explainability.

### 5.1 Moves

| Move | Definition | Effect on C | Typical purpose |
|---|---|---|---|
| **ADD** | Re-run `construct` on the current state | `ΔC < 0` | Closure: new additions may become valuable after DROP/MOVE |
| **DROP** `(i,d,s)` | Remove one assignment | accept iff `slotRemoveDelta < 0` | Remove an assignment made net-harmful by later (overlapping) additions |
| **MOVE** `(i,d,s) → (d',s')` | Relocate one employee's assignment to another feasible slot | `ΔC = removeDelta + addDelta (on post-removal grid)` | Re-position coverage; relieve rest violations |
| **REPLACE** `(i→j, d, s)` | Replace the assignee of a slot by another employee | `ΔC = 0` always | **Fairness repair**: shift hours from the over-target to the under-target employee; rest repair |

### 5.2 Procedure

```
function refine(state, cfg, trace):
    accepted = 0
    for pass in 1..cfg.maxPasses:
        changed = false
        changed |= construct(state, cfg, trace) > 0              // ADD closure
        changed |= tryDrops(state, cfg, trace)
        changed |= tryMoves(state, cfg, trace)
        changed |= tryReplacements(state, cfg, trace)
        if not changed: break
        accepted = trace.countAccepted(refine)
        if accepted ≥ cfg.maxMoves: break
    return state
```

```
function tryDrops(state):
    changed = false
    for a in snapshot(assignments ordered by (employee, day, shiftOrder)):
        if not state.has(a): continue
        if slotRemoveDelta(state, a.d, a.s) < 0:
            remove(state, a); record DROP; changed = true
    return changed
```

```
function tryMoves(state):
    changed = false
    for a in snapshot(assignments ordered by (employee, day, shiftOrder)):
        if not state.has(a): continue
        before = (C(state), F(state))                      // incremental
        remove(state, a)
        best = null
        for (d', s') in slotsOrdered, (d', s') ≠ (a.d, a.s):
            if canAutoAssign(state, a.i, d', s'):
                (dC, dF) = deltaOf(before, state after add(a.i, d', s'))
                keep the minimum by (dC, dF, d', shiftOrder(s'))
        if best != null and (best.dC < 0 or (best.dC == 0 and best.dF < 0)):
            add(state, a.i, best.d', best.s'); record MOVE; changed = true
        else:
            add(state, a.i, a.d, a.s)                       // restore
    return changed
```

```
function tryReplacements(state):
    changed = false
    for slot (d, s) in slotsOrdered:
        for a in snapshot(assignees of slot, in employee order):
            if not state.has(a): continue
            beforeF = F(state)
            remove(state, a)
            best = null
            for j in employeesOrdered, j ≠ a.i, not assigned[j][d][s]:
                if canAutoAssign(state, j, d, s):
                    dF = F(after add(j,d,s)) − beforeF       // incremental O(1) for the hours term
                    keep the minimum by (dF, employeeOrder(j))
            if best != null and best.dF < 0:
                add(state, best.j, d, s); record REPLACE; changed = true
            else:
                add(state, a.i, d, s)
    return changed
```

*Notes.*
- After a REPLACE, coverage is unchanged by construction (the slot keeps the same headcount), so only `F` is evaluated.
- For REPLACE, `totalHours` is unchanged when durations are equal (always: same slot). The hours term of `ΔF` therefore touches only two employees and can be updated in `O(1)`; the rest term needs the two employees' neighbouring days only.
- "Snapshot" means iterate over a copy taken at the start of the function, skipping entries removed by earlier accepted moves.

### 5.3 Why these moves, and what is deliberately omitted

- **REPLACE is the mechanism that fulfils the fairness requirement.** It converts "someone has 0 h while someone else is at 100 % of effective capacity" into a coverage-neutral transfer (Example E).
- **DROP and MOVE** matter mainly when the manager has defined overlapping shifts (e.g. a 10:00–14:00 peak shift next to the defaults), where earlier greedy decisions can become suboptimal.
- **Omitted on purpose:** cross-slot 2-exchange, simulated annealing, random restarts, tabu search. They add code, risk nondeterminism, and are hard to explain in a code walkthrough. They are listed in §14 as future hooks.

### 5.4 Termination and safety

- Every accepted move strictly decreases the integer pair `(C, F)` in lexicographic order; both are bounded below by 0; hence the process terminates.
- Independently, `maxPasses` and `maxMoves` bound the work. **Do not use wall-clock timeouts** (§8). If either cap is hit, return the current (valid) roster and set a flag `refinementCapped = true` in the result.
- Every move re-checks feasibility through `canAutoAssign`, so H1–H5 hold at every intermediate state.

### 5.5 Postconditions

- H1–H5 hold.
- `(C, F)` after refinement `≤` `(C, F)` after construction, lexicographically; in particular **`C` never increases**.
- No feasible ADD with `ΔC < 0` exists.
- No feasible REPLACE with `ΔF < 0` exists (unless `maxPasses`/`maxMoves` was hit).

---

## 6. Phase 3 — Diagnostics and explainability

**Purpose.** Never fail silently (source §4). Tell the manager what was achieved, what could not be, and *why*.

### 6.1 Outputs

The generator returns, in addition to the roster:

1. **Metrics** — all BR-10 §10.1 values, computed by the existing metrics module. [UNCHANGED]
2. **Employee report** — per employee: `hours`, `max`, `effectiveCapacity`, `utilizationRaw = hours / max` (`"N/A"` if `max = 0`), `utilizationEffective = hours / cap` (`"N/A"` if `cap = 0`), `targetHours` (display, one decimal), `deviationHours`.
3. **Shortfall report** — per configured slot with unmet staff-hours, plus each unmet operating hour outside every configured shift: a reason code (§6.2).
4. **Capacity lower bound** (§3.6).
5. **Flags** (§6.4).
6. **Trace** — ordered list of accepted decisions for explanation and tests (§6.5).
7. **Cost summary** — `C`, `F`, `fairnessDeviationHours`, `restViolations`, `refinementCapped`.

### 6.2 Shortfall reason codes

For each slot `(d,s)` whose covered buckets contain any unmet staff-hours:

```
function reasonFor(state, d, s):
    if no employee has cap_i > 0:                          return NO_ELIGIBLE_STAFF
    if slotAddDelta(state, d, s) ≥ 0:                      return STOP_RULE
    if no employee has hours[i] + dur(s) ≤ max_i:          return CAPACITY
    return DAY_CONSTRAINTS
```

| Code | Manager-facing meaning |
|---|---|
| `STOP_RULE` | Adding one more person to this shift would create more weighted excess than weighted shortage removed. The gap is a deliberate trade-off (example message: "Adding a person here would be idle for most of the shift"). |
| `CAPACITY` | Every employee who could work this shift has no contract hours left for it. |
| `DAY_CONSTRAINTS` | Someone has hours left but is blocked that day by the daily limit, an overlapping shift, or is already on this shift. |
| `NO_ELIGIBLE_STAFF` | No employee can be auto-scheduled at all. |
| `NO_SHIFT_COVERAGE` | No configured shift covers this unmet operating hour. This code belongs to an hour-level record `(d,h)`, not a shift slot. |

For every unmet operating hour `(d,h)` outside the union of configured shift windows, emit one hour-level `NO_SHIFT_COVERAGE` record. Do not emit an hour-level record for an hour covered by at least one configured shift; its unmet demand remains in the existing hourly metrics and the relevant slot reports. Do not double-count hourly unmet demand when displaying overlapping slot reports.

**Guarantee:** after Phase 2, every configured slot with unmet hours receives exactly one slot reason code (`ΔC < 0` plus any employee with free hours and no day-constraint block would contradict ADD local optimality), and every unmet hour with no configured shift receives exactly one `NO_SHIFT_COVERAGE` record.

### 6.3 Lower-bound statement

Report: *"At least `unavoidableUnmet` of `totalUnmet` unmet staff-hours cannot be avoided with the current staff capacity."* The remainder (`totalUnmet − unavoidableUnmet`) is **not** claimed to be avoidable: it can come from shift granularity, indivisible shifts, day constraints, or the stop rule. The UI/README MUST NOT label it "algorithm error".

### 6.4 Flags

| Flag | Condition | Severity |
|---|---|---|
| `LOW_UTILIZATION` [CHANGED definition] | `utilizationEffective_i < lowUtilizationRatio × mean(utilizationEffective over employees with cap > 0)` and the mean > 0 | Informational |
| `NEAR_ZERO_WHILE_OTHERS_FULL` [NEW] | ∃ employee `i` with `cap_i > 0` and `hours_i ≤ min_s dur(s)` while ∃ employee `j` with `utilizationEffective_j ≥ 0.9`; attach the cause "no coverage-neutral reassignment exists" | Informational (should be rare after Phase 2; it indicates a structural cause, e.g. day constraints) |
| `REFINEMENT_CAPPED` | `maxPasses` or `maxMoves` reached | Informational |

### 6.5 Trace

```
interface TraceStep {
  seq: number;
  phase: 'construct' | 'refine';
  move: 'ADD' | 'DROP' | 'MOVE' | 'REPLACE';
  employeeId: string;
  day: number;            // destination day
  shiftId: string;        // destination shift
  fromDay?: number; fromShiftId?: string;   // for MOVE
  replacedEmployeeId?: string;              // for REPLACE
  deltaC: number; deltaF: number;
  note: string;           // short human-readable reason, e.g. "removes 6 unmet h, adds 2 excess h"
}
```

The trace SHOULD be bounded by `maxMoves + iterations` and MAY be omitted from persisted storage (regenerate on demand). The UI MAY show "Why was this assignment made?" from it; this is optional.

### 6.6 Minimum UI surface (Tier A)

Keep UI changes small:
- In the existing generation summary: add the lower-bound sentence, per-slot shortfall reasons, and uncovered-hour `NO_SHIFT_COVERAGE` reasons (grouped by contiguous range where BR-10 §10.3 allows).
- In the staff panel: keep `hours / max h` as in the BRD; during a current generation result or preview, add a tooltip or secondary label showing effective capacity and target hours (e.g. "16 / 20 h — full for 8 h shifts").
- Show generation-specific trace, costs, flags, and shortfall reasons only with the current generation result or preview. Clear them on reload and after a manual edit; do not persist or present stale diagnostics as if they described the edited roster. Existing current-state linear metrics remain visible as usual.
- README: algorithm section (see §11, Step 8).

---

## 7. Tier C — Optional analyses

Implement only after Tiers A and B are complete, tested, and merged.

### 7.1 Rest-gap term (`restWeight > 0`)

Already specified in §2.7 (`R(x)`) and enters `F` and `ΔF`. Implementation notes:
- Compute `R` incrementally: adding/removing assignment `(i,d,a)` only affects pairs `(i, d−1, ·, a)` and `(i, d, a, ·→ d+1)`, indices modulo `D`.
- Default remains `restWeight = 0`, i.e. **off**. When on, document it in the README as an opt-in soft preference, not a labour-law rule (the BRD §10.2 *Explicitly unresolved* list still includes legal rest-period rules).
- Recommended experimentation value: `restWeight = 8`, `restMinGapHours = 10`. With the default shifts, `15:00–23:00` followed by `07:00–15:00` the next day has `restGap = 1 + 7 = 8 < 10` and counts as a violation.

### 7.2 Sensitivity of `N`

Pure function of demand and `cap_i`: for `N ∈ {15, 20, 25, 30}` report `requiredHours(N)` and `requiredHours(N) / capacityHours`. Display next to the `N` setting. In the README justify the default as:

```
N = 60 × targetOccupancy ÷ averageServiceMinutes
```

`N = 20` corresponds to ≈ 3 minutes per transaction at 100 % occupancy; the `ceil` in BR-05 supplies the buffer that makes this defensible. State clearly that `N` is an assumption, not a measurement.

### 7.3 Shift suggestions (read-only)

For candidate windows of 4 and 5 whole hours inside the operating window that do not duplicate an existing shift (≈ 25 candidates), run `construct` only (skip refinement) on `shifts ∪ {candidate}` and report `ΔC`, `Δunmet`, `Δexcess` against the current baseline run. Show the top three with `ΔC < 0` as *suggestions*. The system MUST NOT create or apply a shift automatically (BR-06 §6.1: "must honor the actual shifts configured"). Trigger on user action only; never on every edit.

### 7.4 Baseline comparison harness (dev tool)

Optionally retain the BRD v1.0 greedy as a non-user-facing strategy (`strategy: 'brd-v1'`) in a script that prints `(unmet, excess, fairnessDeviationHours, restViolations)` for both strategies on the sample CSV. Useful for the README's "approach and trade-offs" discussion; not required.

---

## 8. Determinism and numerical rules

These make INV-16 (reproducibility) hold across runs and platforms. All are **MUST**.

1. **Integer arithmetic only** in `C`, `F`, deltas, and comparisons. Density comparison uses cross-multiplication (`a.dC · b.dur < b.dC · a.dur`). `F` is scaled by `Σcap` (§2.7); never divide inside the search. Values stay far below 2⁵³ (e.g. `hours·Σcap ≲ 56 · 2800`).
2. **No randomness**, including random tie-breaking and shuffling.
3. **No wall-clock or timer-based termination.** Use the `maxPasses`/`maxMoves` counters only.
4. **Fixed iteration order** from §3.2 everywhere; never iterate over hash-map/set key order or rely on object-key insertion order for decisions — use arrays sorted by the canonical keys.
5. **Tie-break chain** in construction: density → `excessAdded` → `ΔF` → employee order → day → shift order. In refinement: `ΔC` → `ΔF` → destination day → shift order (MOVE); `ΔF` → employee order (REPLACE).
6. **Pure function**: inputs are not mutated; internal state is local to the call.
7. **Same inputs ⇒ identical assignments, metrics, cost, flags, and trace.** The order of the input employee array is part of the input (it defines employee order).

---

## 9. Interfaces and module layout

The stack is the implementer's choice. The following is a suggested decomposition; map it to existing files.

| Module | Responsibility |
|---|---|
| `config` | `GenerationConfig` defaults and parameter validation (§2.2) |
| `demand` | `req[d][h]` from transactions and `N` (existing BR-05 code; reuse) |
| `capacity` | `effectiveCapacity`, lower bound (§3.5–3.6) |
| `cost` | `m`, `mRemove`, `slotAddDelta`, `slotRemoveDelta`, `excessAdded`, `computeC`, `computeF`, `deltaF`, `restViolations` (§2.6–2.7) — **pure, side-effect free, shared by generator and tests** |
| `state` | Incremental `State`, `add`, `remove`, `canAutoAssign` (§4.1–4.2) |
| `construct` | `constructStep`, `construct` (§4) |
| `refine` | `tryDrops`, `tryMoves`, `tryReplacements`, `refine` (§5) |
| `diagnostics` | Employee report, shortfall reasons, lower-bound statement, flags (§6) |
| `generate` | Orchestrates phases 0 → 3; the only public entry point |
| `validate` | **Existing** public manual-edit behavior; share H1–H5 hard-rule predicates with `canAutoAssign` and test their equivalence |

```ts
type Id = string;

interface Shift      { id: Id; start: number; end: number }          // whole hours
interface Employee   { id: Id; name: string; maxHours: number; orderIndex: number }
interface Assignment { employeeId: Id; day: number; shiftId: Id }

interface GenerationConfig {
  N: number;                    // BR-05
  dailyShiftLimit: number;      // L
  wUnder: number;               // 3
  wOver: number;                // 1
  wEmpty: number;               // 2 * wUnder
  restWeight: number;           // 0 = off
  restMinGapHours: number;      // 10
  lowUtilizationRatio: number;  // 0.5
  maxPasses: number;            // 50
  maxMoves: number;             // 5000
}

interface GenerationInput {
  days: number;                 // 7 in production
  openHour: number;             // 7
  closeHour: number;            // 23
  employees: Employee[];        // order = tie-break order
  shifts: Shift[];
  transactions: number[][];     // [day][hourIndex]
}

type BlockReason = 'NO_DEMAND' | 'NO_SHIFTS' | 'NO_ELIGIBLE_STAFF';

type GenerationOutcome =
  | { status: 'blocked'; reason: BlockReason; message: string }
  | { status: 'ok'; result: GenerationResult };

interface GenerationResult {
  assignments: Assignment[];
  cost: { C: number; F: number; fairnessDeviationHours: number; restViolations: number; refinementCapped: boolean };
  metrics: CoverageMetrics;               // existing BR-10 §10.1 type
  employees: EmployeeReport[];
  shortfalls: ShortfallReport[];
  lowerBound: { requiredHours: number; effectiveCapacityHours: number; unavoidableUnmetHours: number };
  flags: Flag[];
  trace: TraceStep[];
}

interface EmployeeReport {
  employeeId: Id; hours: number; maxHours: number; effectiveCapacity: number;
  utilizationRaw: number | 'N/A'; utilizationEffective: number | 'N/A';
  targetHours: number; deviationHours: number;
}

type ShortfallReport =
  | { kind: 'slot'; day: number; shiftId: Id; unmetStaffHours: number;
      reason: 'STOP_RULE' | 'CAPACITY' | 'DAY_CONSTRAINTS' | 'NO_ELIGIBLE_STAFF' }
  | { kind: 'uncovered_hour'; day: number; hour: number; unmetStaffHours: number;
      reason: 'NO_SHIFT_COVERAGE' };
```

**Integration rules**
- Manual edits, regeneration confirmation, import, shift/staff CRUD, and metric recomputation keep their existing code paths. The generator's only touchpoints are: reading schedule data, returning a `GenerationOutcome`, and the UI rendering the extra diagnostics.
- The pure generator uses the new blocked outcome codes. The Python service adapter preserves its existing `SchedulingError` codes: `NO_DEMAND` → `MISSING_DEMAND`, `NO_SHIFTS` → `MISSING_SHIFTS`, and `NO_ELIGIBLE_STAFF` → `NO_ELIGIBLE_EMPLOYEE`.
- Generation diagnostics are transient output for the current generation result or preview, including confirmed refresh. A later reload or manual edit shows current linear metrics without generation-specific diagnostics. No schema or persistence change is required.
- `generate` always starts from an **empty roster** (BR-09 replaces assignments). `refine` additionally accepts an arbitrary *feasible* initial roster for testing; it MUST assert H1–H5 on entry.

---

## 10. Worked examples (normative for tests)

### Example A — Stop rule with the new marginals (reproduces AT-32)

One shift 07:00–15:00, hourly requirement `[1,2,2,3,4,4,3,2]`, defaults `wUnder=3, wOver=1, wEmpty=6`.

| Add # | Staffing before | Per-hour marginals | `ΔC` | Decision |
|---|---|---|---|---|
| 1 | all 0 | 8 × (−6) | **−48** | add |
| 2 | all 1 | 7 × (−3) + 1 × (+1) | **−20** | add |
| 3 | all 2 | 4 × (−3) + 4 × (+1) | **−8** | add |
| 4 | all 3 | 2 × (−3) + 6 × (+1) | **0** | **stop** (`ΔC ≥ 0`) |

Result: 3 employees; unmet = 2, excess = 5; `C = 2·3 + 5·1 = 11`.
With `wUnder = 4, wEmpty = 8`: add #4 has `ΔC = 2 × (−4) + 6 = −2 < 0`, so a fourth employee **is** added. (Matches AT-32.)

### Example B — Empty hour beats second person in a busy hour

Employees E1, E2 (each `max = 8`), one shift 07:00–15:00, `L = 1`. Requirement: Monday `2` in every covered hour; every other day `1`. Only two shifts of capacity exist.

- Add #1 (any day): Monday `8 × (−6) = −48`; other days `−48` (tie → fixed order → Monday).
- Add #2: second person on Monday `8 × (−3) = −24`; first person on Tuesday `8 × (−6) = −48` → **Tuesday**.

Expected roster: Monday 1 person, Tuesday 1 person; **no day has 2 people**. Under BRD linear weights the choice at step 2 is a tie (24 vs 24) resolved arbitrarily and could leave Tuesday empty. (Test AT-38.)

### Example C — Density ranking with a 4-hour peak shift

Shifts `M = 07:00–15:00` and `P = 10:00–14:00`. On both Monday and Tuesday the state is pre-populated with **2 staff on M**. Requirement per hour 07..14: `[2,2,3,3,3,3,3,3]`. One extra employee X with `max = 8` remains. (Unit-test the ranking function on this fixed state; end-to-end generation would first spread E1/E2 elsewhere.)

| Candidate | Calculation | `ΔC` | Density |
|---|---|---|---|
| Third person on M | hours 09–14: 6 × (−3); hours 07–08: 2 × (+1) | −16 | −2 per h |
| Person X on P | hours 10–13: 4 × (−3) | −12 | **−3 per h** |

Density chooses **P** (Monday by fixed order), then P again on Tuesday (X has 4 h left): total `ΔC = −24`. Absolute-benefit ranking (BRD) would choose M (−16) and exhaust X's hours: total `−16`. (Test AT-39.)

### Example D — Effective capacity

| Shift durations | `max` | `D·L` | `cap` |
|---|---|---|---|
| {8} | 20 | 7 | 16 |
| {8} | 12 | 7 | 8 |
| {8} | 7 | 7 | 0 |
| {8} | 60 | 7 | 56 (7 shifts is the ceiling) |
| {8, 4} | 20 | 7 | 20 |
| {8, 4} | 23 | 7 | 20 |
| {8, 4} | 10 | 7 | 8 |

### Example E — Fairness deviation and the REPLACE repair

Employees (all shifts 8 h): Alice `cap = 40`, Bob `cap = 32`, Diana `cap = 16`; `Σcap = 88`.

Initial hours: Alice 40, Bob 8, Diana 0; `totalHours = 48`.

| Employee | `hours·88` | `48·cap` | `|diff|` |
|---|---|---|---|
| Alice | 3520 | 1920 | 1600 |
| Bob | 704 | 1536 | 832 |
| Diana | 0 | 768 | 768 |
| **Fdev** | | | **3200** (≈ 36.4 h) |

REPLACE one of Alice's shifts by Diana on the same slot (`ΔC = 0`): Alice 32, Bob 8, Diana 8.

| Employee | `hours·88` | `48·cap` | `|diff|` |
|---|---|---|---|
| Alice | 2816 | 1920 | 896 |
| Bob | 704 | 1536 | 832 |
| Diana | 704 | 768 | 64 |
| **Fdev** | | | **1792** (≈ 20.4 h) |

`ΔF = −1408 < 0` → accepted. This is exactly the case "Diana at 0 h while Alice is maxed". (Test AT-37.)

A *rejected* example from the balanced state Alice 24, Bob 16, Diana 8: moving one shift Alice→Diana gives 16/16/16 and raises `Fdev` from 384 to 1280, so it is not accepted.

### Example F — Rest violation (Tier C)

Alice works Monday `15:00–23:00` and Tuesday `07:00–15:00`: `restGap = (24 − 23) + 7 = 8 < 10` → `R = 1`. Sunday `15:00–23:00` followed by Monday `07:00–15:00` also counts (cyclic). With `restWeight = 8`, REPLACE of Alice's Tuesday shift by an otherwise-equal colleague, which keeps hours symmetric and removes the violation, has `ΔF < 0` and is accepted. (Test AT-42; choose hours so the fairness term is unchanged.)

### Example G — Lower bound

Four employees, `max = 24` each, 8 h shifts: `cap_i = 24`, `Σcap = 96`. With `requiredHours = 112` (the minimum one-person rule), `unavoidableUnmet = 16`. (Matches BRD Example C.) With `requiredHours = 250` the bound is 154.

---

## 11. Implementation plan

Each step ends with all pre-existing tests green plus the tests named in the step.

| Step | Tier | Work | Definition of done |
|---|---|---|---|
| 1 | A | **Config and model parameterisation.** Introduce `GenerationConfig` and parameter validation; make `days/openHour/closeHour` parameters internally (defaults unchanged). No behaviour change. | Existing suite passes; config validation unit tests |
| 2 | A | **`cost` module.** Implement `m`, `mRemove`, `slotAddDelta`, `slotRemoveDelta`, `excessAdded`, `computeC`, `computeF`, `restViolations`, `deltaF`. | Tests reproduce Example A marginals, Example E table, Example F |
| 3 | A | **`capacity` module.** `effectiveCapacity`, lower bound. | Example D table and Example G pass |
| 4 | A | **`state` module.** Incremental state, `canAutoAssign`, and shared H1–H5 predicates with existing validation. | AT-43: incremental feasibility ≡ shared hard rules on random states; manual warning severities unchanged |
| 5 | A | **`construct`.** Replace the BRD greedy as the generator's core. Keep the old implementation only if needed behind a dev flag (§7.4). | AT-32 (both variants), AT-34, AT-35, AT-38, AT-39 pass; AT-09/10/11/25 still pass |
| 6 | B | **`refine`.** Implement ADD closure, DROP, MOVE, REPLACE with caps. | AT-36, AT-37 pass; refinement never increases `C`; terminates on all random instances |
| 7 | A | **Diagnostics.** Employee report, slot and uncovered-hour shortfall reasons, lower bound, flags, trace. | AT-41 passes; both guarantees in §6.2 hold on random instances |
| 8 | A | **UI and README.** Extend the generation summary (§6.6). README "Auto-scheduler" section: demand model and `N` justification, the lexicographic objective and stop rule (25 % threshold in plain words), effective capacity and fairness definition ("enough hours" = proportional target share, repaired by coverage-neutral swaps), determinism, limitations (§15). Update the AI-usage note if applicable. | Manual walkthrough on the sample CSV; README matches behaviour |
| 9 | C | Optional follow-up only after required Tiers A/B: rest-gap (§7.1), `N` sensitivity (§7.2), shift suggestions (§7.3), comparison harness (§7.4) — any subset | AT-42 / AT-45 only for implemented parts |

**Out of scope for every step:** changing validation severities, import rules, metric formulas, manual-edit semantics, or persistence format. Generation-specific diagnostics are transient.

---

## 12. Test plan (additions to BRD §9.2)

New scenarios continue the BRD numbering. Priorities follow the P0/P1/P2 definitions in BRD §9.2; **finish all P0 before starting P1**.

| ID | Priority | Scenario | Expected result |
|---|---|---|---|
| AT-34 | P0 | Property test: generated rosters over many seeded random instances | H1–H5 hold (weekly max, daily limit, no overlap, no duplicate, valid references); `covered ≤ required` per bucket; ratios finite or "–" |
| AT-35 | P0 | Run the generator twice on identical input | Identical assignments, metrics, cost, flags, trace |
| AT-36 | P0 | Refinement monotonicity over the same random instances | `C_refined ≤ C_constructed`; `(C,F)` lexicographically `≤`; refinement terminates; no feasible ADD with `ΔC < 0` remains |
| AT-37 | P0 | Example E: feed `refine` the imbalanced roster | One slot's assignee is replaced Alice→Diana; `C` unchanged; `F` decreases |
| AT-38 | P1 | Example B: empty-hour priority | One person on Monday, one person on another day; no day with two |
| AT-39 | P1 | Example C: ranking on the fixed pre-populated state | P is ranked first; sequence P(Mon), P(Tue) |
| AT-40 | P0 | Example D: effective capacity table, plus `max = 0` | All rows match; `cap = 0` employees are never auto-assigned (also strengthens AT-11) |
| AT-41 | P1 | Shortfall reasons: construct one scenario per slot reason and `NO_SHIFT_COVERAGE`; plus random instances | Every slot with unmet hours has exactly one slot reason; every unmet hour outside all shift windows has exactly one uncovered-hour reason; lower bound `≤` actual unmet and matches Example G |
| AT-42 | P1, Tier C follow-up | Rest gap (restWeight = 8): Example F | If Tier C is selected, violation removed by REPLACE when hours are symmetric; with `restWeight = 0` the roster is unchanged. Not a Tier A/B gate. |
| AT-43 | P1 | Random states: `canAutoAssign` versus shared H1–H5 predicates used by `validate_state` | Equivalent on every sampled state; manual warning severities unchanged |
| AT-44 | P2 | Oracle on tiny instances (`D = 2`, `open..close` ≈ 8 buckets, 3 employees, 2 shifts ≈ 4096 rosters; enumerate all feasible rosters, take the minimum `(C,F)`) | Record the gap distribution (informational, **no bound asserted**); assert `C_v2 ≥ C_opt` as a sanity check of the oracle |
| AT-45 | P2 | If implemented: `N` sensitivity table and shift suggestions | Table matches direct recomputation; suggestions never modify shifts |
| AT-32 | P1 (existing) | Morning shift stop-rule example | Still passes with the v2 marginals (Example A) |

**Random-instance generator (tests only; seeded PRNG).** Employees 1–8 with `max ∈ {0, 4, 8, …, 48}`; shift sets {defaults}, {defaults + one overlapping peak shift}, {three random valid whole-hour shifts}; transactions uniformly 0–80 per bucket; `L ∈ {1, 2}`; weights {(3,1), (4,1)}. At least 200 seeds per property.

---

## 13. BRD change log

### 13.1 Sections superseded or extended

| BRD location | Change |
|---|---|
| BR-06 "optimization policy" item 2 (primary goal) | **Replaced** by §4 of this appendix (density ranking over feasible triples; stop rule semantics unchanged) |
| BR-06 item 3 (secondary goal: excess) | **Replaced**: excess charged through `wOver` inside `C` (unchanged in effect); first-person weight `wEmpty` added |
| BR-06 item 4 (tertiary: fairness) | **Replaced** by Appendix §2.7 and §5 (`F`, effective capacity, mandatory REPLACE refinement); BRD "MAY" balancing pass becomes **MUST** |
| BR-06 items 1, 5, 6 (hard feasibility, determinism, best effort) | [UNCHANGED] |
| BRD §5.2 approach table | Recommended-row label becomes "Marginal-gain allocation over feasible triples with a cost-based stop rule, followed by deterministic local search" |
| BRD §5.3 | **Replaced** by Appendix §2.6 and §4. The formula `W_under × removed − W_over × added` is the same quantity with the first-person weight refined; "prefer lower excess, then lower-utilization employee, then fixed order" becomes the key chain in §8 item 5 |
| BRD §5.4 fairness | **Extended**: utilization measured against effective capacity; target share; "no fixed minimum" **retained**, but "nobody near-zero while others are maxed" is now repaired by REPLACE and flagged when not repairable |
| BR-06 §6.4 generation feedback | **Extended** with lower bound, shortfall reasons, target vs actual, flags |
| BR-10 §10.1 (calculation definitions) | Metric formulas [UNCHANGED]; additions are diagnostics only |
| LOW_UTILIZATION (BR-08 table) | Definition fixed by Appendix §6.4 |
| BRD §10.2 (*Explicitly unresolved*) question "adjustable W_under / W_over?" | **Answered:** not in the baseline (D-20) |

### 13.2 Decisions

| ID | Decision |
|---|---|
| D-06 (amended) | Cover demand first; charge excess through the stop rule; first person in an empty hour weighs `wEmpty = 2·wUnder`; fairness third and lexicographic |
| D-07 (amended) | Fairness measured by utilization against **effective capacity** relative to a proportional target share |
| D-13 | [UNCHANGED] no guaranteed minimum utilization |
| D-19 | Internal model parameterised by `D`, `open`, `close`; UI fixed at Mon–Sun, 07:00–23:00 |
| D-20 | `wUnder`, `wOver`, `wEmpty` are policy constants in the baseline |
| D-21 | Lexicographic `(C, F)` instead of a weighted sum |
| D-22 | No demand smoothing; no fractional demand in the optimizer |
| D-23 | Candidate unit is a feasible `(employee, day, shift)` triple; ranking by density, stopping on absolute `ΔC` |
| D-24 | Refinement is deterministic first-improvement local search with counter-based caps; no randomness, no wall-clock limits |
| D-25 | Capacity lower bound, slot reasons, and `NO_SHIFT_COVERAGE` for unmet hours outside every configured shift are part of transient generation feedback; unexplained remainder is not labelled avoidable |
| D-28 | Service prerequisite errors retain legacy `SchedulingError` codes; pure generator uses the appendix's blocked outcome codes |
| D-29 | `canAutoAssign` shares H1–H5 predicates with the existing manual validator; no new public validation profile or changed warning severity |
| D-30 | The current API maximum remains `2^31 − 1`; effective capacity calculation must be exact and resource-bounded across that range |
| D-26 | Rest-gap is an optional soft term, default off, cyclic over the typical week |
| D-27 | Shift suggestions are read-only and user-triggered; the system never creates shifts automatically |

### 13.3 Invariants

| ID | Invariant | Enforcement |
|---|---|---|
| INV-19 | Refinement never increases `C`, and strictly decreases `(C, F)` lexicographically per accepted move | Algorithmic; AT-36 |
| INV-20 | Every intermediate state of construction and refinement satisfies H1–H5 | Algorithmic; AT-34, AT-43 |
| INV-21 | The generator uses no randomness and no wall-clock termination; all search arithmetic is integer | Code review; AT-35 |
| INV-22 | `unavoidableUnmet ≤ totalUnmet` for every generated roster | Calculation; AT-41 |
| INV-23 | Every slot with unmet staff-hours carries exactly one slot reason, and every unmet hour outside all shift windows carries exactly one `NO_SHIFT_COVERAGE` reason after generation | Calculation; AT-41 |

---

## 14. Non-goals and future hooks

**Explicit non-goals of this appendix** (do not implement; they widen scope or break determinism/explainability):
- ILP / CP-SAT / any solver dependency
- Simulated annealing, random restarts, tabu search, genetic algorithms
- Demand smoothing, forecasting, per-hour or per-day `N`
- Availability, days off, roles/skills, labour-law rest rules, break modelling
- Manager-editable raw weights; automatic creation of shifts
- Locked assignments, alternative-draft comparison (BR-09 [OPTIONAL])

**Future hooks the design keeps open:**
- `cost` is a pure module: a future exact optimizer (ILP: binaries `x[i,d,s]`; continuous `u_b ≥ r_b − s_b`, `o_b ≥ s_b − r_b`; the piecewise-linear convex per-bucket cost needs no extra binaries) can reuse it as a scorer, or use it as an oracle against this heuristic.
- Optional manager-facing "usefulness threshold" presets, if weights are ever exposed, should be expressed as the single parameter `ρ = wOver / (wUnder + wOver)` mapped to integer pairs, e.g. *Lean* `(wUnder=3, wOver=2)` ρ = 40 %, *Balanced* `(3, 1)` ρ = 25 %, *Coverage-first* `(9, 1)` ρ = 10 %, with `wEmpty = 2·wUnder` in each.
- A cross-slot 2-exchange move can be added to `refine` without changing any interface.

---

## 15. Design rationale and trade-offs (for README and review discussions)

| Component | Benefit | Cost / risk | Mitigation |
|---|---|---|---|
| Lexicographic `(C, F)` | Keeps stop rule and AT-32; fairness cannot cost coverage; no λ to calibrate | Fairness never wins against even 1 unit of coverage cost, so structural cases leave some imbalance | `NEAR_ZERO_WHILE_OTHERS_FULL` flag with cause; lower bound and reasons |
| Feasible-triple greedy with density ranking | No dead-ends; correct under mixed shift lengths | ~30–50 more lines; per-iteration scan of `|E|·D·|S|` candidates | Incremental state; ΔF only for tied set |
| `wEmpty = 2·wUnder` | Never leaves an hour empty while a busy hour gets a second person | Optimizer cost differs from displayed linear metrics | One-sentence README note (§2.9) |
| Effective capacity | Honest utilization, correct "full" notion | "100 %" no longer equals the contractual maximum | Show both numbers in UI (§6.6) |
| Local search | Corrects greedy blind spots, directly addresses the source fairness requirement | May stop at a local optimum; more code and tests | Counter caps, fixed order, oracle test AT-44 to track the gap |
| Rest-gap (optional) | More humane rosters | Goes beyond BRD scope; extra parameter | Default off; documented as a soft preference |
| No solver | Zero dependencies, easy to explain and modify in a live session | No optimality proof | Pure `cost` module keeps ILP as a future option (§14) |

**Known limitations to state in the README:**
- Greedy plus local search does not guarantee global optimality; the quality bar is a defensible, plausible, reproducible roster (BRD §9.3).
- With only two non-overlapping 8-hour shifts, headcount is constant within a shift; some excess is structural. Additional (possibly overlapping) shift definitions can reduce it, which the optional shift suggestions quantify.
- `N` is an assumption, not a measurement; one week of data is a noisy basis for staffing.
- The lower bound ignores shift granularity and day constraints, so it understates unavoidable shortage.
