# ADR-0005: Scheduler and VPS Runtime Model Frame

Status: Proposed  
Date: 2026-03-27

## Context

NEW NFL is intended to run on a Windows VPS with recurring ingestion, possible services, logging, and health visibility. Operational reliability is a first-class project concern.

## Decision Frame

The runtime model must decide:

- which components are long-running services,
- which components are scheduled jobs,
- how jobs are triggered and logged,
- how success/failure evidence is persisted,
- how the system is restarted after interruption,
- how local development and VPS runtime stay aligned.

## Current Recommendation

Use the simplest runtime model that still preserves evidence and recoverability. Avoid unnecessary service sprawl in early phases.

## Required Outcome in later architecture phases

A later ADR must define:
- the first runtime topology,
- the scheduling mechanism,
- the logging/health model,
- the promotion path from DEV-LAPTOP to VPS.
