# Staff Scheduling System

A local NiceGUI web application for store managers planning a typical weekly roster from hourly transaction demand. The current repository is a scaffold for the assignment in `docs/resources/`.

Trust boundary: browser input, uploaded transaction files, environment values, and any future external service response are untrusted.

## Tech stack
- Language/runtime: Python 3.10+; framework: NiceGUI 3.18.0.
- Data/storage: SQLite for named schedules; the default ignored runtime file is `data/schedules.sqlite3`.
- Platform: local browser on Windows, macOS, or Linux; bind to `127.0.0.1:8765`.

## Commands
- Install: `python -m venv .venv` then `.venv/Scripts/python -m pip install -r requirements.txt` on Windows (`.venv/bin/python` on macOS/Linux). `requirements.txt` is app-only.
- Build: N/A (interpreted Python application).
- Test: `python -m pytest`.
- Lint/format: `python -m ruff check .` and `python -m ruff format --check .`.
- Type/static check: `python -m compileall -q src ui tests main.py` (syntax check; no type checker configured).
- Run locally: `python main.py` from the repository root, then open `http://127.0.0.1:8765`.
- Run checks with the Python environment where `requirements.txt` is installed. A task is DONE only when every applicable check above passes.

## Architecture
- `src/domain/`: pure rules, validation, and utilities; no database or UI imports.
- `src/model/`: dataclasses for records passed between layers.
- `src/db/`: SQLite connection, schema, and parameterized queries.
- `src/services/`: use cases that coordinate domain functions, models, and database operations.
- `ui/`: NiceGUI pages and presentation.
- `tests/`: pytest unit, SQLite, and application smoke tests.
- `data/`: supplied sample transaction CSV and the ignored runtime SQLite location.
- `main.py`: application entry point.
- Key decisions: keep domain rules pure, isolate SQLite behind `db/` and `services/`, and keep unfinished workflows out of the UI. The sample CSV is in `data/`.

## Conventions
- Style: Ruff lint and format settings in `pyproject.toml`, PEP 8 names, type hints and docstrings for public functions, explicit errors at boundaries.
- Tests: `tests/test_*.py` using pytest; test observable behavior with small fixtures and temporary SQLite files.
- Commits/PRs: focused changes with descriptive messages; do not push to main.
- Logging: standard-library `logging` when needed; never log secrets or uploaded customer data.

## Security rules
- Validate all external input at the boundary.
- No dynamic code execution or unsafe deserialization on untrusted data.
- File paths: resolve to a canonical path and verify it stays inside the allowed base directory; never rely on string matching.
- Apply resource limits (timeout, memory, size, depth, rate) to anything untrusted.
- Never read, print, or commit secrets, credentials, `.env` files, or real customer data.

## Do NOT
- Add dependencies without asking first, except NiceGUI, pytest, and Ruff already requested for this scaffold.
- Swallow errors (empty catch/except blocks, ignored return values).
- Modify `docs/resources/` source documents, `data/sample_transaction_interview.csv`, generated files, or lockfiles unless the user explicitly requests it.
- Refactor or reformat code unrelated to the task.
- Run destructive commands (delete, force-push, DB drops) or push to the main branch.
- Edit, reorder, or delete existing change log entries (append only).

## Change log (required)
- Every chat that changes the codebase MUST append one entry to `docs/ai/CHANGELOG.md` before the chat ends.
- "Changes the codebase" means any change to source, tests, config, build/CI files, dependencies, schemas, migrations, or scripts.
  Do NOT log chats that only touched documentation (README, `docs/`, comments, AGENTS.md) or made no changes.
- Chronological, append-only: add the new entry at the END of the file, never edit or remove earlier entries.
  Create the file with a `# Change log` heading if it does not exist.
- One entry per chat. If the chat continues after the entry is written, update that same entry instead of adding a second one.
- Entry format:

      ## YYYY-MM-DD HH:MM (UTC) - <short title>
      - Task: <task-slug or one-line request summary>
      - Changes: <what changed, grouped logically; not a raw diff>
      - Files: `path/a`, `path/b`
      - Why: <reason, linked spec/issue if any>
      - Verification: <commands run and results; what was NOT run>
      - Risks / follow-ups: <or "none">

- Never put secrets, credentials, or real customer data in the log.
- If the task was abandoned or only partly done, still log it and mark it "Status: partial" with what remains.

## Definition of done
- Behavior matches the spec; each requirement has a test that can actually fail.
- No new errors or warnings from build, lint, or static checks; no unrelated changes in the diff.
- Docs/comments updated where behavior changed.
- Change log entry appended (if the chat changed the codebase beyond documentation).
- Summary of changes, risks, and anything not covered by tests.

## Known pitfalls (agent mistakes to avoid)
- Do not present the scaffold landing page as a completed scheduling workflow.
- Treat CSV and integer inputs as untrusted; validate type, range, and structure before every write.
- Zero transactions are valid demand; missing demand is not zero, and the system must keep those cases distinct.
- Refresh previews must be version-bound and stale confirmations must be rejected; never mutate active state during a preview.
- Generator tie-breaks are deterministic and rely on stable IDs; do not add randomness or database-order-dependent logic.
- Keep state changes atomic across history snapshots, demand updates, and roster replacement; partial writes are rejected.

## References
- `docs/resources/SWE_Take-Home_Staff_Scheduling_System.pdf`: assignment brief.
- `data/sample_transaction_interview.csv`: supplied transaction sample for future importer work.
- `README.md`: setup, architecture, assumptions, and next steps.
