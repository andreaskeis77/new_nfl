# ADR-0012: Canonical Schema Family Boundaries

Status: Accepted  
Date: 2026-03-27  
Phase: A0.4

## Context

The project now has logical layering and metadata governance, but still requires a stable schema-family map for the physical database posture.

Without clear boundaries, staging, canonical facts, marts, feature outputs, and simulation results will blur together and weaken both maintainability and trust.

## Decision

The project adopts the following schema-family boundaries inside the canonical DuckDB database:

- `meta` — registries, runs, audit, DQ, lineage helpers, freshness, quarantine
- `raw` — optional relational raw mirrors when useful
- `stg` — source-normalized staging tables
- `core` — canonical entities and canonical facts
- `mart` — browse and comparison read models
- `feat` — derived feature sets for analytics
- `sim` — simulation registry, inputs, outputs, evaluation
- `scratch` — explicitly non-canonical, temporary structures

## Boundary rules

1. `core` may only contain canonicalized entities and facts.
2. `stg` may be source-specific and may be regenerated.
3. `mart` exists for consumption shape, not truth ownership.
4. `feat` must be derivable from upstream accepted layers.
5. `scratch` is never a contractual dependency for product surfaces.

## Consequences

### Positive

- easier reasoning about table placement
- clearer lifecycle expectations per schema family
- safer future expansion into analytics and simulation

### Negative

- more up-front naming discipline is required
- developers must resist placing convenience tables in the wrong schema

## Follow-on requirements

- bootstrap DDL must create these schema families
- future ADRs may refine table placement rules, but must not collapse the boundary model without justification
