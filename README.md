# Staff Scheduling System

A local web app for store managers to plan a typical Monday–Sunday roster from hourly transaction demand. The application supports named schedules, staff and shift maintenance, demand import, coverage analysis, automatic draft generation, manual assignment edits, and read-only schedule history. See the [take-home brief](docs/resources/SWE_Take-Home_Staff_Scheduling_System.pdf) for the original deliverables and [AI_USAGE.md](AI_USAGE.md) for how AI assistance was used and reviewed.

## What the application does

- Create and switch between independent SQLite-backed weekly schedules.
- Add, edit, and remove staff and shifts; view each employee's assigned hours and weekly limit.
- Import a weekly transaction CSV, inspect validation findings, and distinguish missing demand from a valid report containing zero transactions.
- View a Monday–Sunday roster and hourly demand, scheduled staffing, coverage gaps or excess, weekly totals, overall transactions per staff-hour, and the average ratio across staffed day/hour cells.
- Generate a demand-aware draft, review its diagnostics, and make manual assignment changes. Re-imports and threshold changes after demand exists require a preview and confirmation; confirmed replacements preserve the previous state in read-only history.

The interface presents the roster as the main workspace. Assignment and shift reviews show eligibility, conflicts, warnings, and projected impact before committing where applicable.

## Automatic scheduling approach

The default demand threshold is **20 transactions per employee-hour**. For each open hour, required staffing is `max(1, ceil(transactions / N))`, where `N` is the configured threshold. Thus every open hour requires at least one employee, including an hour with zero transactions; absent demand is not treated as zero.

The deterministic generator starts from an empty draft and considers feasible employee/day/shift assignments. Feasibility respects weekly hour maxima, the configured daily shift limit, non-overlap, and assignment uniqueness. Its primary objective balances unmet staffing against excess coverage. It builds coverage first, then refines the roster with add, drop, move, and coverage-neutral replacement passes. Effective capacity informs fairness tie-breaks and fairness improvements that do not worsen the primary coverage cost. Stable ordering makes results reproducible for the same ordered inputs.

This is a **bounded heuristic, not a global optimizer**. Its remaining-shortage estimate is a conservative lower bound based on relaxed effective staff capacity, not a guarantee that every remaining gap is fillable. Search has explicit candidate, work, trace, and evaluation budgets; a budget breach is reported before persistence instead of silently returning a reduced search.

## Assumptions, configuration, and design

The schedule represents a **typical week**, not a dated calendar week. Its seven days are ordered Monday through Sunday, with 16 one-hour operating buckets per day: `[07:00, 23:00)`. A bucket at 22:00 covers through 22:59. The supplied [sample transaction CSV](data/sample_transaction_interview.csv) has dates and columns in its own order; dates are informational and weekday columns are normalized into the schedule's Monday-first order.

### Schedule settings and inputs

| Setting or input | Default / accepted values | Rationale |
|---|---|---|
| Transactions per required employee-hour (`N`) | `20` by default; configurable to a positive whole number | Provides a simple, explainable demand proxy. Required staff per open hour is `max(1, ceil(transactions / N))`. |
| Daily shift limit | `1` by default; configurable to a positive whole number | Keeps the default policy simple while allowing a manager to permit additional shifts. |
| Shift definitions | `07:00–15:00` and `15:00–23:00`; manager can maintain shifts using whole-hour same-day times within `[07:00, 23:00)` | Shift end times are exclusive; a shift ending at 15:00 does not cover the 15:00 hour. |
| Staff weekly maximum | Set per employee as a nonnegative whole number | Generation must not exceed an employee's maximum; zero-hour capacity is valid. |
| Imported demand | Exactly one nonnegative whole-number transaction count per weekday/hour; zero is valid | Missing demand is unavailable, not zero. Invalid or oversized uploads are rejected before stored demand changes. |

### Generator policy

