# ADR-0009: Entity Identity and Canonical Keys

- Status: Accepted
- Date: 2026-03-27
- Deciders: Andreas + ChatGPT
- Supersedes: none
- Superseded by: none

## Context

NEW NFL will consolidate overlapping data from multiple sources. External source identifiers are not stable enough to act as the sole identity mechanism across the platform. Team names, player names, scheduling details, and source-specific ids can vary over time or differ across providers.

Without a canonical identity policy, the project would risk duplicate entities, broken joins, and unsafe source conflict resolution.

## Decision

NEW NFL will define and maintain internal canonical keys for core entities. External source identifiers will be mapped to those internal canonical identities rather than replacing them.

Core entity classes:
- season
- week
- team
- player
- game
- venue

The identity model must support:
- source-specific external ids
- alias history
- mapping confidence
- temporal validity where needed
- conservative behavior when identity is uncertain

## Rules

1. Canonical keys are platform-owned, not source-owned.
2. External ids are metadata and mapping inputs, not canonical truth by themselves.
3. Identity-critical conflicts should block or quarantine rather than silently merge.
4. Mapping decisions must be reviewable and traceable.
5. Canonical ids must be stable enough for downstream marts, analytics, and simulation history.

## Consequences

### Positive
- cleaner joins across layers
- more reliable consolidation
- better support for long-term historical analysis
- lower risk of silent duplication

### Negative
- higher upfront modeling effort
- mapping logic may be complex for edge cases
- some records may need quarantine until identity is resolved

## Alternatives Considered

### Alternative A: trust each source id as canonical within its own domain
Rejected because cross-source integration would remain fragile.

### Alternative B: use natural keys only (names/dates/combinations)
Rejected because names and schedules are not stable enough for all cases.

## Follow-up

Later tranches must define:
- specific key strategy by entity class
- mapping table structures
- conflict review and override workflow
