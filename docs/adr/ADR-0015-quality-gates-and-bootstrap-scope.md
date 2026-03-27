# ADR-0015: Quality Gates and Bootstrap Scope

- Status: Accepted
- Date: 2026-03-27

## Context

The project must avoid the common failure mode where a new codebase starts with informal commands, untested setup steps, and unclear
success criteria. The first implementation tranche therefore needs explicit gates.

## Decision

T1.0 is constrained to the following scope:

- local Python environment bootstrap,
- baseline DuckDB initialization,
- baseline metadata schemas and tables,
- deterministic CLI entry points,
- baseline automated tests,
- baseline lint and test gate script.

The local green gate for T1.0 is:

1. `tools/bootstrap_local.ps1` completes successfully,
2. `python -m new_nfl.cli health` returns success,
3. `tools/run_quality_gates.ps1` completes successfully.

## Consequences

- T1.0 remains intentionally small
- The project gets a hard executable baseline before any ingestion code is added
- Later tranches can extend from a reproducible green state instead of a documentation-only baseline
