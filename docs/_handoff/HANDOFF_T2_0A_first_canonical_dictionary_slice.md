# HANDOFF T2.0A First Canonical Dictionary Slice

Status: ready for local validation

Scope:
- add the first canonical `stg -> core` ingest slice
- use the actually available T1.5 staging asset:
  `stg.nflverse_bulk_schedule_dictionary`
- keep the slice narrow and honest by canonicalizing the schedule field dictionary,
  not schedule facts
- add a dedicated `core-load` CLI command

What changed:
- added `src/new_nfl/core_load.py`
- added `core-load` command to `src/new_nfl/cli.py`
- added tests for the dictionary-style core load and CLI parsing

Target semantics:
- source table: `stg.nflverse_bulk_schedule_dictionary`
- target table: `core.schedule_field_dictionary`
- key: normalized `field`
- invalid rows: blank or null `field`
- execute mode rebuilds the target table snapshot and keeps the latest row per field

Validated expectation:
- dry-run reports source counts, distinct key count, and invalid row count
- execute rebuilds `core.schedule_field_dictionary`
- targeted tests for `core_load`, CLI parser, `stage_load`, and adapter CLI should all be green

Preferred next step after green:
- decide whether T2.0B should widen from dictionary metadata to a true schedule/facts ingest path
