# Project State

## Current phase

- Phase: T1.2 Source Adapter Skeleton
- Status: ready for local import, execution, and validation
- Latest intended scope: add adapter abstraction, registry-bound dry-run planning, and CLI
  visibility for source adapter skeletons without yet fetching real data

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

## T1.2 target output

- `src/new_nfl/adapters/` adapter skeleton package
- registry-aligned adapter descriptors for the four seeded default sources
- dry-run adapter planning contract
- additional CLI entry points for adapter listing and description
- adapter-focused tests
- concept and ADR coverage for adapter posture

## Immediate next validation

**DEV-LAPTOP**

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m new_nfl.cli bootstrap
.\.venv\Scripts\python.exe -m new_nfl.cli seed-sources
.\.venv\Scripts\python.exe -m new_nfl.cli list-adapters
.\.venv\Scripts\python.exe -m new_nfl.cli describe-adapter --adapter-id nflverse_bulk
.	oolsun_quality_gates.ps1
```

## Expected next tranche after green

- T1.3 first real adapter fetch contract and raw landing artifact capture
