# NEW NFL Physical Platform Blueprint v0.1

Status: Draft for architectural baseline  
Phase: A0.4  
Scope: Physical data platform blueprint before runtime bootstrap

## 1. Purpose

This document translates the logical architecture from A0.1-A0.3 into a physical target state for the first implementation phase of NEW NFL.

It does **not** define final production-scale infrastructure. It defines the first durable, operable, and testable platform posture that can be built incrementally on the development laptop and later deployed to the Windows VPS.

## 2. Design goals

The physical platform must satisfy the following design goals:

1. **Deterministic local development**
   - one canonical local repository
   - one canonical local workspace root
   - one canonical command surface

2. **Operational continuity**
   - ingestion state must survive process restarts
   - audit history must survive code changes
   - web browse models must be regenerated predictably

3. **Metadata-first operation**
   - source registry, run registry, DQ events, and load events are first-class system assets
   - no data movement without traceability

4. **Storage pragmatism**
   - start with a single-node platform posture that is easy to inspect, back up, and reason about
   - avoid premature service sprawl

5. **Separation of concerns**
   - raw acquisition artifacts
   - relational metadata and canonical facts
   - derived marts
   - analytics / simulation artifacts
   must not collapse into one undifferentiated storage bucket

## 3. Recommended phase-1 physical posture

### 3.1 Core platform choice

Phase 1 uses the following primary physical posture:

- **Git repository** for code, docs, and small durable project artifacts
- **DuckDB** as the canonical local analytical database
- **Parquet** as the durable raw/curated file format for larger external payloads and extracted intermediate datasets
- **Local filesystem directories** for controlled raw landing, exports, snapshots, and evidence artifacts

### 3.2 Why this posture is recommended

This posture is recommended because it gives:

- fast local iteration
- excellent inspectability
- simple VPS transferability
- low infrastructure overhead
- strong compatibility with analytics workflows
- strong fit for append-oriented historical data

### 3.3 What is intentionally deferred

The following are deferred beyond the first technical bootstrap unless a hard constraint appears:

- multi-node database deployment
- distributed queue infrastructure
- external orchestration platform
- object store dependency
- container-first runtime model
- service mesh or microservice split

## 4. Canonical repository root

Canonical development repository root:

`C:\projekte\newnfl`

Canonical VPS application root will be defined later, but must mirror the local structure conceptually.

## 5. Recommended top-level repository layout

```text
newnfl/
├─ docs/
├─ src/
├─ tests/
├─ tools/
├─ scripts/
├─ config/
├─ data/
│  ├─ raw/
│  ├─ stage/
│  ├─ curated/
│  ├─ marts/
│  ├─ analytics/
│  ├─ simulations/
│  └─ tmp/
├─ var/
│  ├─ logs/
│  ├─ runs/
│  ├─ locks/
│  ├─ reports/
│  └─ cache/
└─ .venv/
```

## 6. Filesystem zones

### 6.1 `data/raw/`
Purpose:
- immutable or minimally touched raw acquisition artifacts
- source payload snapshots
- file-based fallback evidence

Rules:
- write-once per acquisition event where feasible
- partition by source and acquisition date
- do not overwrite previous raw evidence silently

### 6.2 `data/stage/`
Purpose:
- source-normalized extracted datasets
- temporary-but-repeatable intermediate structures

Rules:
- may be regenerated
- still traceable to source payload and run id
- not yet canonical truth

### 6.3 `data/curated/`
Purpose:
- optional Parquet-based durable outputs supporting curated cross-run assets
- exported canonical subsets or stable dimensional views when beneficial

Rules:
- only generated from validated upstream layers
- regeneration procedure must be documented

### 6.4 `data/marts/`
Purpose:
- read-optimized outputs for browse and comparison surfaces
- table extracts supporting web views

### 6.5 `data/analytics/`
Purpose:
- feature sets
- model inputs
- evaluation datasets
- backtest-ready prepared datasets

### 6.6 `data/simulations/`
Purpose:
- simulation inputs
- simulation outputs
- evaluation artifacts
- benchmark snapshots

### 6.7 `var/logs/`
Purpose:
- structured and human-readable runtime logs

### 6.8 `var/runs/`
Purpose:
- run manifests
- captured evidence
- per-run summaries
- small machine-readable artifacts

### 6.9 `var/reports/`
Purpose:
- quality gate outputs
- DQ summaries
- ingest freshness reports
- release evidence

## 7. Database posture

## 7.1 Canonical database file

The implementation phase should use one primary DuckDB file for the working system, for example:

`data/newnfl.duckdb`

Optional secondary files may later exist for sandboxing, migration rehearsal, or snapshot comparison, but the system must designate exactly one canonical active database file in each environment.

## 7.2 Schema family posture

Recommended schema families inside DuckDB:

- `meta` — registries, runs, audit, DQ, config snapshots
- `raw` — optional raw relational landing mirrors where useful
- `stg` — source-normalized staging tables
- `core` — canonical entities and facts
- `mart` — browse and comparison read models
- `feat` — feature-generation outputs
- `sim` — simulation registry and results
- `scratch` — explicitly non-canonical, ephemeral work area

## 7.3 Core rule

No table belongs in `core` unless:

- canonical keys are defined
- source precedence is defined
- provenance columns are defined
- DQ expectations are defined

## 8. Environment posture

## 8.1 Development laptop

Primary use:
- authoring
- unit tests
- schema evolution
- local ingest rehearsal
- web foundation work
- documentation updates

## 8.2 Windows VPS

Primary use:
- durable scheduled ingestion
- continuously available browse surface
- stored logs and run evidence
- health endpoints and service monitoring

## 8.3 Parity rule

Local and VPS structures should be as similar as practical.

Differences are acceptable only when:
- caused by OS/service realities
- documented in runbook or ADR
- not hidden inside undocumented scripts

## 9. Backup and recovery posture

Phase-1 backup posture should include:

- Git-based code and docs history
- DuckDB file backup or snapshot strategy
- retention-aware storage for raw artifacts
- retained run manifests and release evidence

Minimum requirement:
- no single ingestion run should be the only source of truth for its own metadata

## 10. Operational evidence posture

The platform must make it easy to answer:

- what ran
- when it ran
- against which sources
- with which parser version
- with which outcome
- with which warnings or DQ events

This evidence may be split between:
- relational metadata tables
- structured files under `var/runs/`
- summarized docs under `docs/_ops/`

## 11. Security and secrets posture

Phase-1 rules:

- no secrets committed to Git
- environment-specific secrets in non-tracked config
- no raw cookies/tokens inside docs or handoff files
- scraping/session-based connectors require explicit handling and later hardening

## 12. Constraints and risks

Main risks at this stage:

- too many source-specific storage conventions
- silent growth of raw storage volume
- mixing canonical and exploratory data
- lack of retention discipline
- weak naming and partition conventions

## 13. Exit criteria for A0.4

A0.4 is successful when the project has:

- one recommended physical storage posture
- one recommended repository and filesystem layout
- one defined schema family map
- one defined canonical database posture
- one documented local/VPS split
- one documented metadata-first operational evidence model

## 14. Leads into next phase

This document enables the first technical bootstrap tranche, which should introduce:

- repository bootstrap scaffolding
- config surface
- initial folder creation automation
- database bootstrap
- metadata schema creation
- first health and smoke checks
