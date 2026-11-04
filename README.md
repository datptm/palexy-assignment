# Staff Scheduling System

A local browser app for a store manager to plan a typical Monday–Sunday week. The [assignment brief](docs/resources/SWE_Take-Home_Staff_Scheduling_System.pdf) describes the target product. The NiceGUI page uses the SQLite-backed scheduling service for a weekly roster, staff and shift maintenance, demand import, coverage analysis, draft generation, and read-only history.

## Installation

Use Python 3.10 or newer. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

On macOS or Linux, replace `.\.venv\Scripts\python` with `.venv/bin/python`.

## Run

From the repository root:

```powershell
.\.venv\Scripts\activate
python main.py
```

Open <http://127.0.0.1:8765>.

## Checks

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src ui tests main.py
```

Run checks in the environment installed from `requirements.txt`.

## Layout

- `src/domain/`: pure scheduling rules and validation.
- `src/model/`: dataclasses shared between layers.
- `src/db/`: SQLite connection, schema, and record operations.
- `src/services/`: application entry points that coordinate domain rules and storage.
- `ui/`: NiceGUI pages and presentation only.
- `tests/`: automated tests.
- `data/`: supplied sample CSV and the default location for the ignored runtime SQLite file.
- `scripts/`: [manual commands](scripts/README.md) for creating, inspecting, importing, and generating schedules.
- `main.py`: starts the local web app.
- `docs/resources/`: original assignment brief.

## Scheduling behavior

The week is Monday–Sunday. Shift end times are exclusive, so the default shifts 07:00–15:00 and 15:00–23:00 cover 07:00 through 22:59. The current time helper accepts same-day, whole-hour shifts. `data/sample_transaction_interview.csv` is the supplied sample input; managers can upload a transaction CSV through the Demand import panel.

`ScheduleService` in `src/services/schedules.py` stores independent named weeks, staff, shifts, demand, assignments, and historical snapshots in SQLite. It validates imported CSV bytes before writing. At threshold `N` (20 transactions per person-hour by default), each open hour requires at least one employee and otherwise `ceil(transactions / N)` employees.

Automatic generation starts with an empty roster, adds only feasible shifts with negative weighted shortage/excess cost, then refines the roster with add, drop, move, and coverage-neutral replacement passes. It is deterministic for the same ordered inputs and uses effective-capacity fair share only to break ties or improve fairness without worsening coverage cost; REPLACE can redistribute work without changing coverage. Search is a bounded heuristic, not a global optimizer. Its unavoidable-shortage figure is a conservative lower bound based on relaxed effective staff capacity, not a promise that all remaining shortages can be filled.

Effective capacity uses a bounded duration-residue dynamic program: for largest shift duration `q`, its sum bound is `(q - 1) × sum(distinct smaller durations)`. With supported shift lengths up to 16 hours, the DP has at most 1,800 sum entries and its memory use does not depend on an employee's weekly maximum. Before search, generation limits candidate space to 100,000 triples, estimated work to 50 million evaluations, and the decision trace to 250,000 records; it also enforces a 50-million actual candidate-evaluation budget. Exceeding a budget returns an explicit error before persistence, without reducing the supported weekly-hours maximum.

Generation diagnostics show optimizer costs and explanations separately from the dashboard's existing linear coverage and transaction metrics. They are transient and belong only to the current generated result or read-only preview; reloads and manual edits clear them. Re-imports and post-import threshold changes require a signed preview and explicit confirmation; confirmation captures the prior state and replaces demand and roster atomically. Manual over-limit edits retain their warning behavior. Authentication and deployment are outside this local application.

## AI usage

Codex prepared the repository scaffold and checked it against the assignment brief. The project owner should verify the running UI and review future scheduling assumptions and algorithm results against realistic demand before submission.
