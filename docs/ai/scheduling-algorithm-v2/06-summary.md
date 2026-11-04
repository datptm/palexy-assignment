# Scheduling algorithm v2 — Stage 6 summary

**Task:** `scheduling-algorithm-v2`  
**Status:** The Stage 6 finding was resolved in the follow-up documented in §6. Sections 1–5 retain the original audit evidence and statuses.  
**Authority:** The owner identified [01-spec.md](01-spec.md), [02-design.md](02-design.md), [03-plan.md](03-plan.md), [04-tests.md](04-tests.md), and the implementation steps as approved. Their older “proposed” headings were not edited.

## 1. Outcome and changes made

The current implementation adds a typed, pure generator with capacity, cost, construction, refinement, and transient diagnostics in `src/model/scheduling.py` and `src/domain/generation.py`. It shares assignment rules with `src/domain/validation.py`, carries results through `src/services/schedules.py`, presents them in `ui/roster.py`, `ui/demand_panel.py`, and `ui/staff_panel.py`, and updates `README.md`. Focused v2 domain, service, and UI tests are present. These implementation changes were already in the working tree when Stage 6 began; this stage changed **only this summary**. The working tree also contains other pre-existing edits and untracked resource files, which were left untouched.

**Confirmed gap:** The construction ADD loop uses `len(trace) >= max_moves` as its stop condition (`src/domain/generation.py:649`), and `generate_roster` passes that same trace into construction before refinement (`src/domain/generation.py:1135-1139`). The approved FR-4.2 requires construction to repeat until no feasible negative-`ΔC` addition remains. FR-5.3 defines `maxMoves` as a refinement stopping cap. A read-only reproduction with two one-hour days, two eligible employees, and `max_moves=1` returned **one assignment, one unmet staff-hour, a single `CONSTRUCTION/ADD` trace record, and `refinement_capped=True`**. The second day's ADD is feasible and decreases `C`. The existing cap test (`tests/test_generation_v2.py::test_refinement_rejects_fairness_worsening_replacement_and_reports_caps`) asserts only that the capped flag appears and therefore passes despite this behavior. This is a requirement failure even though the full automated suite passes. No source or test fix was made, per the Stage 6 instruction.

The evidence command was:

```powershell
.\.venv\Scripts\python.exe -c "from tests.test_generation_v2 import _state, _config, _run; o=_run(_state(day_count=2, employees=(8,8)), _config(day_count=2, open_end_hour=8, max_moves=1)); print('assignments=', len(o.draft.assignments), 'unmet=', o.draft_result.weekly.unmet_staff_hours, 'trace=', [(x.phase,x.action) for x in o.diagnostics.trace], 'capped=', o.diagnostics.refinement_capped)"
```

Output: `assignments= 1 unmet= 1 trace= [('CONSTRUCTION', 'ADD')] capped= True`.

## 2. Spec traceability

Paths below are relative to the repository root. `V2` means `tests/test_generation_v2.py`; `SVC` means `tests/test_scheduling_algorithm_v2_service.py`; `UI` means `tests/test_scheduling_algorithm_v2_ui.py`. “Suite pass” means the cited tests passed in the 184-pass full run; it does **not** resolve the confirmed gap or prove cases those tests do not assert. “Mapped” means an implementation and test location were identified, but no further independent requirement audit was performed after the gap was found. “Gap” means directly contradicted by the reproduction above.

### Functional requirements

