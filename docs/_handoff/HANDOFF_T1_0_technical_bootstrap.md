# HANDOFF T1.0 — Technical Bootstrap

## Scope

T1.0 introduces the first real implementation surface for NEW NFL after the A0 architecture sequence.

## Included

- Python package bootstrap
- local settings surface
- baseline DuckDB initialization
- baseline metadata tables
- local CLI
- local quality-gate script
- local bootstrap script
- baseline tests

## Expected validation

**DEV-LAPTOP**

```powershell
.	oolsootstrap_local.ps1
.\.venv\Scripts\python.exe -m new_nfl.cli health
.	oolsun_quality_gates.ps1
```

## Green state definition

T1.0 is green when the commands above complete successfully and the local DuckDB file exists under `data/db/new_nfl.duckdb`.

## Next step after green

T1.1 should introduce metadata-management utilities and a safe initial source-registry seeding mechanism.
