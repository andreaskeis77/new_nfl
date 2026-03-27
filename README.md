# NEW NFL

NEW NFL is a private NFL data platform and analysis center. This repository follows a documentation-first,
systems-engineering approach with explicit handoffs, architecture records, phased implementation, and
Windows-first execution guidance.

## Current implementation status

- Architecture phase A0 is complete.
- T1.0 introduces the first technical bootstrap.
- No ingestion adapters or web application runtime are included yet.
- The current code establishes the local Python package, storage/bootstrap logic, and baseline tests.

## Local bootstrap entry points

**DEV-LAPTOP**

```powershell
.\.venv\Scripts\python.exe -m new_nfl.cli bootstrap
.\tools\run_quality_gates.ps1
```

The bootstrap command creates the expected local directory tree, initializes the DuckDB database,
and creates the baseline metadata and schema surface required for later tranches.
