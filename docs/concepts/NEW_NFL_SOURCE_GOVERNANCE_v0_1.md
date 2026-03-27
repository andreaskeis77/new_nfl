# NEW NFL Source Governance v0.1

Status: Draft for architecture tranche A0.3  
Owner: Andreas + ChatGPT  
Scope: Source policy, redundancy, fallback, conflict handling, and operational governance for NEW NFL

## 1. Purpose

This document defines how NEW NFL will govern data sources before any production ingestion code is built. The system goal is not merely to “pull from many sources,” but to do so in a controlled way that preserves provenance, prioritizes robustness, and keeps downstream data models stable.

Source breadth is a feature only if source behavior is predictable, reviewable, and auditable.

## 2. Governing Principles

1. Source onboarding is explicit, not ad hoc.
2. Every source has a declared role in the ecosystem.
3. Redundancy is intentional, not duplicative noise.
4. A higher number of sources does not automatically increase trust.
5. Every fetch event must be attributable to a source profile and an ingest run.
6. Conflicts between sources are resolved by policy, not by undocumented intuition.
7. Unsupported or unstable sources may be used only as bounded fallbacks.
8. A source can be active for one dataset class and forbidden for another.
9. Phase 1 favors structured, reproducible acquisition over fragile scraping.
10. Source governance is part of the architecture, not just an ops concern.

## 3. Source Roles

NEW NFL will classify sources by functional role:

- **Primary source**  
  Preferred source for one or more dataset classes. Used first whenever available and healthy.

- **Secondary source**  
  Trusted source used for gap-fill, cross-checking, or coverage expansion.

- **Fallback source**  
  Used only when primary/secondary sources are unavailable, delayed, or materially incomplete.

- **Reference source**  
  Used to validate identity, naming, mappings, or static reference information.

- **Derived source**  
  A transformed or re-packaged source that may simplify acquisition but must still preserve original provenance context if possible.

## 4. Source Tiers

### Tier A — Canonical Structured Sources
Characteristics:
- structured access
- relatively stable schema or format
- reproducible retrieval
- suitable for recurring automated ingestion
- expected to be Phase 1 first-class citizens

Typical use:
- historical schedules
- teams
- players
- weekly team/player stats
- game results
- rosters

### Tier B — Complementary Structured or Semi-Structured Sources
Characteristics:
- helpful enrichment
- may be narrower, less stable, or more operationally variable than Tier A
- may provide near-real-time or niche data not available in Tier A

Typical use:
- injuries
- snap counts
- depth charts
- betting lines
- weather enrichment
- venue details
- specific tracking or derived advanced metrics

### Tier C — HTML / Fragile / Human-Oriented Sources
Characteristics:
- page scraping, brittle parsing, or UI-oriented pages
- operationally expensive to maintain
- allowed only under explicit justification
- never treated as a silent canonical truth source

Typical use:
- emergency fallback
- one-off recovery
- manual verification support
- temporary bridge until a structured source exists

## 5. Source Registry Requirement

Every onboarded source must have a source registry entry. The registry is a metadata asset, not optional project notes.

Minimum fields:

- `source_id`
- `source_name`
- `source_role`
- `source_tier`
- `dataset_classes_supported`
- `access_mode`
- `retrieval_pattern`
- `expected_frequency`
- `priority_rank`
- `owner`
- `enabled_flag`
- `phase_introduced`
- `terms_or_risk_note`
- `stability_note`
- `fallback_policy`
- `last_reviewed_at`

## 6. Dataset Classes

Source policy is assigned per dataset class, not globally. Initial dataset classes for governance purposes:

- season schedule
- game results
- game metadata
- team reference
- player reference
- roster snapshots
- player weekly stats
- team weekly stats
- standings / playoff state
- injury data
- venue data
- weather context
- betting / market context
- simulation inputs
- simulation outputs (internal only)

A source may be Tier A for one class and Tier B or disallowed for another.

## 7. Onboarding Criteria

A source may enter Phase 1 only if all of the following are true:

1. The source serves a clearly named dataset class.
2. The retrieval path is reproducible.
3. The expected output shape is understandable enough to define normalization.
4. Provenance can be captured.
5. Rate/risk characteristics are acceptable for private non-commercial use.
6. The source materially improves coverage, timeliness, resilience, or validation quality.
7. A fallback position is documented if the source is important.

## 8. Temporary Sources

Some sources may be admitted on a temporary basis under a bounded exception. Temporary admission requires:

- explicit reason
- expiry date or review milestone
- limited dataset class scope
- no silent promotion into canonical processing

## 9. Source Health States

Every source should conceptually be represented by a health state:

- `green` — healthy and eligible for normal use
- `yellow` — usable with caution; partial degradation
- `red` — unavailable or materially untrustworthy
- `quarantined` — intentionally excluded pending review

These are operational states and may vary over time independently from the static source tier.

## 10. Fallback Policy

Fallback is controlled, not automatic in all cases.

### Allowed fallback triggers
- source unavailable
- retrieval failure
- unacceptable freshness lag
- material incompleteness
- schema drift blocking normalization
- high conflict rate detected against better sources

### Not allowed as automatic fallback triggers
- mere convenience
- marginally slower response time
- a desire to mix in “more data” without defined value
- undocumented parser preference

### Fallback outcomes
- continue with alternate source and mark provenance
- partially continue and flag incompleteness
- stop the pipeline for the affected dataset class
- quarantine conflicting batch for review

## 11. Conflict Resolution Policy

Source conflict policy is dataset-class-specific, but the default rule set is:

1. Prefer the highest-ranked eligible source for canonical write.
2. Preserve conflicting alternate values in audit/conflict structures where useful.
3. Do not overwrite silently when identity alignment is uncertain.
4. If a lower-tier source conflicts with a higher-tier source, the lower-tier value does not win automatically.
5. If two similarly ranked sources conflict on a critical field, record a DQ conflict event.
6. Some fields may permit “best available” fallback; some must remain unresolved until reviewed.

Field categories:

- **Identity-critical** — game_id mapping, team mapping, player mapping, season/week identity  
  Conservative behavior; conflicts should block or quarantine.

- **Fact-critical** — final score, game date/time, roster membership snapshot, official weekly stat totals  
  Prefer explicit winner source; unresolved conflict should not be silently published as canonical fact.

- **Enrichment** — weather, market signals, informal descriptors  
  More tolerant resolution may be acceptable if provenance is preserved.

## 12. Manual Override

Manual source override is permitted only as a documented operational action and must never erase provenance. If manual intervention occurs, it must produce a durable trace in project artifacts or runtime metadata.

## 13. Review Cadence

Source registry review cadence:

- Tier A: at least once per season and after any major breakage
- Tier B: before activation and then periodically while used
- Tier C: on every meaningful reuse decision

## 14. Phase 1 Policy

Phase 1 source posture is deliberately conservative:

- prioritize structured sources
- onboard a limited number of dataset classes first
- use redundancy where it clearly increases resilience
- defer wide scraping ambitions
- treat fallback as a governed mechanism
- do not chase total source breadth before the canonical model stabilizes

## 15. Non-Goals for A0.3

This document does not yet:
- list every actual public source to be used
- authorize specific scraping targets
- define parser implementation details
- define scheduler retry code
- define storage DDL

Those belong to later architecture and implementation tranches.

## 16. Decision Impact

A disciplined source governance model will:
- reduce hidden inconsistency
- make redundancy auditable
- support future simulation quality evaluation
- keep source failures from corrupting canonical layers
- improve maintainability of a long-lived private data platform
