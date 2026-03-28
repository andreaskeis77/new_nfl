# NEW NFL First Staging Load v0.1

## Purpose

T1.5 introduces the first normalized staging load for `nflverse_bulk`.

The goal is deliberately small:

- consume the latest registered raw source file for `nflverse_bulk`
- load one CSV into one staging table
- preserve row-level provenance columns
- record the staging load in metadata

## Input contract

The staging load depends on a previously recorded source file in `meta.source_files`.

For T1.5 the source file is expected to be a CSV downloaded by the T1.4 remote fetch path.

## Output contract

For the first known remote file `dictionary_schedules.csv`, T1.5 writes:

- table: `stg.nflverse_bulk_schedule_dictionary`

The table is loaded with `ALL_VARCHAR=TRUE` to avoid premature typing decisions.

Additional provenance columns are appended:

- `_source_file_id`
- `_source_file_path`
- `_adapter_id`
- `_loaded_at`

## Runtime behavior

Dry-run:

- no database table write
- no new ingest run
- no load event
- returns the planned target table and latest source file reference

Execute:

- reads the latest source file for the adapter
- creates or replaces the first staging table
- records a new ingest run under `adapter.nflverse_bulk.stage_load`
- records a load event against `stg`

## T1 cycle closure

T1 is considered complete once:

- T1.4 remote fetch is green
- T1.5 staging load is green

After that, the next cycle starts with T2.0 canonical ingest.
