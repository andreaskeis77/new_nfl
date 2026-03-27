# HANDOFF A0.3 — Source Governance and Metadata

Status: Green  
Date: 2026-03-27  
Tranche: A0.3  
Scope: Source governance, source tiering, fallback policy, provenance model, metadata domains, canonical identity policy

## 1. What changed

This tranche moved NEW NFL from general architecture into data governance architecture.

Added:
- source governance concept
- metadata model concept
- ADR-0007 source tiering and fallback policy
- ADR-0008 provenance and audit model
- ADR-0009 entity identity and canonical keys

Updated:
- docs index
- project state
- ADR and concepts readmes

## 2. Why this matters

The most fragile part of NEW NFL is not the website but the integrity of a multi-source private data platform over time. A0.3 defines the policy layer needed before schema design and runtime ingestion work.

## 3. Current validated state

Validated at documentation/architecture level only.

Current architecture posture now includes:
- governed source onboarding
- tiered source model
- explicit fallback posture
- metadata-first control plane
- canonical key principle for core entities

No runtime code has been introduced.

## 4. Open decisions remaining after A0.3

Still open:
- concrete physical metadata schema
- exact table/view layout for raw/staging/core/meta/read models
- dataset-class priority matrix by actual source
- retention and snapshot policy
- scheduler cadence by dataset class
- exact Phase 1 entity/table scope
- web application technical stack finalization for Phase 1 runtime

## 5. Risks

- overexpansion of source ambition before Phase 1 core is stable
- premature scraping complexity
- underestimating identity and mapping edge cases
- building UI before source governance and metadata control are operationalized

## 6. Recommended next step

Proceed to A0.4 with focus on:
- physical data platform blueprint
- metadata schema draft
- layer-by-layer storage posture
- runtime boundary between recurring jobs and read-only web surfaces

## 7. Gate assessment

- Method gate: green
- Architecture gate: green for A0.3
- Runtime gate: not started by design
- Deployment gate: not started by design
