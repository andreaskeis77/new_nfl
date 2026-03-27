# ADR-0013: Python Runtime and Toolchain

- Status: Accepted
- Date: 2026-03-27

## Context

The project needs a first executable surface that works on the Windows-based development laptop and can later be reproduced on the
Windows VPS. The first runtime choice must minimize friction, keep the entry points explicit, and support a documentation-first flow.

## Decision

The project will use:

- Python package layout under `src/`
- `pyproject.toml` as the single package and tool configuration surface
- `venv` on Windows as the default local environment mechanism
- PowerShell scripts for local bootstrap and quality gates
- `pytest` for tests
- `ruff` for linting
- `duckdb` as the local analytical storage engine for the bootstrap phase

## Consequences

### Positive

- Explicit and conventional Python layout
- Low-friction bootstrap on the development laptop
- Easy later reproduction on the VPS
- Clean transition from architecture documents into real testable code

### Negative

- Windows-specific scripts must be maintained carefully
- Tooling still needs later hardening for CI and VPS automation

## Notes

This ADR does not decide CI/CD tooling yet. It decides only the first executable development surface.
