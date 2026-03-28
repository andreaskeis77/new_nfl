# ADR-0023 First Normalized Staging Load

## Status
Accepted

## Decision

The first staging load will target a single CSV-backed staging table for `nflverse_bulk`.

The first table is:

- `stg.nflverse_bulk_schedule_dictionary`

The first implementation uses:

- latest registered source file for the adapter
- `read_csv_auto(..., HEADER=TRUE, ALL_VARCHAR=TRUE)`
- appended provenance columns for source file and adapter identity

## Rationale

This keeps T1.5 narrow and robust.

We want a working vertical slice from:

- remote raw fetch
- source file registration
- staging table load
- load event metadata

without introducing broad typing or canonical modeling yet.
