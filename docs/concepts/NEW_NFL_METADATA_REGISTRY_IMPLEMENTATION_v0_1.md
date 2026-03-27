# NEW NFL Metadata Registry Implementation v0.1

Status: active
Phase: T1.1
Last updated: 2026-03-27

## Purpose

This document defines the first executable metadata-management surface for NEW NFL. It is intentionally narrow: it does not ingest NFL source data yet, but it turns the metadata architecture into callable, testable repository code.

## T1.1 Scope

Included in this tranche:
- schema and table assurance for the metadata surface
- seeded default source-registry records
- list and query operations for source registry
- pipeline-state upsert and readback operations
- ingest-run and metadata-event helper functions for later adapter work
- CLI surface for bootstrap, source seeding, source listing, and pipeline-state operations

Not included in this tranche:
- real source adapters
- scheduler integration
- VPS services
- web runtime
- factual NFL data ingestion

## Metadata Service Boundaries

The metadata service is the only place in T1.1 that should directly manage metadata DDL and metadata writes. Other later modules may call it, but they should not each invent their own metadata SQL.

## Source Registry Posture

The default source registry seed is deliberately conservative. It establishes source classes and operating assumptions rather than claiming production readiness for every future endpoint. Registry rows created in T1.1 are therefore marked as `candidate` and can later be promoted, revised, or retired by explicit tranche work.

## Pipeline State Posture

Pipeline state in T1.1 is deliberately simple:
- one row per pipeline name
- last run status
- last attempt timestamp
- optional last success timestamp
- free-form JSON state payload

This is enough to support early bootstrap, registry seeding, and future orchestration without prematurely locking the final scheduler contract.

## Event Logging Posture

T1.1 also introduces Python helpers for:
- ingest runs
- load events
- data-quality events

These helpers are not exposed as broad operational CLI commands yet. They exist to give the next tranche a stable programmatic surface.

## Validation Expectations

A green T1.1 state means:
- bootstrap still works
- source seeding is idempotent
- source listing works
- pipeline-state roundtrip works
- metadata helper tests pass under pytest
- ruff remains green
