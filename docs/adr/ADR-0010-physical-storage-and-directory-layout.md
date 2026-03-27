# ADR-0010: Physical Storage and Directory Layout

Status: Accepted  
Date: 2026-03-27  
Phase: A0.4

## Context

NEW NFL requires a physical platform posture that is simple enough for deterministic local development and early VPS deployment, while still separating raw acquisition artifacts, canonical database state, marts, analytics outputs, and operational evidence.

Without a defined physical layout, the project risks:

- data sprawl
- ambiguous storage ownership
- hidden local conventions
- poor transferability to the VPS
- weak cleanup and retention discipline

## Decision

The project adopts a **filesystem-structured single-node posture** for phase 1.

Repository-relative storage zones are established as the physical baseline:

- `data/raw/`
- `data/stage/`
- `data/curated/`
- `data/marts/`
- `data/analytics/`
- `data/simulations/`
- `data/tmp/`
- `var/logs/`
- `var/runs/`
- `var/locks/`
- `var/reports/`
- `var/cache/`

The canonical DuckDB file is expected to live under `data/`, with one designated active database file per environment.

## Consequences

### Positive

- simple to understand
- easy to script and inspect
- fits Windows development and VPS rollout
- aligns with metadata-first evidence retention
- supports future retention and backup policies

### Negative

- filesystem discipline becomes important
- raw storage can grow quickly
- some duplication between relational and file-based evidence is expected

## Follow-on requirements

- bootstrap tooling must create required directories deterministically
- runbook must document retention expectations
- metadata schema must reference file artifacts explicitly
