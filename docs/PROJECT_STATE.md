# NEW NFL Project State

Status: Active  
Current phase: **A0.4 — Physical Platform Blueprint and Metadata Schema Outline**  
Current repo posture: **architecture only, no runtime code yet**  
Current branch target: `main`

## Completed so far

### T0
- engineering foundation established
- workflow hardened
- handoff and ops placeholders created
- repo hygiene controls added

### A0.1
- system concept baseline defined
- ADR baseline established

### A0.2
- data platform posture and phase-1 scope defined

### A0.3
- source governance and metadata model defined
- source tiering, provenance, and canonical key ADRs added

### A0.4
- physical storage and directory layout defined
- metadata schema outline defined
- schema-family boundary ADRs accepted

## Current architecture posture

The project currently assumes:

- single-node phase-1 platform posture
- Git + DuckDB + Parquet + filesystem zones
- metadata-first operation
- explicit schema families: `meta`, `raw`, `stg`, `core`, `mart`, `feat`, `sim`, `scratch`
- later VPS deployment on Windows Server
- browse-first web experience before heavier simulation features

## Immediate next step

Recommended next tranche: **T1.0 Technical Bootstrap**

T1.0 should create the initial implementation scaffolding for:

- repository runtime directories
- initial config surface
- bootstrap scripts
- initial DuckDB bootstrap
- metadata schema skeleton
- health and smoke checks

## Constraints

- no runtime code has been introduced yet
- no source adapters have been implemented yet
- no web application code has been introduced yet
- no scheduler/runtime services have been created yet
