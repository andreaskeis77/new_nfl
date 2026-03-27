# NEW NFL System Concept v0.2

Status: Draft for architecture alignment  
Phase: A0.2  
Scope: Concept only. No runtime implementation.  
Last Updated: 2026-03-27

## 1. Purpose

This document advances the architecture concept from **A0.1** to a more operational posture.  
The goal is still to avoid premature coding, but the system is now described precisely enough to support:

- platform and storage decisions,
- phase-1 scope boundaries,
- dataset family prioritization,
- ingestion-layer responsibilities,
- future web and analysis architecture without rework.

This document is the current architecture anchor for NEW NFL until replaced by a newer concept version and corresponding ADR updates.

## 2. Product Goal

NEW NFL shall become a private, durable NFL data and analysis platform for one primary operator.  
It shall:

1. preserve historically relevant NFL text/tabular data over roughly the last 15 years and continue forward,
2. refresh important data on declared cadences, with higher frequency during the active season,
3. consolidate redundant source inputs into a canonical fact layer with retained provenance,
4. provide a strong web interface for browsing, filtering, comparing, and inspecting data,
5. support later analytics, simulation, and prediction workloads without contaminating the canonical historical record.

## 3. A0.2 Architecture Recommendation

The recommended phase-1 technical posture is:

- **Python 3.12** as the primary implementation language,
- **DuckDB** as the central analytical storage engine,
- **Parquet** as the preferred durable file format for raw/staging exchange and evidence-oriented persisted extracts,
- **filesystem-based landing and evidence structure** under a controlled repo-external data root,
- **server-rendered web UI plus HTTP API** in a Python-first application stack,
- **Windows VPS** as the target production-style runtime in early phases,
- **scheduled jobs** for retrieval, ingestion, rebuilds, and freshness checks.

This posture is chosen because the system is private, single-operator, heavily analytical, append-oriented, and expected to favor reproducibility and inspectability over multi-user transactional behavior.

## 4. Explicit Early-Phase Non-Goals

The following remain out of scope for phase 1 unless explicitly approved later:

- public or commercial multi-user productization,
- full workflow orchestration platforms before simpler scheduling is exhausted,
- object/media archival,
- prediction-first implementation before fact-platform stability,
- broad uncontrolled scraping without source governance,
- distributed microservice decomposition.

## 5. Phase-1 Capability Scope

Phase 1 is not “everything NFL.” It is a disciplined first operating platform.

### 5.1 Must-have in Phase 1

- season, week, team, game, player, roster, and schedule foundations,
- canonical identifiers and source provenance,
- historical backfill posture,
- declared refresh classes,
- dataset freshness visibility,
- read-only browse/filter/compare views in the web UI,
- run registry and ingest evidence,
- rebuildability from retained raw/staging evidence where feasible.

### 5.2 Strong candidates for Phase 1.5

- injuries,
- depth charts,
- snap counts,
- betting lines,
- weather/venue enrichments,
- advanced metrics not required for canonical base browsing.

### 5.3 Deferred to later phases

- probabilistic game simulation,
- playoff-tree simulation engine,
- feature engineering library,
- experiment tracking beyond a minimal registry structure,
- model selection and automated evaluation loops.

## 6. Primary Dataset Families

The first controlled dataset families should be:

1. seasons
2. weeks
3. teams
4. games / schedules / results
5. players
6. rosters
7. team-level aggregated stats
8. player-level aggregated stats

These families form the minimum viable canonical platform because most later capabilities depend on them.

Secondary dataset families can be added only after the primary set has:

- stable identifiers,
- stable refresh behavior,
- source coverage confidence,
- UI readability,
- acceptable reconciliation logic.

## 7. Platform Storage Posture

### 7.1 Core decision

NEW NFL should use **DuckDB + Parquet** as the default data platform posture for phase 1.

### 7.2 Why this is the default

This posture fits the actual project conditions:

- single primary operator,
- analytical rather than OLTP-heavy usage,
- strong rebuild/read patterns,
- portable local/VPS execution,
- low operational overhead,
- good fit for append-oriented ingest and denormalized read models.

### 7.3 What DuckDB is responsible for

DuckDB is responsible for:

- source-shaped staging tables,
- canonical core tables,
- read models / UI marts,
- analytics-ready views or tables,
- operational metadata tables,
- reconciliation and validation queries.

### 7.4 What Parquet is responsible for

Parquet is responsible for:

- persisted extracted artifacts where tabular persistence makes sense,
- source handoff between retrieval and ingestion steps,
- intermediate evidence and rebuild support,
- optional partitioned historical snapshots.

### 7.5 What is deliberately not chosen as the phase-1 center

The following are not the recommended phase-1 core platform:

- PostgreSQL as the main warehouse,
- SQLite as the main analytical store,
- a lakehouse stack with heavy external services,
- a distributed compute platform.

These can be revisited later if scope, concurrency, or operating constraints materially change.

## 8. Data Root and Logical Zones

The system should plan for a **repo-external data root** so that operational data, evidence, and bulk artifacts do not pollute the Git repository.

Recommended logical zones:

