# Staff Scheduling System

A local browser app for a store manager to plan a typical Monday–Sunday week. The [assignment brief](docs/resources/SWE_Take-Home_Staff_Scheduling_System.pdf) describes the target product; this repository currently contains its runnable foundation, not the finished scheduler.

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
- `main.py`: starts the local web app.
- `docs/resources/`: original assignment brief.

## Brief assumptions and next steps

The week is Monday–Sunday. Shift end times are exclusive, so the default shifts 07:00–15:00 and 15:00–23:00 cover 07:00 through 22:59. The current time helper accepts same-day, whole-hour shifts. `data/sample_transaction_interview.csv` is the supplied sample input; the UI does not import it yet.

The SQLite layer can store named schedules in `data/schedules.sqlite3` through `src/services/schedules.py`, but the UI is not wired to that service yet. Next implementation steps are staff and shift editing, transaction import, auto-scheduling, direct roster editing, and live aggregated demand/coverage feedback. The auto-scheduling threshold and fairness policy remain open decisions; they should be justified and tested when that feature is built. Authentication and deployment are outside this baseline.

## AI usage

Codex prepared the repository scaffold and checked it against the assignment brief. The project owner should verify the running UI and review future scheduling assumptions and algorithm results against realistic demand before submission.
