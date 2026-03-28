# NEW NFL

NEW NFL is a private NFL data platform and analysis center.
This repository follows a documentation-first, systems-engineering approach with explicit
handoffs, architecture records, phased implementation, and Windows-first execution guidance.

## Current implementation status

- Architecture phase A0 is complete.
- T1.0 established the local Python package and bootstrap surface.
- T1.1 added the first metadata-management utilities and source-registry operations.
- T1.2 added a source-adapter skeleton layer and dry-run adapter planning commands.
- T1.3 adds the first real adapter execution contract for `nflverse_bulk`.
- Remote source downloading and web application runtime are not included yet.

## Local bootstrap entry points

**DEV-LAPTOP**

```powershell
.\.venv\Scripts\python.exe -m new_nfl.cli bootstrap
.\.venv\Scripts\python.exe -m new_nfl.cli seed-sources
.\.venv\Scripts\python.exe -m new_nfl.cli list-sources
.\.venv\Scripts\python.exe -m new_nfl.cli list-adapters
.\.venv\Scripts\python.exe -m new_nfl.cli describe-adapter --adapter-id nflverse_bulk
.\.venv\Scripts\python.exe -m new_nfl.cli run-adapter --adapter-id nflverse_bulk
.\.venv\Scripts\python.exe -m new_nfl.cli run-adapter --adapter-id nflverse_bulk --execute
.\.venv\Scripts\python.exe -m new_nfl.cli list-ingest-runs --pipeline-name adapter.nflverse_bulk.fetch
.\.venv\Scripts\python.exe -m new_nfl.cli show-pipeline-state --pipeline-name adapter.nflverse_bulk.fetch
.	oolsun_quality_gates.ps1
```

The bootstrap command creates the expected local directory tree, initializes the DuckDB
database, and creates the baseline metadata and schema surface required for later tranches.
