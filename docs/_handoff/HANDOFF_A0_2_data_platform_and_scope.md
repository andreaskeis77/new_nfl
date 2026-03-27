# HANDOFF A0.2 – Data Platform and Scope

Status: Green  
Date: 2026-03-27  
Phase: A0.2

## Completed in this tranche

- advanced the architecture concept from v0.1 to v0.2,
- accepted the default data platform posture,
- accepted the explicit phase-1 scope boundary,
- tightened the ingestion-layer contract,
- updated project state and document indices.

## Validated architecture posture

The current recommended posture is:

- Python-first implementation,
- DuckDB as the phase-1 warehouse center,
- Parquet as the default persisted tabular exchange/evidence format,
- repo-external data root,
- read-only web foundation in phase 1,
- later analytics/simulation layers kept separate from canonical history.

## Current green decisions

- ADR-0001 accepted
- ADR-0002 accepted
- ADR-0003 accepted
- ADR-0006 accepted

## Still open

- initial source registry structure,
- source governance and tier criteria in operational detail,
- initial metadata schema,
- canonical entity field contracts,
- runtime scheduler choice,
- first web query surface details.

## Recommended next tranche

**A0.3 – Source Governance and Metadata Model**

This next tranche should define:

- source registry design,
- source tier policy,
- dataset freshness classes,
- reconciliation classes,
- run registry and metadata minimum schema expectations.

## Gate note

No runtime code has been introduced.  
The repository remains architecture/documentation only.
