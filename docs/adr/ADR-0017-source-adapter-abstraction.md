# ADR-0017 Source Adapter Abstraction

## Status

Accepted

## Context

NEW NFL already has a metadata registry and seeded source identifiers, but it does not yet have
a runtime abstraction for individual source implementations. Starting real ingestion work without
such a layer would couple orchestration directly to source-specific code.

## Decision

The system introduces a source-adapter abstraction with these properties:

- one canonical adapter identifier per source
- adapter identifiers aligned to metadata `source_id`
- adapter descriptors available without network access
- a dry-run planning surface available before real fetch logic exists
- adapter listing and inspection available through the CLI

T1.2 uses static skeleton adapters rather than live implementations.

## Consequences

Positive:

- future source work can be added one adapter at a time
- orchestration can bind to stable adapter identifiers
- registry alignment is testable before network code exists
- the CLI can expose adapter state without side effects

Negative:

- there is temporary duplication between metadata registry seed data and static adapter
  descriptors
- the first real adapter tranche must keep these definitions aligned until registry-driven
  adapter discovery is introduced
