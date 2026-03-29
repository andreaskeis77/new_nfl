# HANDOFF T1.5 Repair 01 Stage Load Circular Export

Status: delivered and locally validated

Scope:
- repair a circular import between `new_nfl.stage_load` and
  `new_nfl.adapters.__init__`
- keep the repair bolt narrow
- restore the import/collection gate before any T2.0 work
- document the delivery/apply workflow correction for future tranches

What changed:
- removed the `stage_load` re-export from `src/new_nfl/adapters/__init__.py`
- updated `src/new_nfl/cli.py` to import `execute_stage_load` directly from
  `new_nfl.stage_load`

Validated locally on DEV-LAPTOP:
- `python -c "import new_nfl.stage_load; print('stage_load import ok')"`
- `python -c "import new_nfl.cli; print('cli import ok')"`
- `.\.venv\Scripts\python.exe -m pytest tests/test_stage_load.py tests/test_cli_adapter.py -q`

Observed green signals:
- `stage_load import ok`
- `cli import ok`
- targeted test pair green
- temporary `_apply/` directory removed after apply
- repair committed separately as:
  `T1.5 repair: remove stage_load circular export`

Operational lesson from this repair:
- repo workflow knowledge must live in repo documentation and handoffs, not only
  in assistant memory
- ZIP apply defaults must assume the Windows user's Downloads folder
- every ZIP delivery must include an explicit DEV-LAPTOP apply block
- manual copy/paste fallback is not the default workflow

Preferred next step:
- execute `T2.0-entry` as a docs-only cycle-cut bolt:
  - sync `docs/PROJECT_STATE.md`
  - sync `docs/_handoff/README.md`
  - define `T2.0A` as the first minimal canonical `stg -> core` slice