| Spec item | Implementation | Verification result | Status |
|---|---|---|---|
| FR-1.1 Pure typed operation, empty-start adapter | `generation.py::generate_roster`, `_run`; `model/scheduling.py::GenerationOutcome`; `services/schedules.py::_generated` | V2 purity and empty-start tests; SVC preview/confirm tests: suite pass | Test pass |
| FR-1.2 Defaults and integer config validation | `model/scheduling.py::GenerationConfig`; `generation.py::_validate_config`; schedule threshold and daily limit | V2 invalid-config and demand-boundary tests: suite pass | Test pass |
| FR-1.3 Ordered prerequisite blocks, legacy mapping, no write, partial capacity | `generation.py::_prepare`, `_blocked`; `services/schedules.py::_generated` | V2 prerequisite tests and SVC blocked-state tests: suite pass | Test pass |
| FR-1.4 Test bounds, production week, zero versus absent demand | `GenerationConfig`; `generation.py::_required_counts` | V2 zero-demand/integer-ceiling tests: suite pass | Test pass |
| FR-2.1 Canonical order and precomputed shift data | `generation.py::_prepare`, `_Roster`; employee IDs stand for creation order under the approved assumption | V2 canonical-output test: suite pass; pairwise overlap precomputation was not established in this stopped audit | Mapped; review remaining detail |
| FR-2.2 Exact effective capacity through API maximum | `generation.py::effective_capacity` duration-residue DP | V2 exact/reference/API-maximum tests: suite pass; source documents bound `(q−1) × sum(smaller durations)` | Test pass |
| FR-2.3 Required/capacity hours and conservative bound | `generation.py::_prepare`, `_diagnostics` | V2 capacity/shortfall and shortage-free tests: suite pass | Test pass |
| FR-3.1 Weighted bucket cost and marginals | `generation.py::_Roster.primary_cost`, `_added_cost`, `_removed_cost` | V2 default/custom marginal tests: suite pass | Test pass |
| FR-3.2 Integer fair-share cost and display-only division | `generation.py::_Roster.fairness_cost`, `_diagnostics` | V2 REPLACE and employee-diagnostic tests: suite pass | Test pass |
| FR-3.3 Lexicographic objective; unchanged linear metrics | `generation.py::_rank_candidates`, refinement passes, `_make_result`; `src/domain/metrics.py` | V2 cost/refinement tests and UI metric-label test: suite pass | Test pass |
| FR-4.1 H1–H5 feasible triples and manual warning severity | `validation.py::can_place_assignment`, `validate_state`; `generation.py::_Roster._can_add` | V2 feasibility/trace tests plus `tests/test_validation.py`: suite pass | Test pass |
| FR-4.2 Density/tie ranking and ADD until closure | `generation.py::_rank_candidates`, `_add_closure` | V2 Examples A–C tests pass, but low `max_moves` stops construction while a negative-`ΔC` ADD remains | **Gap** |
| FR-4.3 Effective-capacity fairness ties, no inherited/manual-only additions | `generation.py::_fairness_deltas`, `_run` | V2 canonical and empty-start tests: suite pass | Test pass |
| FR-5.1 ADD/DROP/MOVE/REPLACE order and acceptance rules | `generation.py::_refine`, `_drop_pass`, `_move_pass`, `_replace_pass` | V2 REPLACE, cap, and trace tests: suite pass | Mapped; not fully re-audited |
| FR-5.2 Tentative restoration, strict improvement, feasible intermediates | `generation.py::_move_pass`, `_replace_pass`; `_Roster` | V2 accepted-trace and REPLACE tests: suite pass | Test pass |
| FR-5.3 Pass/move caps apply to refinement, capped result semantics | `generation.py::_refine`, `_add_closure`; diagnostics flag | V2 cap test passes but the reproduction proves the move cap also truncates construction | **Gap** |
| FR-6.1 Existing metrics and employee capacity/utilization/target | `generation.py::_make_result`, `_diagnostics`; `ui/staff_panel.py` | V2 zero-denominator and UI tests: suite pass | Test pass |
| FR-6.2 Ordered slot and uncovered-hour reasons | `generation.py::_shortfalls`; `ui/roster.py::_generation_diagnostics` | V2 shortfall-reason and uncovered-hour tests: suite pass | Test pass |
| FR-6.3 Lower-bound values and careful wording | `generation.py::_diagnostics`; `ui/roster.py` | V2 shortfall/bound and UI tests: suite pass | Test pass |
| FR-6.4 Utilization, near-zero, and cap flags | `generation.py::_diagnostics`, `_has_feasible_replacement` | V2 utilization/flag/cap tests: suite pass; construction cap is mislabeled as refinement cap | **Partial** |
| FR-6.5 Ordered integer-delta trace and final costs | `model/scheduling.py::GenerationTrace`, `GenerationDiagnostics`; `generation.py::_record`, `_diagnostics` | V2 reproducibility and trace tests: suite pass | Test pass |
| FR-7.1 Versioned, atomic, transient service workflow | `services/schedules.py::generate`, `preview_generation`, `confirm_generation`, `preview_refresh`, `confirm_refresh` | SVC tests and existing refresh tests: suite pass | Test pass |
| FR-7.2 Summary, staff, flags/cost, optional trace view | `ui/roster.py`, `ui/demand_panel.py`, `ui/staff_panel.py` | UI tests: suite pass | Test pass |
| FR-7.3 README policy and limitations | `README.md::Scheduling behavior` | Prose reviewed during this stage; no automated prose assertion | Mapped; manual review |

