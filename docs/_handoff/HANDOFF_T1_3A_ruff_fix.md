# HANDOFF T1.3A Ruff Fix

Status: completed after validation

Scope:
- resolve the last Ruff error in `src/new_nfl/adapters/fetch_contract.py`
- keep T1.3 behavior unchanged
- preserve full-file ZIP delivery discipline

Validated target state:
- `ruff check .` passes
- `pytest -q` passes
- `run-adapter --adapter-id nflverse_bulk` dry-run still works
- `run-adapter --adapter-id nflverse_bulk --execute` still lands receipt artifacts

Note:
- This tranche is a minimal gate-repair bolt only.
- No feature or schema behavior was changed beyond the linter-compatible UTC alias update.

Next step:
- finalize T1.3 commit and proceed to T1.4 first true remote fetch implementation
