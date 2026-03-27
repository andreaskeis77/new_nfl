# NEW NFL System Concept v0.1

Status: Draft for architecture alignment  
Phase: A0.1  
Scope: Concept only. No runtime implementation.  
Last Updated: 2026-03-27

## 1. Purpose

This document defines the first architecture-level target picture for **NEW NFL**. It is intentionally written before code implementation so that engineering method, system boundaries, data lifecycle, source strategy, operating model, and user-facing objectives are aligned before runtime decisions are locked in.

The system goal is not a small stats viewer. The goal is a **private NFL data and analysis center** with durable ingestion, strong provenance, weekly/daily refresh behavior, rich browse/filter/compare capabilities, and later simulation and prediction workflows whose own quality can be measured over time.

## 2. Product Goal

NEW NFL shall become a private, long-lived NFL data platform that:

1. ingests and preserves relevant NFL text/tabular data over roughly the last 15 years and continues forward,
2. refreshes data on a defined schedule, with higher frequency during the active season,
3. consolidates redundant source inputs into a canonical fact layer,
4. serves a high-quality web interface for browsing, filtering, comparing, and inspecting data,
5. prepares a later analysis and simulation layer without mixing forecast artifacts into the canonical historical record.

## 3. Explicit Non-Goals for the Early Phases

The following are **not** phase-1 goals:

- building prediction models before the fact platform is stable,
- building a public multi-user SaaS,
- storing media files such as video or image archives,
- optimizing for commercial monetization,
- building a broad content-management system,
- integrating every possible source before a source governance model exists.

## 4. Primary User and Operating Context

Primary user: Andreas, acting as the sole operator and primary analyst.

Operating context:

- Development is performed on the **DEV-LAPTOP** in VS Code with PowerShell.
- Production-style execution is intended for a **Windows VPS**.
- The system is private and non-commercial.
- The system must remain understandable and operable over long periods with handoffs and session changes.

## 5. Core User Capabilities

The first system concept shall support the later implementation of these user capabilities:

### 5.1 Browse
The user can inspect seasons, weeks, teams, players, games, rosters, standings-related views, injuries if available, and derived summaries through a fast web UI.

### 5.2 Compare
The user can compare teams, seasons, players, and game contexts across multiple filters without leaving the platform.

### 5.3 Inspect Provenance
The user can inspect where a record came from, when it was fetched, which run produced it, and whether multiple sources agreed or disagreed.

### 5.4 Validate Freshness
The user can see how current a dataset is, when the last successful ingest happened, what the expected cadence is, and whether a source is degraded.

### 5.5 Prepare Analysis and Simulation
The system can later support model features, backtests, playoff-tree simulations, future game simulations, and quality scoring of those outputs without re-architecting the base platform.

## 6. Data Classes

The system should plan for the following data classes. This list is conceptual and not yet a schema contract.

### 6.1 Core historical fact data
- schedules and games
- teams
- players
- rosters
- player game/week/season stats
- team game/week/season stats
- standings-related or standings-derivable datasets
- play-by-play and event-level datasets where feasible

### 6.2 Context and enrichment data
- injuries, depth charts, snap counts, transactions, venues, weather, betting lines, advanced metrics, or similar enrichments when legally and technically feasible

### 6.3 Operational metadata
- source registry
- ingest runs
- source files / retrieval artifacts
- table-level stats
- freshness expectations
- data quality results
- reconciliation outcomes

### 6.4 Analysis artifacts
- feature sets
- experiment inputs
- simulation runs
- predictions
- model evaluation outputs
- backtest and forecast quality metrics

## 7. Layered System Model

The platform shall be built as a layered data system. Layers must remain explicit and should not be blurred for convenience.

### 7.1 Raw Landing Layer
Purpose:
- retain fetched source artifacts or normalized retrieval outputs,
- preserve reproducibility and evidence,
- support reprocessing.

Properties:
- append-oriented,
- source-identifiable,
- linked to retrieval metadata,
- no silent overwrite without version evidence.

### 7.2 Source-Normalized Staging Layer
Purpose:
- convert source-specific formats into stable, source-shaped tables,
- apply technical normalization,
- preserve source semantics before consolidation.

Properties:
- still source-aware,
- suitable for validation and source-specific debugging,
- can be rebuilt from raw artifacts when needed.

### 7.3 Canonical Core Layer
Purpose:
- produce the consolidated fact model,
- resolve duplicates and conflicts,
- assign stable keys,
- represent the platform’s best factual truth at the time of processing.

Properties:
- provenance remains traceable,
- conflict resolution rules are explicit,
- facts are separated from predictions.

### 7.4 Read Models / UI Marts
Purpose:
- optimize for browsing, filtering, comparison, and fast web rendering,
- expose derived but still deterministic views,
- avoid coupling the UI directly to raw or staging complexity.