### Non-functional requirements

| Spec item | Implementation | Verification result | Status |
|---|---|---|---|
| Determinism and precision | Integer costs/deltas and fixed ordering in `generation.py`; `Fraction` for utilization flag comparison | V2 canonical/repeated-output tests: suite pass | Test pass |
| Performance and bounded work | `generation.py::effective_capacity`, `_preflight_work`, `_WorkBudget`, pass/move caps | API-maximum tests and all three opt-in benchmarks pass; cap semantics fail FR-5.3 | **Partial** |
| Security and reliability | Input validation in `generation.py`; service transaction/version boundaries in `services/schedules.py` | V2 invalid-input and SVC no-write/stale tests: suite pass | Mapped; audit stopped at gap |
| Compatibility | `generate_draft` adapter; unchanged SQLite schema, metrics and manual-warning paths | Existing pytest suite, scripts, refresh, UI, validation tests: pass | Test pass |
| Verification gate | Project `.venv` and commands in §3 | Full pytest, Ruff lint/format, compileall, and diff check pass; behavior gap remains | **Partial** |

### Edge and failure cases from spec §4

| Spec item | Implementation | Verification result | Status |
|---|---|---|---|
| Missing demand/shifts/staff precedence and no mutation | `generation.py::_prepare`; service mapper | V2 prerequisites; SVC no-write: pass | Test pass |
| Zero transactions still require one person | `generation.py::_required_counts` | V2 zero-demand test: pass | Test pass |
| Insufficient but positive capacity gives partial draft/bound | `_prepare`, `_diagnostics` | V2 capacity/shortfall tests: pass | Test pass |
| Open hour outside all shifts | `_shortfalls` | V2 uncovered-hour test: pass | Test pass |
| Zero/too-small maximum | `effective_capacity`, `_prepare` | V2 capacity and blocked tests: pass | Test pass |
| Mixed durations, overlap, `L>1`, adjacency | `effective_capacity`; `_Roster._can_add`; `validation.py` | V2 capacity/feasibility tests: pass | Mapped; not fully re-audited |
| Zero-`ΔC` ADD and deterministic ties | `_rank_candidates` | V2 Example A and canonical tests: pass; positive ADD can remain after construction cap | **Partial** |
| `sumCap=0` | `_prepare`, `_Roster.fairness_cost` | V2 blocked and zero-denominator tests: pass | Test pass |
| No unmet demand | `_shortfalls`, `_diagnostics` | V2 shortage-free test: pass | Test pass |
| Refinement cap hit | `_refine`, `_diagnostics` | V2 cap test: pass; cap can hit during construction | **Partial** |
| Existing edited roster, cancel/stale/confirm | service preview/confirm methods | SVC and existing refresh tests: pass | Test pass |
| Invalid demand/config/work limit; full max range | `_validate_config`, `_required_counts`, `_preflight_work`, `effective_capacity` | V2 invalid-input/API-maximum tests: pass; no separate Stage 6 over-budget probe | Mapped; limited verification |

