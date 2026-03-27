# ADR-0016 Metadata Registry Service Surface

Status: Accepted
Date: 2026-03-27

## Context

T1.0 created the baseline DuckDB schemas and control tables, but the repository still lacked a usable service layer for metadata operations. Without that layer, later source adapters would either duplicate metadata SQL or defer metadata discipline until too late.

## Decision

NEW NFL will introduce a dedicated Python metadata service surface in T1.1.

This service is responsible for:
- ensuring metadata schemas and required columns exist
- seeding default source-registry records
- reading source-registry rows
- upserting pipeline-state rows
- creating and finishing ingest-run rows
- recording load events
- recording dq events

A minimal CLI surface will be exposed for the most immediate developer-facing operations:
- bootstrap
- seed-sources
- list-sources
- set-pipeline-state
- show-pipeline-state

Lower-level metadata event helpers remain Python-level operations for now.

## Consequences

Positive:
- metadata operations gain one canonical code surface
- later adapters can call stable helpers instead of inventing SQL
- source governance becomes executable rather than purely documentary
- idempotent source seeding is now testable

Negative:
- bootstrap and metadata logic become more coupled than in T1.0
- future migrations must keep backward compatibility with early metadata tables

## Follow-up

T1.2 should build source adapter skeletons on top of this metadata service rather than bypassing it.
