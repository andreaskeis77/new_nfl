# HANDOFF T1.0B — Settings Root Override Fix

## Scope
Repair the bootstrap test surface by making `load_settings()` honor
`NEW_NFL_REPO_ROOT` during tests and controlled local runs.

## Why this tranche exists
T1.0A fixed Ruff and the over-aggressive `pip` self-upgrade in the bootstrap
script, but left `src/new_nfl/settings.py` untouched. The tests rely on a
temporary repository root override; without that override the settings object
keeps pointing at the real checkout path on disk.

## Observed failure
- `ruff check .` passed
- `pytest -q` failed in:
  - `tests/test_settings.py`
  - `tests/test_bootstrap.py`
- Root cause: `load_settings()` ignored `NEW_NFL_REPO_ROOT`

## Fix
- add explicit `NEW_NFL_REPO_ROOT` support
- keep repo-relative resolution for `NEW_NFL_DATA_ROOT` and `NEW_NFL_DB_PATH`
- leave runtime defaults unchanged for normal local development

## Expected gate state after apply
- `ruff check .` green
- `pytest -q` green
- `tools/bootstrap_local.ps1` green
- `python -m new_nfl.cli health` green

## Next step after green
Commit the pending T1.0/T1.0A/T1.0B bootstrap surface and move to T1.1.
