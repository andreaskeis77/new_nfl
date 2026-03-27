# ADR-0001: Repository and Operating Model

Status: Accepted  
Date: 2026-03-27

## Context

NEW NFL is intended to be developed over a long period with repeated handoffs, PowerShell-based execution, local development on a Windows laptop, and later VPS deployment on Windows. Continuity and traceability are critical because the project will span documentation, ingestion, web UI, operations, and later simulation.

## Decision

The project will use a repository-first operating model with:

- tranche-based delivery,
- mandatory documentation updates for material changes,
- explicit execution-location labeling (`DEV-LAPTOP`, `VPS-USER`, `VPS-ADMIN`),
- handoff artifacts stored in the repository,
- green-gate progression rather than “fix later” progression,
- ZIP-based file delivery from ChatGPT during implementation phases.

## Consequences

Positive:
- work remains reproducible across sessions,
- operational ambiguity is reduced,
- repository state becomes the canonical continuation point.

Negative:
- discipline overhead is higher,
- small changes require more formal bookkeeping than ad-hoc work.

## Notes

This ADR is foundational and should remain stable unless the project operating model changes materially.
