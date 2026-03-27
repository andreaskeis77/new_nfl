# NEW NFL Project State

## Current Phase

- Current tranche: **A0.3**
- Status: **Green**
- Repository posture: **documentation-first, architecture-active, runtime not started**
- Current branch expectation: `main` remains stable and reviewable

## Current Achievements

Completed and committed:
- engineering foundation
- workflow hardening and repo hygiene
- A0.1 system concept and ADR baseline
- A0.2 data platform posture and Phase 1 scope boundary
- A0.3 source governance and metadata model baseline

## Current Architecture Posture

The current target posture is:

- documentation-driven systems engineering
- conservative Phase 1 scope
- metadata-first multi-source platform
- layered acquisition and consolidation model
- read-only web surface before advanced analytics/simulation runtime
- VPS deployment planned but not yet designed to implementation level

## What Is Decided

Decided at current architecture level:
- repo and operating model
- phase-1 boundary as a limited first operating scope
- data platform posture direction
- ingestion layering principle
- source tiering and fallback policy
- provenance and audit requirement
- canonical key requirement for core entities

## What Is Still Open

Open architecture topics:
- physical storage layout and concrete schema draft
- metadata schema structure
- actual dataset-class-to-source matrix
- scheduler/runtime topology
- read model strategy detail
- web app runtime design detail
- retention, pruning, and snapshot policy
- DQ rule catalog first cut

## Immediate Next Recommendation

Proceed with **A0.4**:
- physical data platform blueprint
- metadata schema outline
- storage/layer mapping
- runtime boundary between jobs and read-only web application

## Operational Notes

- No runtime code exists yet by design.
- No VPS service setup exists yet by design.
- No ingestion source is approved for implementation yet beyond architecture-level governance.
- All next steps should continue to preserve small-batch, green-gate discipline.
