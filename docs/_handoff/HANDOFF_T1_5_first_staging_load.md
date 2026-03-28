# HANDOFF T1.5 First Staging Load

Status: ready for validation

Scope:
- add the first normalized staging load for `nflverse_bulk`
- load the latest registered CSV source file into the first staging table
- record a stage-load ingest run and load event
- keep T1.5 narrow so T1 can close cleanly once green

Expected green signals:
- `stage-load --adapter-id nflverse_bulk` dry-run is side-effect free
- `stage-load --adapter-id nflverse_bulk --execute` writes `stg.nflverse_bulk_schedule_dictionary`
- row count is reported and stored in the load event
- full quality gates remain green

Next step after green:
- close T1
- start T2.0 canonical ingest and first browseable data path
