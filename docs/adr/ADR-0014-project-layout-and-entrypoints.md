# ADR-0014: Project Layout and Entry Points

- Status: Accepted
- Date: 2026-03-27

## Context

The project needs a first concrete directory and command surface that matches the already documented architecture while staying small
enough for an initial bootstrap tranche.

## Decision

The first executable layout will include:

- `src/new_nfl/` for Python code
- `tests/` for automated tests
- `tools/` for PowerShell automation helpers
- `data/` as the local generated working area
- `docs/` as the canonical documentation and handoff surface

The first supported entry points are:

- `python -m new_nfl.cli bootstrap`
- `python -m new_nfl.cli health`
- `tools/bootstrap_local.ps1`
- `tools/run_quality_gates.ps1`

## Consequences

- The project now has a real but intentionally narrow operational surface
- Later tranches must preserve these entry points or explicitly supersede them via ADR
- The package root and tooling are now stable enough for T1.x extensions
