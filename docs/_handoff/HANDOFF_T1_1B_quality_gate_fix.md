# HANDOFF T1.1B Quality Gate Fix

Status: ready for validation

Scope:
- repair Ruff failures introduced by T1.1A
- keep the legacy metadata migration behavior from T1.1A intact
- avoid any change to the functional CLI paths already validated on the local DuckDB state

Validated intent:
- `seed-sources` still succeeds against a legacy T1.0 database
- `set-pipeline-state` still succeeds against a legacy T1.0 database
- `show-pipeline-state` still returns the persisted state
- `ruff check .` returns green
- `pytest -q` returns green

Files in this bolt:
- `src/new_nfl/metadata.py`
- `tests/test_metadata_migration.py`
- `docs/_handoff/HANDOFF_T1_1B_quality_gate_fix.md`

Next step after green validation:
- commit and push T1.1B
- then proceed to T1.2 source adapter skeleton
