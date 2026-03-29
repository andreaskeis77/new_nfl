# HANDOFF T2.0C First Browseable Core Dictionary Slice

Status: ready for local validation

Scope:
- add the first read-only browse path on top of the canonical core dictionary slice
- keep the scope limited to `core.schedule_field_dictionary`
- expose a narrow CLI surface for inspection without widening the ingest scope

What changed:
- added `src/new_nfl/core_browse.py`
- added `browse-core` command to `src/new_nfl/cli.py`
- added tests for the browse module and CLI parsing

Browse semantics:
- source object: `core.schedule_field_dictionary`
- current adapter scope: `nflverse_bulk` only
- optional filters: `--field-prefix`, `--limit`
- output order: sorted by `field`

Validated expectation:
- `browse-core --adapter-id nflverse_bulk` returns a small deterministic listing
- missing core table fails with a clear instruction to run `core-load --execute` first
- targeted tests for `core_browse`, `core_load`, `stage_load`, and CLI parsing should all be green

Preferred next step after green:
- decide whether to widen from dictionary browseability to a true schedule/facts ingest path
