# ADR-0002: Data Platform and Storage Decision Frame

Status: Proposed  
Date: 2026-03-27

## Context

NEW NFL requires durable historical storage, repeatable ingestion, multi-layer processing, UI-friendly read access, and later analytics/simulation support. The project also needs strong local operability and a realistic VPS deployment path.

## Decision Frame

This ADR is not final yet. It establishes the decision frame for A0.2.

The storage decision must explicitly answer:

1. What engine stores raw retrieval evidence?
2. What engine stores source-normalized and canonical data?
3. What engine serves read models for the web UI?
4. Will one engine serve all layers initially, or will layers split by concern?
5. How will metadata, runs, freshness, and DQ results be stored?
6. How will rebuildability be preserved?

## Current Recommendation

Start by evaluating a single-engine posture for early phases unless it creates unacceptable friction. Layer separation is mandatory even if physical separation is deferred.

## Open Options to assess in A0.2

- one-engine initial platform,
- hybrid platform with separate raw artifact storage and analytical core storage,
- separate UI-serving store if needed later.

## Required Outcome in A0.2

A0.2 must produce an accepted ADR with a clear recommendation and explicit tradeoffs.
