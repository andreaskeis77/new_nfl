# NEW NFL Source Adapter Skeleton v0.1

## Purpose

This tranche introduces the first adapter abstraction layer without yet fetching real NFL data.
The goal is to freeze the runtime contract between source registry records, adapter identifiers,
dry-run planning, and future ingest orchestration.

## Scope of T1.2

T1.2 adds:

- a stable source-adapter catalog in Python
- one adapter descriptor per seeded registry source
- a dry-run adapter plan surface
- CLI commands to list and describe adapter skeletons
- tests for adapter identity, CLI exposure, and registry binding

T1.2 does not yet add:

- HTTP calls
- file downloads
- parsing logic
- staging transformations
- scheduler wiring

## Adapter identity model

The adapter identifier is intentionally aligned to the metadata `source_id` values:

- `nflverse_bulk`
- `official_context_web`
- `public_stats_api`
- `reference_html_fallback`

This keeps registry rows, adapter selection, and later ingest runs on one canonical identifier.

## Dry-run planning contract

Each adapter can already produce a plan that describes:

- registry binding state
- transport class
- extraction mode
- raw landing prefix
- stage dataset target
- source status
- implementation notes

This is a no-network contract. It exists to harden orchestration and naming before we build
the first real adapter.

## CLI surface

T1.2 adds two new commands:

- `new_nfl.cli list-adapters`
- `new_nfl.cli describe-adapter --adapter-id <id>`

These commands must remain side-effect-light. They may bootstrap the local metadata surface,
but they must not fetch external data.

## Raw landing convention

Dry-run plans point at:

- `data/raw/planned/<adapter_id>/...`

This is a planning prefix only. Real ingestion tranches may refine the final raw landing
partitioning, but T1.2 fixes the naming posture and keeps it repo-relative.

## Why this tranche exists

We already have metadata and source registry operations from T1.1. Before writing any real
fetcher, we now insert a strict adapter abstraction layer so later source-specific work can be
added in small, testable bolts.

## Expected next tranche after green

T1.3 should introduce the first real source-fetch contract with local raw landing artifacts and
run-registration updates for one adapter path.
