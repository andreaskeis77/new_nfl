# ADR-0003: Ingestion Layering

Status: Accepted  
Date: 2026-03-27  
Decision Phase: A0.2

## Context

NEW NFL intends to ingest data from multiple source types with varying reliability, structure, and cadence.  
The project requires provenance, rebuildability, source-specific debugging, and later canonical reconciliation.

Without explicit layers, source semantics, canonical truth, UI performance needs, and future model inputs will blur into one another.

## Decision

NEW NFL shall use the following explicit data layers:

1. **Raw Landing**
2. **Source-Normalized Staging**
3. **Canonical Core**
4. **Read Models / UI Marts**
5. **Analytics / Feature Layer**
6. **Prediction / Simulation Registry**

## Layer intent

### 1. Raw Landing
Retain retrieval artifacts and source-linked evidence.

### 2. Source-Normalized Staging
Express source-shaped tables after technical normalization but before cross-source consolidation.

### 3. Canonical Core
Represent the platform’s best factual truth with explicit reconciliation and traceable provenance.

### 4. Read Models / UI Marts
Provide denormalized, deterministic, performance-oriented views for the web interface.

### 5. Analytics / Feature Layer
Prepare reproducible model and analysis inputs.

### 6. Prediction / Simulation Registry
Preserve non-canonical future-facing outputs separately from factual history.

## Rules

- Predictions shall never be treated as canonical facts.
- UI marts shall not become the de facto canonical truth.
- Source staging shall remain source-aware.
- Every canonicalized fact must remain traceable to source evidence and run context.
- Layer skipping requires explicit ADR-level approval.

## Consequences

### Positive

- simpler debugging,
- clearer rebuild paths,
- better provenance,
- safer future extension into simulations,
- less UI/data-model coupling.

### Negative / trade-offs

- more explicit structures to maintain,
- some additional transformation overhead,
- stronger upfront modeling discipline required.

## Review trigger

Revisit if implementation experience proves that one layer is redundant or if an additional layer is needed for operational clarity.
