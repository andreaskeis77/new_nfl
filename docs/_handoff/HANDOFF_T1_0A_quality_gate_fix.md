# HANDOFF T1.0A - Quality Gate Fix

## Scope
Repair the first technical bootstrap tranche after successful local initialization exposed a red lint gate and an avoidable bootstrap-script weakness on Windows.

## Validated State
- Editable install works in the local virtual environment.
- Baseline DuckDB bootstrap succeeds.
- `new_nfl.cli health` returns `STATUS=ok`.
- `pytest` is green.
- Remaining issue in T1.0 was limited to lint findings and the unnecessary `pip` self-upgrade step in `tools/bootstrap_local.ps1`.

## Changes in this tranche
- Remove unused imports and line-length violations.
- Normalize import ordering in `src/new_nfl/bootstrap.py`.
- Remove the forced `pip install --upgrade pip` step from the local bootstrap script.
- Preserve T1.0 scope: still no ingestion, scheduler, VPS deployment, or web application code.

## Expected Gate Result
- `ruff check .` green.
- `pytest` green.
- `tools/bootstrap_local.ps1` completes without attempting a `pip` self-upgrade.

## Next Step
Proceed to T1.1 only after local quality gates are green and this repair is committed.
