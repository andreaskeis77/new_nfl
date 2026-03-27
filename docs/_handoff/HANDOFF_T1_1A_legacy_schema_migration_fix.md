# HANDOFF T1.1A Legacy Schema Migration Fix

Status: completed

Scope:
- repair T1.1 runtime failures against an existing local DuckDB created by T1.0
- add compatibility logic for legacy metadata column names from the earlier bootstrap surface
- align CLI runtime behavior with green pytest results

Problem observed:
- `seed-sources` failed against an existing local database with `NOT NULL constraint failed: source_registry.source_key`
- `set-pipeline-state` failed against an existing local database with `NOT NULL constraint failed: pipeline_state.pipeline_key`
- root cause: T1.1 introduced new metadata column names but did not migrate or dual-write against the legacy T1.0 local schema

Fix applied:
- metadata surface now backfills legacy-to-modern columns during bootstrap/ensure
- write paths now support both modern and legacy columns where needed
- migration tests were added for legacy `source_registry` and `pipeline_state`

Validated target state:
- existing local databases from T1.0 can be used without manual deletion
- `seed-sources` works on both fresh and legacy metadata surfaces
- `set-pipeline-state` and `show-pipeline-state` work on both fresh and legacy metadata surfaces

Next step:
- rerun T1.1 runtime commands and then proceed to T1.2 source adapter skeleton
