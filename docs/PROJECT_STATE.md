# Project State

## Current phase
- Phase: T1.0 Technical Bootstrap
- Status: ready for implementation import and local execution
- Latest intended scope: establish the first executable local package, bootstrap commands, baseline DuckDB metadata surface, and green local quality gates

## Completed phases
- T0.x method foundation
- A0.1 system concept and ADR baseline
- A0.2 data platform and phase-1 scope
- A0.3 source governance and metadata model
- A0.4 physical platform blueprint and metadata schema outline

## T1.0 target output
- `pyproject.toml`
- `src/new_nfl/` package root
- `tests/` baseline tests
- `tools/` baseline PowerShell command surface
- `data/` local working directories created by bootstrap
- `data/db/new_nfl.duckdb` created by bootstrap
- baseline `meta` control tables created by bootstrap

## Immediate next validation
**DEV-LAPTOP**

```powershell
.\tools\bootstrap_local.ps1
.\.venv\Scripts\python.exe -m new_nfl.cli health
.\tools\run_quality_gates.ps1
```

## Expected next tranche after green
- T1.1 metadata-management utilities and initial source-registry seeding
