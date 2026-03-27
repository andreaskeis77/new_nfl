# NEW NFL Technical Bootstrap v0.1

## Purpose

T1.0 is the first implementation tranche after the architecture sequence A0.1–A0.4. Its purpose is not to ingest NFL data yet.
Its purpose is to establish a minimal but real technical surface that can be executed, tested, and extended without violating the
project's documentation-first and handoff-heavy engineering method.

## Included in T1.0

- Python package root under `src/new_nfl/`
- Minimal CLI with deterministic local entry points
- Local bootstrap logic for directory creation
- Baseline DuckDB database initialization
- Baseline metadata schemas and control tables
- Minimal quality gate script
- Minimal Windows-first bootstrap script
- Smoke and bootstrap tests

## Explicitly excluded from T1.0

- Source adapters
- Scheduled jobs
- VPS deployment
- Web application runtime
- Canonical business tables
- Feature engineering
- Simulation pipelines

## T1.0 acceptance posture

T1.0 is successful when a clean checkout on the development laptop can:

1. create a local virtual environment,
2. install the package and dev dependencies,
3. initialize the baseline directory tree,
4. create the baseline DuckDB database,
5. create the baseline schema and metadata tables,
6. pass the local quality gate script.

## Local command surface

**DEV-LAPTOP**

```powershell
.	oolsootstrap_local.ps1
.\.venv\Scripts\python.exe -m new_nfl.cli health
.	oolsun_quality_gates.ps1
```

## Transition to T1.1

T1.1 should add the first metadata management utilities and a registry-safe mechanism to seed or update `meta.source_registry`
without introducing real ingestion logic.
