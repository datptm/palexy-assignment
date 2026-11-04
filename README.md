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

`ScheduleService` in `src/services/schedules.py` stores independent named weeks, staff, shifts, demand, assignments, and historical snapshots in SQLite. It validates imported CSV bytes before writing, estimates required staff at a default threshold of 20 transactions per person-hour, generates a deterministic best-effort roster, and calculates current coverage and workload metrics. Re-imports and post-import threshold changes require a signed preview and explicit confirmation; confirmation captures the prior state and replaces the active roster atomically. Manual over-limit edits return warnings. The page keeps the roster editable and shows coverage and warnings from the committed service result. Authentication and deployment are outside this local application.

## AI usage

Codex prepared the repository scaffold and checked it against the assignment brief. The project owner should verify the running UI and review future scheduling assumptions and algorithm results against realistic demand before submission.
