# Project State

## Current phase

- Phase: T1.3 First Fetch Contract
- Status: ready for local import, execution, and validation
- Latest intended scope: add the first real adapter execution contract for `nflverse_bulk`,
  including dry-run and execute mode, landed raw receipt artifacts, ingest-run metadata,
  and load-event capture without yet downloading remote source payloads

## Completed phases

- T0.x method foundation
- A0.1 system concept and ADR baseline
- A0.2 data platform and phase-1 scope
- A0.3 source governance and metadata model
- A0.4 physical platform blueprint and metadata schema outline
- T1.0 technical bootstrap
- T1.0A quality gate repair
- T1.0B settings override repair
- T1.0C repo cleanup
- T1.0D delivery protocol documentation
- T1.1 metadata registry implementation
- T1.1A legacy schema migration repair
- T1.1B quality gate repair
- T1.1C final gate and delivery documentation
- T1.2 source adapter skeleton
- T1.2A full-file delivery rule codification

## T1.3 target output

- one real adapter execution contract for `nflverse_bulk`
- dry-run mode with no side effects
- execute mode with landed raw receipt artifacts
- ingest-run metadata capture for adapter execution
- load-event metadata capture for raw landed contract artifacts
- CLI visibility for adapter execution and ingest-run listing
- concept and ADR coverage for the first fetch contract posture

## Immediate next validation

**DEV-LAPTOP**

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m new_nfl.cli bootstrap
.\.venv\Scripts\python.exe -m new_nfl.cli seed-sources
.\.venv\Scripts\python.exe -m new_nfl.cli run-adapter --adapter-id nflverse_bulk
.\.venv\Scripts\python.exe -m new_nfl.cli run-adapter --adapter-id nflverse_bulk --execute
.\.venv\Scripts\python.exe -m new_nfl.cli list-ingest-runs --pipeline-name adapter.nflverse_bulk.fetch
Get-ChildItem .\dataaw\landed
flverse_bulk -Recurse
.	oolsun_quality_gates.ps1
```

## Expected next tranche after green

- T1.4 first true remote fetch implementation for one adapter
