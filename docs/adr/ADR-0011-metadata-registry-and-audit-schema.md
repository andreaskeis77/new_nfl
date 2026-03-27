# ADR-0011: Metadata Registry and Audit Schema

Status: Accepted  
Date: 2026-03-27  
Phase: A0.4

## Context

A0.3 established source governance, provenance, canonical keys, and metadata-first operation. The project now needs an explicit physical metadata posture that can support ingestion observability, conflict management, DQ event capture, and later simulation evaluation.

## Decision

The project establishes `meta` as the primary metadata schema family and defines the following tables as phase-1 metadata baseline candidates:

- `meta.source_registry`
- `meta.source_endpoint_registry`
- `meta.ingest_run`
- `meta.load_event`
- `meta.raw_artifact_registry`
- `meta.dq_event`
- `meta.conflict_event`
- `meta.table_freshness`
- `meta.config_snapshot`
- `meta.entity_key_registry`
- `meta.quarantine_registry`
- `meta.release_evidence`

The project also reserves `sim` for simulation-specific run and evaluation metadata.

## Rationale

This decision makes operational history queryable and keeps provenance, DQ, and conflict management visible as first-class capabilities.

## Consequences

### Positive

- every run can be traced
- source governance becomes operational rather than conceptual
- DQ and conflict history become queryable
- simulation work can later be evaluated against explicit run metadata

### Negative

- metadata design must be maintained carefully
- bootstrap work becomes slightly larger
- some tables may need refinement once real sources are integrated

## Follow-on requirements

- A later tranche must translate the outline into executable DDL
- health and smoke checks must cover metadata schema existence
- ingestion code must not bypass run registration