### Acceptance criteria and scope decisions

| Spec item | Implementation | Verification result | Status |
|---|---|---|---|
| AC-1 blocks, legacy errors, zero demand, no write | `_prepare`, `_blocked`, service mapper | V2 and SVC prerequisite tests: pass | Test pass |
| AC-2 capacity recurrence, API max, Examples D/G | `effective_capacity`, `_diagnostics` | V2 capacity/reference/bound tests: pass | Test pass |
| AC-3 Example A stop/default versus custom weights | `_rank_candidates` | V2 default-marginal test: pass | Test pass |
| AC-4 Example B empty-hour preference | `_rank_candidates` | V2 empty-hour test: pass | Test pass |
| AC-5 Example C density order | `_rank_candidates`, `rank_add_candidates` | V2 peak-density test: pass | Test pass |
| AC-6 H1–H5, shared predicates, monotonic refinement | `_Roster`, `validation.py`, refinement passes | V2 feasibility/trace tests: pass | Test pass |
| AC-7 Example E REPLACE and fairness rejection | `_replace_pass` | V2 REPLACE tests: pass | Test pass |
| AC-8 reproducible full output | `_run`, canonical preparation/trace | V2 canonical-output test: pass | Test pass |
| AC-9 shortfall reason and conservative bound | `_shortfalls`, `_diagnostics` | V2 reasons/uncovered-hour tests: pass | Test pass |
| AC-10 transient UI diagnostics and README | UI panels, service result, README | UI and SVC tests: pass; README prose manually mapped | Test pass with manual prose review |
| AC-11 preview/cancel/stale/atomic replacement | service preview/confirm methods | SVC plus existing refresh tests: pass | Test pass |
| AC-12 all FR/NFR and applicable gates | All paths above | Gates pass, but FR-4.2/FR-5.3 reproduction fails required behavior | **Gap** |
| Approved assumptions 1–6 | Tier A/B scope, `generate_draft` adapter, ID order, slot/hour shortfalls, transient diagnostics, zero rest count | Mapped to `generation.py`, service/UI and README; suite passes | Mapped |
| Explicit non-goals and optional Tier C/AT-42/44/45 | No solver, schema change, forecast, rest-gap implementation or new runtime dependency | `requirements.txt` and schema unchanged; opt-in Tier C tests not required | Out of scope |

## 3. Full-suite commands and results

All Python commands used `.venv\Scripts\python.exe` from the repository root (Python 3.13.5 with project dependencies). The repository has no build step and no configured type checker; `compileall` is its specified static/syntax check.