- `data/raw/` – retrieved source artifacts and source-linked persisted extracts
- `data/staging/` – source-normalized materializations if persisted outside DuckDB
- `data/warehouse/` – primary DuckDB file(s) and warehouse-side assets
- `data/exports/` – explicit user-facing or review-oriented exports
- `data/runtime/` – transient runtime files where needed
- `data/logs/` – service/job logs if not kept elsewhere
- `data/snapshots/` – controlled state captures, optional by phase

Exact paths will later be formalized in runtime configuration ADRs.

## 9. Layer Responsibilities

### 9.1 Raw landing

Purpose:
- preserve what was fetched,
- preserve retrieval evidence,
- support replay and diagnosis.

Rules:
- append-oriented where feasible,
- no silent destructive overwrite,
- source, timestamp, and run linkage required.

### 9.2 Source-normalized staging

Purpose:
- express source-specific semantics in stable source-shaped tables,
- isolate parser/adapter behavior from canonical reconciliation,
- make source debugging practical.

Rules:
- staging tables remain source-aware,
- can be rebuilt from raw evidence,
- may persist in DuckDB and/or Parquet depending on the pipeline step.

### 9.3 Canonical core

Purpose:
- represent the platform’s best current factual model,
- resolve conflicts,
- assign stable internal keys,
- preserve traceability.

Rules:
- canonical facts are not predictions,
- conflict resolution must be explicit,
- provenance must remain queryable.

### 9.4 Read models / UI marts

Purpose:
- fast, legible browsing and comparison,
- derived but deterministic user-facing views,
- separation of UX performance concerns from core modeling complexity.

Rules:
- rebuildable from canonical inputs,
- optimized for specific screens and queries,
- may be denormalized.

### 9.5 Analytics / feature layer

Purpose:
- support later model features and repeatable analysis datasets.

Rules:
- versioned transformation logic,
- traceable input lineage,
- distinct from UI marts.

### 9.6 Prediction / simulation registry

Purpose:
- preserve future-oriented outputs separately from historical fact.

Rules:
- never merged into canonical history,
- linked to inputs, model version, run context, and evaluation metrics.

## 10. Canonical Entity and Key Strategy

Phase 1 requires a stable internal key strategy.

### 10.1 Internal canonical keys

The platform should define internal canonical identifiers for core entities such as:

- season
- week
- team
- game
- player
- roster membership / time-bounded player-team relationship

### 10.2 External identifiers

Source-provided identifiers shall be preserved where available but treated as source-specific references, not universal truth.

### 10.3 Mapping principle

The system should maintain explicit mapping logic from source identifiers to canonical identifiers.  
No hidden one-off mapping code should become the de facto identity model.

## 11. Provenance and Reconciliation Minimum Contract

Every canonicalized record should later be supportable by metadata including, at minimum:

- source system,
- source tier,
- ingest run id,
- retrieval timestamp,
- processing timestamp,
- source-side identifier where available,
- record fingerprint or hash,
- reconciliation status,
- conflict note or rule note when applicable.

Redundancy is allowed only if evidence survives.

## 12. Refresh Classes

Phase 1 should introduce declared refresh classes before source breadth expands.

Recommended classes:

- **R0 Static/Historical** – refresh only when backfill or correction is needed
- **R1 Slow-changing** – weekly or less frequent
- **R2 In-season Daily** – daily refresh target during active season
- **R3 Event-driven / high-volatility** – reserved for later phases where technically justified

Each dataset family should later be assigned one class.

## 13. Read-Only Web Scope for Phase 1

The early web application should remain read-only and focus on clarity.

Target views:

- home/dashboard with freshness and run status summary,
- seasons and weeks browse,
- teams browse and inspect,
- games browse and inspect,
- players browse and inspect,
- roster views,
- comparison pages for teams / players / seasons where feasible,
- provenance/freshness drilldown.

Early exclusions:
- write-heavy admin surfaces,
- simulation UI,
- workflow builder UI,
- broad customization complexity.

## 14. Operating Model Recommendation

### 14.1 DEV-LAPTOP

Primary use:
- authoring,
- test execution,
- schema evolution,
- local smoke validation,
- documentation and release preparation.

### 14.2 Windows VPS

Primary use:
- scheduled retrieval and ingestion,
- hosted read-only web runtime,
- persistent warehouse/data root,
- health and freshness monitoring.

### 14.3 Runtime discipline

The production-style runtime should stay simple in early phases:

- a small number of durable services,
- scheduled jobs with explicit logs,
- evidence-producing batch runs,
- no unnecessary service explosion.

## 15. Main Risks at A0.2

The dominant architecture risks remain:

1. uncontrolled source sprawl,
2. weak identity and reconciliation rules,
3. mixing fact storage with forecast artifacts,
4. overbuilding operational complexity too early,
5. UI goals outrunning the data model,
6. absent freshness and provenance visibility.

## 16. Decisions to be Locked Next

The next architecture step should lock:

- initial physical data layout convention,
- first canonical entity list and core fields,
- initial operational metadata schema,
- source registry structure,
- phase-1 web query surface,
- scheduler/runtime pattern on the Windows VPS.

## 17. Current Recommendation

Proceed with the following posture unless a later ADR reverses it:

- **DuckDB is the phase-1 warehouse center.**
- **Parquet is the default persisted tabular exchange/evidence format.**
- **The repo remains code-light until A1 starts.**
- **Phase 1 covers canonical fact platform + read-only web foundation, not simulation.**
- **Source breadth expands only under explicit source governance.**
