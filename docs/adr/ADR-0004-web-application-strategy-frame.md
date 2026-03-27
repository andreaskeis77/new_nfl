# ADR-0004: Web Application Strategy Frame

Status: Proposed  
Date: 2026-03-27

## Context

The project requires a web interface that serves as a private NFL data and analysis center. The web surface must support browsing, filtering, comparison, freshness visibility, and later analytical drill-down.

## Decision Frame

The web strategy must answer:

- what framework or runtime will serve the UI,
- whether API and UI live in the same process initially,
- what the first navigable slices are,
- how read models are exposed,
- how observability and freshness are surfaced to the user,
- how much interactivity is server-driven versus client-driven.

## Current Recommendation

Prefer a practical, maintainable, private-console approach over an over-designed front-end stack. The first release should optimize for reliability, browseability, and clear analyst workflows.

## Required Outcome in A0.2 / A0.3

A later ADR should settle:
- runtime choice,
- UI/API boundary,
- first page set,
- performance posture for common queries.
