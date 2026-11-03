# Manual scheduling commands

Run these from the repository root with the Python environment used by the app. On Windows, replace `python` below with `.venv/Scripts/python.exe` if the virtual environment is not active. On macOS/Linux, use `.venv/bin/python`.

```sh
python -m scripts.schedules create "Shop week"
python -m scripts.schedules list
python -m scripts.schedules add-employee 1 Alex 40
python -m scripts.import_csv 1 data/sample_transaction_interview.csv
python -m scripts.generate 1
python -m scripts.schedules show 1 --demand --history
```

The commands use `data/schedules.sqlite3` by default. Add `--db-name manual.sqlite3` **before** the command or schedule ID to keep a separate local database in `data/`. The printed schedule ID is used by later commands. `show` prints the current state and weekly metrics; `--demand` prints all 112 hourly demand rows, and `--history` lists saved prior-state snapshots.

The first valid CSV import stores demand without changing the roster. A later import shows a read-only replacement preview. Rerun it with `--confirm-replace` to save a snapshot and replace demand and the roster. Likewise, generation commits directly into an empty roster; with an existing roster it previews the replacement until `--confirm-replace` is supplied. Invalid input exits with status 2 and prints structured validation errors without writing a partial import.

CSV files must be inside `data/`, including after symlink resolution, and are read with a 1 MiB cap. Database names are simple `.sqlite3` filenames inside `data/`. Copy a report into `data/` before importing it; avoid placing real customer information in this repository.
