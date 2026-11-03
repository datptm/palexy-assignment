# Change log

## 2026-11-03 15:30 (UTC) - Add core scheduling red tests
- Task: `core-scheduling-logic` Stage 4 tests first
- Changes: Added a traceable test matrix, synthetic CSV helper, and red-stage tests for validation, import, service edits, metrics, generation, and refresh safety. Production code and existing fixtures were not changed.
- Files: `docs/ai/core-scheduling-logic/04-tests.md`, `tests/scheduling_support.py`, `tests/test_limits.py`, `tests/test_validation.py`, `tests/test_csv_import.py`, `tests/test_scheduling_service.py`, `tests/test_metrics.py`, `tests/test_generation.py`, `tests/test_refresh.py`
- Why: Lock down the approved `01-spec.md`, `02-design.md`, and `03-plan.md` contracts before feature implementation.
- Verification: Baseline pytest: 14 passed. Red-stage `.venv/Scripts/python.exe -m pytest -q --tb=line -p no:cacheprovider --basetemp=.test-tmp/pytest`: 63 failed for missing planned modules/service operations, 14 passed, with no collection or fixture errors. `pytest --collect-only`: 77 collected. `ruff check --no-cache .`: passed. `ruff format --check .`: 47 files formatted. `compileall -q src ui tests main.py`: passed. `git diff --check`: passed. Production behavior and performance benchmarks were not run because this is the tests-only stage.
- Risks / follow-ups: Proposed method signatures, result fields, and some error codes need manager review. Several specified edge, policy, and performance cases remain listed in `04-tests.md` for the implementation stage.
