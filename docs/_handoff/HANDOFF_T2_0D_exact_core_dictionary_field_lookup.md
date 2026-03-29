# HANDOFF T2.0D Exact Core Dictionary Field Lookup

Status: ready for local validation

Scope:
- add the first exact lookup path on top of the browseable core dictionary slice
- keep the bolt read-only
- expose one exact field lookup command for `core.schedule_field_dictionary`

What changes:
- add `src/new_nfl/core_lookup.py`
- extend `src/new_nfl/cli.py` with `describe-core-field`
- add focused tests for lookup behavior and CLI parsing

What this bolt does not do:
- no new ingest path
- no schema change
- no multi-table browse surface
- no fuzzy search semantics

Preferred next step after local validation:
- either a small browse refinement bolt
- or the first non-dictionary factual source slice for T2.1
