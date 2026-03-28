# NEW NFL

NEW NFL is a private NFL data platform project focused on robust ingestion, metadata-driven operations, and a high-quality local and VPS-hosted analysis surface.

## Current implementation status

- T1.0 local bootstrap and metadata baseline
- T1.1 metadata registry and pipeline state service surface
- T1.2 source adapter skeleton and adapter catalog
- T1.3 first adapter execution contract with raw landing receipts
- T1.4 first true remote fetch implementation for `nflverse_bulk`

## Current command surface

```powershell
python -m new_nfl.cli bootstrap
python -m new_nfl.cli seed-sources
python -m new_nfl.cli list-sources
python -m new_nfl.cli list-adapters
python -m new_nfl.cli describe-adapter --adapter-id nflverse_bulk
python -m new_nfl.cli run-adapter --adapter-id nflverse_bulk
python -m new_nfl.cli run-adapter --adapter-id nflverse_bulk --execute
python -m new_nfl.cli fetch-remote --adapter-id nflverse_bulk
python -m new_nfl.cli fetch-remote --adapter-id nflverse_bulk --execute
python -m new_nfl.cli list-ingest-runs --pipeline-name adapter.nflverse_bulk.remote_fetch
```

## Delivery rule

Implementation and fix tranches are delivered as flat-root ZIP packages with complete files. Manual search/replace instructions are not the standard workflow.