Properties:
- denormalized as needed,
- rebuildable from canonical data,
- performance-oriented.

### 7.5 Analytics / Feature Layer
Purpose:
- prepare analysis-ready datasets,
- build features for simulations and prediction experiments,
- support reproducible model inputs.

Properties:
- versioned logic,
- traceable to canonical inputs,
- separate from the read models.

### 7.6 Prediction / Simulation Registry
Purpose:
- record simulated outputs and model predictions,
- preserve assumptions and input states,
- evaluate forecast quality later.

Properties:
- never treated as canonical history,
- linked to model version, run context, and evaluation metrics,
- auditable.

## 8. Source Strategy

Source breadth is a project goal, but uncontrolled source sprawl is a system risk. NEW NFL shall therefore use a tiered source strategy.

### 8.1 Tier A – Canonical bulk sources
Use for:
- historically broad structured datasets,
- repeatable pulls,
- foundation tables.

Selection criteria:
- durable access pattern,
- structured schema,
- broad historical coverage,
- acceptable reliability.

### 8.2 Tier B – Supplementary APIs / feeds
Use for:
- domain-specific enrichments,
- near-real-time updates,
- missing dimensions not covered by Tier A.

Selection criteria:
- operational value exceeds maintenance cost,
- source adds real signal, not mere duplication,
- terms and technical stability are acceptable.

### 8.3 Tier C – Fallback extraction paths
Use for:
- controlled gap filling,
- resilience against source outages,
- cases where no structured alternative exists.

Selection criteria:
- explicit approval,
- legal/operational review,
- stronger monitoring because breakage probability is higher.

## 9. Consolidation and Provenance Rules

Every consolidated fact must remain traceable.

The system concept therefore requires later schemas and pipelines to support, at minimum:

- source identifier,
- source priority / trust tier,
- ingest run identifier,
- retrieved timestamp,
- processing timestamp,
- source-side primary identifier where available,
- record hash or equivalent fingerprint,
- reconciliation status,
- conflict notes when applicable.

Redundancy is allowed only if provenance survives. “Best value wins” without auditability is not acceptable.

## 10. Refresh and Cadence Model

The refresh model should be schedule-aware and season-aware.

Target posture:

- historical bulk backfills can run as controlled catch-up jobs,
- in-season core updates should run at least daily,
- weekly or slower refresh is acceptable for stable historical or low-volatility datasets,
- every source or dataset shall later receive a declared expected cadence and freshness SLA class.

The concept deliberately avoids exact scheduler settings at this stage. Those belong in later operating-model ADRs.

## 11. Web Application Target Picture

The first web target picture is a **private analyst console**, not a marketing website.

The web experience should emphasize:

- quick navigation,
- low-friction filtering,
- readable tables,
- comparison views,
- drill-down pages,
- visible freshness status,
- visible provenance and ingestion health where useful.

The UI should feel like a usable internal data center: calm, information-dense, and structured. It should not depend on decorative complexity.

## 12. Operating Model

### 12.1 Development
- primary development on DEV-LAPTOP,
- reproducible commands,
- PowerShell-first instructions,
- repository-first documentation,
- tranche-based delivery.

### 12.2 VPS runtime
- Windows VPS is the target for durable execution,
- long-running services and scheduled tasks must later be documented as first-class runtime components,
- logs, health endpoints, and run evidence must be part of the system, not afterthoughts.

### 12.3 Handoffs
- every meaningful tranche must leave behind project-state and handoff evidence,
- new sessions must be able to continue from repository state rather than chat memory.

## 13. Risk Areas

Key early risks:

1. **Source sprawl** – too many sources before governance exists.
2. **Key instability** – changing identifiers across sources can poison consolidation.
3. **Layer leakage** – UI or analysis logic coupled directly to staging/raw layers.
4. **Prediction contamination** – forecast outputs treated like factual history.
5. **Operational opacity** – jobs run, but their evidence is weak.
6. **Scope inflation** – too much simulation ambition before base data reliability exists.

## 14. Recommended A0 Follow-Up Sequence

After this concept draft, the recommended sequence is:

1. choose the initial storage and runtime posture,
2. define the first canonical subject areas,
3. define the metadata / run registry baseline,
4. define the first ingestion path end-to-end,
5. define the first read-model/UI slice,
6. only then define the first implementation tranche.

## 15. Open Decisions

The following remain deliberately open after v0.1:

- exact storage engine combination for raw/core/read layers,
- exact web stack choice,
- scheduler/tooling choice on the VPS,
- first source set,
- exact canonical key design,
- exact DQ rule catalog,
- first UI slice boundaries.

## 16. Current Recommendation

Proceed with architecture phase A0.2 next. Do not start ingestion code yet. First freeze:

- layer responsibilities,
- data platform/storage decision,
- source governance model,
- operational runtime model,
- first canonical scope.
