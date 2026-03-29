# Project State

## Current phase

T2.0 — Canonical Ingest Entry

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

## Current runtime posture

- local Python package
- local DuckDB metadata surface
- seeded source registry
- adapter catalog
- raw landing receipts
- first true remote fetch path with dry-run and execute modes
- first normalized staging load into `stg.nflverse_bulk_schedule_dictionary`
- CLI surface for `fetch-remote` and `stage-load`
- import/collection gate restored after the T1.5 repair bolt

## T1 foundation cycle summary

T1 is considered delivered as the ingestion foundation cycle.

What T1 established:
- technical bootstrap
- metadata and pipeline-state surface
- adapter registry and descriptor surface
- first fetch contract
- first true remote fetch
- first normalized staging load

What T1 deliberately did **not** establish:
- canonical `stg -> core` ingest
- broad multi-table canonical modeling
- browseable/query-facing data path
- broader data-quality and replay coverage beyond the current narrow slice

## Current cycle

We are now in the T2.0 entry step.

The purpose of this step is to:
1. keep the cycle cut explicit in repo documentation
2. protect T2.0 from starting on an ambiguous T1/T2 boundary
3. set the first T2.0 implementation slice as a narrow canonical ingest bolt

## Preferred next bolt

T2.0A — First canonical reference slice

Scope:
- read from `stg.nflverse_bulk_schedule_dictionary`
- create the first minimal canonical `core` object
- keep the slice narrow around a `season` / `week` reference path
- make the source-table contract explicit
- support dry-run and execute modes
- keep provenance and key validation visible

Do not mix into T2.0A:
- browseable/query-facing read paths
- additional sources
- broader canonical modeling
- scheduler or operational automation
- non-essential UX polish

## Validation posture

Before starting T2.0A:
- keep T1.5 targeted tests green
- keep the repaired import/collection gate green
- treat this T2.0 entry bolt as docs-only
