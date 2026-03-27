# ADR-0002: Data Platform and Storage Decision

Status: Accepted  
Date: 2026-03-27  
Decision Phase: A0.2

## Context

NEW NFL is a private, single-operator NFL data and analysis platform intended to run primarily on a DEV-LAPTOP for development and a Windows VPS for production-style execution.

The system must support:

- historical backfills,
- repeated reads and analytical queries,
- canonical consolidation,
- read-optimized UI models,
- provenance and freshness tracking,
- later analytical and simulation-oriented layers.

At this phase, the project needs a default storage posture that is simple, inspectable, portable, and strong enough for phase 1.

## Decision

The phase-1 data platform shall use:

- **DuckDB** as the central analytical warehouse engine,
- **Parquet** as the preferred durable tabular exchange and persisted evidence format,
- a **repo-external filesystem data root** for raw, staging, warehouse, exports, logs, and related operational assets.

## Rationale

This decision is based on the current project conditions:

1. The platform is private and effectively single-user.
2. The workload is analytical and append/rebuild oriented, not transaction-heavy.
3. The system must remain operable on Windows with low operational burden.
4. Historical rebuildability and inspectability matter more than multi-user concurrency.
5. DuckDB aligns well with denormalized marts, reconciliation queries, and local/VPS portability.
6. Parquet provides durable, portable tabular persistence outside the warehouse file itself.

## Consequences

### Positive

- low operational overhead,
- good local/VPS portability,
- strong fit for analytical queries,
- easy export/rebuild patterns,
- good support for deterministic read models.

### Negative / trade-offs

- not designed as a high-concurrency transactional system,
- service boundaries must remain disciplined because there is no external DB server layer doing that discipline for us,
- some operational patterns differ from classic server-database assumptions,
- future scale changes may require revisiting the decision.

## Explicit non-decisions

This ADR does not yet define:

- exact database file naming,
- exact filesystem paths,
- table schemas,
- index/materialization policy,
- API/web framework implementation,
- scheduler tool implementation.

Those decisions remain for later ADRs and implementation phases.

## Alternatives considered

### PostgreSQL-centric primary store

Rejected for phase 1 as the default center because it adds operational overhead without solving the main early-phase needs better than DuckDB for this project profile.

### SQLite-centric primary store

Rejected as the main platform because the expected analytical posture and warehouse-style querying model are a weaker fit.

### Multi-service lakehouse stack

Rejected as premature complexity for a private single-operator system at this stage.

## Review trigger

Revisit this ADR if:

- concurrency requirements materially change,
- the VPS runtime model changes substantially,
- dataset volume or workload profile exceeds the practical posture for the chosen stack,
- phase-2 product goals require stronger transactional guarantees.
