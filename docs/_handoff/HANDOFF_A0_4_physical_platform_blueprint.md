# HANDOFF A0.4 — Physical Platform Blueprint and Metadata Schema Outline

Status: Ready for handoff  
Phase: A0.4  
Date: 2026-03-27

## Scope of this tranche

A0.4 converts the prior logical architecture into a physical target posture for the first implementation phase. It defines:

- physical storage posture
- repository and filesystem layout
- database schema-family boundaries
- metadata registry baseline
- operational evidence posture

## Delivered artifacts

- `docs/concepts/NEW_NFL_PHYSICAL_PLATFORM_BLUEPRINT_v0_1.md`
- `docs/concepts/NEW_NFL_METADATA_SCHEMA_OUTLINE_v0_1.md`
- `docs/adr/ADR-0010-physical-storage-and-directory-layout.md`
- `docs/adr/ADR-0011-metadata-registry-and-audit-schema.md`
- `docs/adr/ADR-0012-canonical-schema-family-boundaries.md`

Updated:
- `docs/INDEX.md`
- `docs/PROJECT_STATE.md`
- `docs/adr/README.md`
- `docs/concepts/README.md`

## Current validated state

The project remains in a **code-free architecture phase**. No runtime implementation is introduced by this tranche.

The architectural baseline now includes:

- method foundation
- system concept v0.2
- phase-1 scope boundary
- source governance and metadata model
- physical storage and directory layout
- metadata schema outline
- schema-family boundaries

## What is now decided

- phase-1 storage posture is DuckDB + Parquet + disciplined filesystem zones
- one canonical working database file per environment is expected
- metadata is a first-class schema family
- schema families are explicitly separated across `meta`, `raw`, `stg`, `core`, `mart`, `feat`, `sim`, and `scratch`

## Open items

Still open for the next phase:

- exact initial physical filenames and bootstrap paths
- first executable DDL surface
- config file posture
- Python package layout and tool entry points
- health and smoke bootstrap
- initial local and VPS bootstrap scripts

## Recommended next step

Proceed to **T1.0 technical bootstrap** with a tightly scoped implementation tranche that creates:

- repository scaffolding for `src/`, `tests/`, `tools/`, `config/`, `scripts/`, `data/`, `var/`
- bootstrap directory creation
- initial config surface
- canonical DuckDB bootstrap
- metadata schema creation skeleton
- health and smoke commands
