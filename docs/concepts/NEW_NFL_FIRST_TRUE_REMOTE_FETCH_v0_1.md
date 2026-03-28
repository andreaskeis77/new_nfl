# NEW NFL First True Remote Fetch v0.1

## Goal
Introduce the first real remote fetch path for `nflverse_bulk` while keeping the blast radius small and observable.

## Scope
- one adapter only: `nflverse_bulk`
- dry-run mode remains side-effect free
- execute mode performs a real download from a remote URL
- raw landing writes:
  - request manifest
  - fetch receipt
  - downloaded asset file
- ingest run and load event are persisted

## Non-goals
- multi-asset parallel fetch
- parsing into staging
- retry orchestration
- scheduler integration
- VPS services

## Contract
- default remote URL comes from seeded source registry metadata
- CLI can override the remote URL explicitly
- downloaded file is stored under:
  `data/raw/landed/<adapter_id>/<ingest_run_id>/`
- receipt contains checksum and byte size
