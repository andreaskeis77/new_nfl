# NEW NFL Phase-1 Scope v0.1

Status: Draft  
Phase: A0.2  
Last Updated: 2026-03-27

## 1. Purpose

This document translates the architecture concept into a more executable phase-1 delivery scope.  
It is a scope control tool. It prevents premature expansion and keeps the first implementation focused on a durable NFL fact platform.

## 2. Phase-1 Goal

Deliver a private, read-only NFL data platform that can:

- ingest and preserve the primary historical NFL fact datasets,
- refresh important datasets on declared cadences,
- consolidate multiple sources into a canonical model with provenance,
- expose a clear browser-oriented web interface,
- provide operational visibility into freshness, runs, and source status.

## 3. In Scope

### 3.1 Core datasets

- seasons
- weeks
- teams
- games / schedules / results
- players
- rosters
- team aggregated stats
- player aggregated stats

### 3.2 Operational capabilities

- source registry
- ingest run registry
- source-file / retrieval-artifact tracking
- freshness status
- reconciliation status
- rebuild posture from evidence where feasible

### 3.3 UI capabilities

- browse
- inspect
- filter
- compare
- view freshness
- view provenance summary

## 4. Out of Scope

- prediction engine
- playoff simulation engine
- automated betting-style scenario systems
- media storage
- public multi-user access
- generalized content features
- advanced admin UX
- uncontrolled source scraping expansion

## 5. Entry Criteria to Start Implementation

Implementation should begin only when these are sufficiently stable:

- data platform posture accepted,
- phase-1 scope accepted,
- first canonical entity list accepted,
- first metadata requirements accepted,
- first runtime operating model accepted.

## 6. Exit Criteria for Phase 1

Phase 1 should be considered complete only if:

- core dataset families exist in canonical form,
- provenance is queryable,
- freshness status is visible,
- read-only web UI is usable,
- refresh jobs are operable on the VPS,
- rebuild and diagnostic posture is documented.

## 7. Scope Guardrails

Any proposal that adds a new dataset family or new UI surface should answer:

1. Does it help the phase-1 goal directly?
2. Does it require new identity logic?
3. Does it require new reconciliation logic?
4. Does it increase operator burden significantly?
5. Can the system remain understandable after the addition?

A “no” or “unclear” answer is a reason to defer.