| Command | Result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest` | First sandbox run: 84 passed, 3 skipped, 100 fixture-setup errors. Every error shown arose from `PermissionError [WinError 5]` while pytest accessed `C:\Users\PC\AppData\Local\Temp\pytest-of-PC`; this did not test those cases. |
| `.\.venv\Scripts\python.exe -m pytest -q --tb=short --basetemp=.test-tmp/stage6-summary-20261104-a -p no:cacheprovider` | Second sandbox run: temporary-directory permission errors again, including pytest cleanup on the workspace basetemp; exit 1. |
| `.\.venv\Scripts\python.exe -m pytest -q --tb=short -p no:cacheprovider` outside the sandbox | **184 passed, 3 skipped in 26.06s**, exit 0. The three skips were opt-in benchmarks. |
| `RUN_SCHEDULING_BENCHMARKS=1` with `.\.venv\Scripts\python.exe -m pytest tests/test_performance.py -q -s --tb=short -p no:cacheprovider` outside the sandbox | **3 passed in 4.36s**; reported timings: import/metrics 0.0078s, 100 employees/32 shifts 3.8967s, confirmed refresh 0.0163s. These are local observations, not timing assertions. |
| `.\.venv\Scripts\python.exe -m ruff check .` | Exit 0; “All checks passed!” |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Exit 0; 94 files already formatted. |
| `.\.venv\Scripts\python.exe -m compileall -q src ui tests main.py` | Exit 0; no output. |
| `git diff --check` | Exit 0; only Git LF-to-CRLF warnings, no whitespace errors. |
| Build / separate type checker | Not run: interpreted Python app; neither is configured in `AGENTS.md`/`pyproject.toml`. |

The passing suite establishes that current tests pass in an environment with usable temporary directories. It does not establish FR-4.2/FR-5.3, because the cap test checks the flag rather than construction closure. The read-only reproduction above is the contrary evidence.

## 4. Known limitations, risks, and follow-ups

1. **Review and fix required:** Count `max_moves` only within refinement, and let construction reach negative-`ΔC` ADD closure. Add a regression test that asserts the two-day case covers both days when `max_moves=1`; separately test that refinement stops at its move cap with a valid partial local-search result. Re-run the full gate after any fix. This is a proposal for review, not a change made in Stage 6.
2. The generator is a deterministic heuristic. The effective-capacity shortage figure is a conservative lower bound, not a proof that all remaining shortage can be filled. Slot shortfall records may overlap and must not be summed as independent unmet hours.
3. The capacity method documents a maximum-independent DP bound; its exact memory/time ceiling was reviewed by code and representative tests, not measured with a memory profiler. The 100-employee/32-shift benchmark passed on this local machine; other machines may differ.
4. This audit stopped on the confirmed cap gap. Rows marked “Mapped” still need a complete independent review, especially precomputation and untested budget boundaries. Desktop/narrow-screen layout, accessibility, and prose were not verified in a live browser.
5. Tier C rest-gap scoring, sensitivity, shift suggestions, and comparison harness remain outside the approved Tiers A/B scope.

## 5. Lessons learned and proposed AGENTS.md Known pitfalls lines

The passing cap test checked only the flag, so it did not catch an avoidable shortage introduced before refinement. A test for a stopping rule needs to check both the stop point and what work must have completed before it. The sandbox's temporary-directory restriction also showed why a fixture-setup error must be separated from an application failure and rerun in a usable environment.

Proposed concise lines for owner review; **AGENTS.md was not edited**:

> - Construction must reach negative-cost ADD closure before applying refinement move caps; test the roster and remaining feasible additions, not only the capped flag.
> - Treat pytest temporary-directory permission errors as environment failures; rerun the full suite with a usable temp location before judging application behavior.

## 6. Follow-up resolution

After review, construction was changed to run ADD closure independently of `max_moves`. The refinement phase now records the trace length at its start and counts only subsequent accepted ADD, DROP, MOVE, and REPLACE actions against `max_moves`. The ordered trace still includes construction decisions.

The regression test `test_construction_reaches_add_closure_before_refinement_move_cap` failed before the fix because only day 0 was assigned; it passes after the fix and asserts both days are staffed, unmet hours are zero, and `refinement_capped` is false. A separate test, `test_refinement_move_cap_counts_only_refinement_actions`, confirms that an imbalanced existing roster still stops after one accepted REPLACE and reports the cap. The former combined cap test was split so these behaviors are asserted independently. The FR-4.2, FR-5.3, FR-6.4, and AC-12 gap/partial statuses above are historical for this specific finding; the follow-up tests now verify the corrected cap boundary. Other rows marked “Mapped” were not expanded into a new full audit.

Follow-up verification: focused v2 tests, **46 passed**; full pytest, **186 passed, 3 opt-in benchmarks skipped**. Ruff lint, Ruff format, compileall, and `git diff --check` passed. The opt-in benchmarks were not rerun for this focused cap-accounting change. The existing performance observations in §3 remain local historical measurements.

