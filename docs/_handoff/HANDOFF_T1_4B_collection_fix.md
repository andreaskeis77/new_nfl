# HANDOFF T1.4B Collection Fix

Status: proposed

Scope:
- restore adapter catalog export compatibility required by T1.2/T1.3/T1.4 surfaces
- document a stricter validation sequence for future tranches

Problem observed:
- cli import failed because `new_nfl.adapters.__init__` expected
  `adapter_binding_rows` from `new_nfl.adapters.catalog`
- this caused immediate collection/import failure before runtime validation

Fix in this tranche:
- restore `adapter_binding_rows(settings)` in `src/new_nfl/adapters/catalog.py`
- keep adapter descriptor and plan behavior aligned with the T1.4 adapter model
- harden validation protocol with explicit collection-first and public-export rules

Expected next validation:
- import succeeds
- bootstrap / seed-sources succeed
- fetch contract and remote fetch commands run
- quality gates are green

Next step after green:
- commit T1.4 and close this repair bolt
