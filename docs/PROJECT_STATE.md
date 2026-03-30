# Project State

## Current phase

T2.2A — VPS Deploy Runbook for Preview Release

## Completed

- A0 architecture and method foundation
- T1.0 local bootstrap
- T1.1 metadata registry
- T1.2 adapter skeleton
- T1.3 first fetch contract
- T1.4 first true remote fetch
- T1.5 first normalized staging load for `nflverse_bulk`
- T1.5 repair 01: remove the `stage_load` circular export and restore the import/collection gate
- T1.x method hardening for artifact apply and validation workflow
- T2.0 entry cycle cut
- T2.0A first canonical dictionary core load
- T2.0B methodik bolt for separation of `Einordnung` and `Aktion`
- T2.0C first browseable core dictionary slice
- T2.0D exact core dictionary field lookup
- T2.0E negative lookup miss-path hardening
- T2.0F core dictionary browse with `data_type` filter
- T2.0G core dictionary summary by `data_type`
- T2.1A stage-load source-file pinning
- T2.1B source-file discovery for operators
- T2.1C local HTML preview for core dictionary
- T2.1D local mini webserver for preview

## Current runtime posture

- local Python package with CLI surface
- local DuckDB metadata surface
- seeded source registry
- adapter catalog
- raw landing receipts
- true remote fetch path with dry-run and execute modes
- source-file discovery and explicit `source_file_id` pinning
- first normalized staging load into `stg.nflverse_bulk_schedule_dictionary`
- first canonical core load into `core.schedule_field_dictionary`
- browse / exact lookup / summary over the core dictionary
- local HTML preview export
- local mini webserver for preview

## Current release posture

The project now has a **local preview-release candidate**.

That means:
- data can be fetched and loaded locally
- the first canonical core object can be built locally
- the first web-facing preview can be rendered and served locally

What is still missing before the first VPS preview release:
- a pinned VPS runbook with exact operator steps
- a preview release cut that is replayed on the VPS
- a VPS smoke test covering `/healthz` and `/`
- an explicit rollback / restart note for the preview service

## Current cycle

We are now in T2.2 release preparation.

## Preferred next bolt

T2.2B — VPS preview release execution and smoke test
