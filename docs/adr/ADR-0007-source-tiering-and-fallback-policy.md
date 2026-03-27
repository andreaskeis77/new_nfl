# ADR-0007: Source Tiering and Fallback Policy

- Status: Accepted
- Date: 2026-03-27
- Deciders: Andreas + ChatGPT
- Supersedes: none
- Superseded by: none

## Context

NEW NFL is designed as a resilient multi-source NFL data platform. Multi-source acquisition is valuable only if sources are governed by an explicit policy. Without tiering and fallback rules, source sprawl would introduce hidden inconsistency, brittle operations, and undocumented conflict handling.

## Decision

NEW NFL will use an explicit source tiering and fallback model.

### Source tiers
- Tier A: canonical structured sources
- Tier B: complementary structured or semi-structured sources
- Tier C: fragile / HTML / emergency fallback sources

### Source roles
- primary
- secondary
- fallback
- reference
- derived

### Policy
1. Source onboarding requires registry metadata.
2. Source eligibility is assigned per dataset class.
3. Canonical writes prefer the highest-ranked eligible source.
4. Fallback activation must be rule-driven, not convenience-driven.
5. Tier C sources are bounded and never silent canonical truth sources.
6. Source conflict handling must preserve provenance and may trigger DQ events or quarantine.

## Consequences

### Positive
- clearer operational behavior
- auditable redundancy
- lower risk of silent inconsistency
- better long-term maintainability

### Negative
- more metadata and process overhead
- slower source onboarding
- requires stronger discipline before implementation

## Alternatives Considered

### Alternative A: no tiering, just use “best available” data
Rejected because it would create unstable consolidation behavior and poor diagnosability.

### Alternative B: single-source-only strategy
Rejected because it does not meet resilience goals and would make the platform too brittle when a source fails or degrades.

## Follow-up

Later tranches must define:
- actual source registry structure
- dataset-class-specific priority rules
- fallback gating behavior in runtime pipelines
