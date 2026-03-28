# ADR-0019 First Fetch Contract and Raw Landing Receipt

## Status

Accepted

## Decision

NEW NFL introduces a first real adapter execution contract in T1.3.
The first real contract is bound to `nflverse_bulk` and produces raw landed
artifacts under a deterministic directory keyed by `ingest_run_id`.

Every execute-mode run must create:
- one ingest run record
- one raw landed directory
- one request manifest file
- one fetch receipt file
- one load-event record
- one pipeline-state update

## Rationale

The project needs an operational shape before implementing remote source logic.
A receipt-based raw landing contract gives traceability and deterministic file
layout without yet depending on remote source semantics.

## Consequences

Positive:
- landed raw traces are inspectable on disk
- metadata and filesystem are correlated by ingest run
- future fetch logic can be swapped in behind the same run contract

Negative:
- T1.3 creates execution receipts but not real source payloads yet
- additional work is required in T1.4 to turn the contract into true fetching
