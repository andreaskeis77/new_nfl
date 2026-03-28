# HANDOFF T1.4 First True Remote Fetch

Status: ready_for_validation

## Scope
- first true remote fetch implementation for `nflverse_bulk`
- dry-run remains side-effect free
- execute mode downloads one real remote asset
- metadata and raw landing receipts are written

## Validation target
- `fetch-remote --adapter-id nflverse_bulk` returns dry-run contract
- `fetch-remote --adapter-id nflverse_bulk --execute` downloads one file
- `list-ingest-runs --pipeline-name adapter.nflverse_bulk.remote_fetch` shows the run
- `ruff` and `pytest` are green

## Cycle note
T1 is not complete yet. The current T1 cycle closes after:
- T1.4 green
- T1.5 first normalized staging load green
