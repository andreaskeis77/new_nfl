# HANDOFF T1.2A Full-File Delivery Rule and Adapter Gate Fix

Status: ready_for_validation

Scope:
- fix the remaining Ruff/import-order issue in `tests/test_adapters.py`
- keep the Windows-safe path assertion in the adapter test
- harden repo method documents so full-file ZIP delivery is explicit and mandatory
  by default in implementation, fix, debug, and quality-gate tranches

Files in this tranche:
- `docs/ENGINEERING_MANIFEST.md`
- `docs/WORKING_AGREEMENT.md`
- `docs/DELIVERY_PROTOCOL.md`
- `tests/test_adapters.py`

Expected validation:
- `ruff check .` returns green
- `pytest -q` returns green
- adapter CLI commands remain green
- method docs clearly state that Andreas should receive complete files in ZIPs
  rather than manual search/replace instructions

Next step after green:
- commit and push T1.2A
- continue with T1.3 first real adapter fetch contract
