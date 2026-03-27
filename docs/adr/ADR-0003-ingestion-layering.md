# ADR-0003: Ingestion Layering

Status: Accepted  
Date: 2026-03-27

## Context

The project requires data redundancy, later source expansion, and auditability. Without explicit layering, source-specific logic, UI concerns, and canonical truth maintenance would collapse into each other.

## Decision

NEW NFL will use at least the following logical layers:

- Raw Landing
- Source-Normalized Staging
- Canonical Core
- Read Models / UI Marts
- Analytics / Feature Layer
- Prediction / Simulation Registry

## Consequences

Positive:
- source-specific troubleshooting becomes possible,
- provenance is preserved,
- simulation outputs remain separate from factual history,
- UI performance optimization can occur without damaging canonical integrity.

Negative:
- more upfront design work,
- more tables and transforms to maintain.

## Notes

This ADR defines the mandatory logical layering only. It does not yet decide physical storage.
