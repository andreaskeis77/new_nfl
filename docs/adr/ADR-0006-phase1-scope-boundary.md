# ADR-0006: Phase-1 Scope Boundary

Status: Accepted  
Date: 2026-03-27  
Decision Phase: A0.2

## Context

NEW NFL has a very broad long-term vision: durable data collection, rich browsing, comparison, provenance, freshness visibility, later simulation, and later prediction quality tracking.

Without a formal phase-1 boundary, the project risks immediate scope sprawl and unstable architecture.

## Decision

Phase 1 is limited to building the **canonical fact platform and read-only web foundation**.

This includes:

- core historical NFL fact datasets,
- source provenance and reconciliation posture,
- freshness and ingest visibility,
- read-only browse/filter/compare UI,
- VPS-ready scheduled refresh posture.

This excludes:

- simulation engines,
- forecasting models,
- prediction evaluation loops beyond minimal future registry preparation,
- public or multi-user product features,
- broad admin workflows,
- uncontrolled expansion into every possible dataset family.

## Rationale

This scope boundary protects:

- architecture stability,
- identity model clarity,
- reconciliation maturity,
- operator usability,
- implementation speed with lower rework risk.

## Consequences

### Positive

- earlier working system,
- lower cognitive load,
- clearer acceptance criteria,
- better chance of robust provenance and freshness visibility.

### Negative / trade-offs

- some interesting advanced use cases are intentionally delayed,
- some source families will wait even if technically available,
- early UI may feel narrower than the long-term vision.

## Review trigger

Revisit when the core fact platform is operational, browseable, and refreshed reliably on the VPS.
