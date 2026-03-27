# ADR-0008: Provenance and Audit Model

- Status: Accepted
- Date: 2026-03-27
- Deciders: Andreas + ChatGPT
- Supersedes: none
- Superseded by: none

## Context

NEW NFL will ingest data from multiple sources across multiple layers. Without strong provenance and audit structures, the platform could not reliably explain where data came from, what code processed it, which conflicts occurred, or how later canonical facts were formed.

This is especially important because the system is expected to support later analytics, simulation, and retrospective evaluation.

## Decision

NEW NFL will adopt a metadata-first provenance and audit model covering at least:
- source registry
- run registry
- load events
- DQ events
- canonical mapping traceability

Every meaningful acquisition or processing run must be represented as a run-level artifact. Every meaningful load attempt must be representable as a source/dataset/layer-specific load event. Quality issues and conflicts must be durable events, not transient console output.

## Required provenance concepts

Minimum provenance concepts:
- source identity
- run identity
- retrieval timestamp
- parser/normalization version
- artifact fingerprint or source record hash when feasible
- confidence or conflict status where relevant

## Consequences

### Positive
- stronger diagnosability
- support for auditability and debugging
- better confidence in canonical data
- future support for model/simulation traceability

### Negative
- more implementation effort
- more storage overhead for metadata
- requires discipline in runtime design

## Alternatives Considered

### Alternative A: minimal logging only
Rejected because logs alone do not provide sufficient structured traceability.

### Alternative B: provenance only for raw artifacts
Rejected because canonical and normalized layers would then lose explainability.

## Follow-up

Later tranches must define:
- physical metadata schema
- retention and pruning policy
- UI exposure of selected metadata and freshness state
