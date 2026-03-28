# ADR-0024 Stage Load Contract and Provenance Columns

## Status
Accepted

## Decision

Every T1.5 staging table load appends these provenance columns:

- `_source_file_id`
- `_source_file_path`
- `_adapter_id`
- `_loaded_at`

The load event for the first staging load is recorded as:

- `event_kind=stage_loaded`
- `target_schema=stg`
- `target_object=<table name>`

## Rationale

The first staging layer must preserve traceability without forcing canonical modeling too early.

These columns are enough for:

- debugging
- replay inspection
- raw-to-stage provenance
- later canonical joins and quality checks