Generator scoring uses fixed internal defaults rather than manager-adjustable weights: each additional unmet employee-hour costs `3`, excess coverage costs `1` per staff-hour, and the first unmet employee in an hour costs `6`. This makes opening a completely uncovered hour more costly than adding another person to an already staffed but still-under-covered hour. The generator prioritizes lowering coverage cost; effective-capacity fair share is secondary and may not worsen that primary cost. These optimizer costs are separate from the dashboard's linear coverage and transaction metrics.

Search is deterministic for the same normalized inputs and stable record ordering. It begins with an empty roster, respects weekly maxima, daily shift limits, overlap, and duplicate-assignment constraints, then applies bounded improvement passes. The defaults are up to `50` refinement passes and `5,000` accepted refinement moves. Resource guards also cap candidate space at `100,000` triples, estimated work and actual candidate evaluations at `50,000,000`, and decision-trace records at `250,000`. Hitting a safety budget fails explicitly before persistence; a move/pass cap instead returns the valid current draft with a cap diagnostic.

This design deliberately favors an explainable, reviewable draft over a claim of global optimality. Remaining-shortage diagnostics include a conservative lower bound based on relaxed effective staff capacity; they do not prove that the rest of the shortage is avoidable.

### Product and safety choices

- The weekly roster is the primary workspace; detailed metrics, warnings, staff limits, and demand are separated into labeled views so the calendar remains scannable.
- Assignment and used-shift edits are reviewed with eligibility, conflicts, warnings, or projected impact before commit where applicable. Hard-invalid assignments are blocked; policy exceptions such as manual over-limit scheduling remain possible with explicit warnings.
- Initial demand import does not automatically create a roster. Re-imports and threshold changes after demand exists require explicit preview and confirmation because they replace the current roster, including manual edits. Confirmation saves the previous state atomically in read-only history; cancellation leaves it unchanged.
- SQLite is the local source of truth. The app binds to `127.0.0.1`; authentication, multi-user access, publishing, and deployment are outside scope.

## Install

Use Python 3.10 or newer. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

On macOS or Linux, replace `.\.venv\Scripts\python` with `.venv/bin/python`.

## Run

From the repository root:

```powershell
.\.venv\Scripts\python main.py
```

Open <http://127.0.0.1:8765>. The app binds to the local machine; its default runtime database is `data/schedules.sqlite3`.

## Verify

Run these commands in the environment installed from `requirements.txt`:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m compileall -q src ui tests main.py
```

`compileall` is a syntax check, not a separate type checker. The project is an interpreted Python application, so no build step is required. Optional performance benchmarks are opt-in.

## Project layout

- `src/domain/`: pure scheduling rules, CSV validation, demand calculations, metrics, and generation.
- `src/model/`: typed records shared between layers.
- `src/db/`: SQLite schema, connections, and parameterized persistence.
- `src/services/`: use cases that coordinate domain rules and storage.
- `ui/`: NiceGUI pages and presentation.
- `tests/`: pytest unit, SQLite integration, UI workflow, and application smoke tests.
- `scripts/`: [manual commands](scripts/README.md) for creating, inspecting, importing, and generating schedules.
- `docs/resources/`: assignment and design source documents.
- `.agents/`: repository AI workflow guides, staged prompts, and reusable skills.
- `docs/ai/`: task specifications, designs, plans, test records, implementation summaries, and an append-only change log.

## AI usage

AI assistance supported requirements analysis, design, test planning, implementation, and review. The project owner kept responsibility for decisions, review, and verification. The staged process, reusable skills, evidence from completed tasks, and known limitations are described in [AI_USAGE.md](AI_USAGE.md).


## Future work

If time allows, the next improvements would be:

- Refine the interface through manager feedback and usability testing, improving visual hierarchy, navigation, and the clarity and speed of common roster-editing tasks.
- Research alternative scheduling approaches and compare them explicitly against the current deterministic heuristic using representative demand and staff scenarios. Use measurable outcomes—such as unmet and excess staff-hours, workload fairness, runtime, and explainability—to guide any algorithm upgrade.
