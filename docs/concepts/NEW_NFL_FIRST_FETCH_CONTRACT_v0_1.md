# NEW NFL First Fetch Contract v0.1

## Purpose

T1.3 introduces the first real adapter execution contract for `nflverse_bulk`.
The goal is not full source integration yet. The goal is a reliable operational
shape for one adapter:

- dry-run contract
- execute contract
- landed raw artifact receipt
- ingest-run metadata
- load-event metadata
- pipeline-state update

## Phase boundary

Included in T1.3:
- CLI-triggered adapter run contract
- `nflverse_bulk` as the first real adapter path
- raw landed directory under `data/raw/landed/<adapter_id>/<ingest_run_id>/`
- `request_manifest.json` as the planned fetch contract
- `fetch_receipt.json` as the execution receipt
- ingest-run and load-event metadata records

Not included in T1.3:
- real remote download logic
- parsing of source payloads
- stage-table loading
- retries, backoff, or scheduler automation
- broad multi-adapter execution orchestration

## Contract shape

### Dry run

Dry run is side-effect free.
It returns the adapter plan and states what would happen, but it does not:
- create landed files
- create ingest runs
- create load events
- update pipeline state

### Execute

Execute creates a minimal but real raw-landing trace:
- one ingest run
- one landed directory
- one request manifest file
- one fetch receipt file
- one load event
- one pipeline-state update

## Why this matters

This gives NEW NFL a stable step between architecture and true source ingestion.
We can now prove:
- the adapter contract is operationally real
- landed raw artifacts have a deterministic path
- metadata can trace one adapter execution end to end
- later source fetchers can plug into a known execution envelope

## Landed artifact contract

`request_manifest.json` records:
- adapter id
- pipeline name
- ingest run id
- stage dataset target
- source status
- planned asset list

`fetch_receipt.json` records:
- adapter id
- pipeline name
- ingest run id
- run status
- load event id
- landed file list
- stage dataset target

## Immediate next step after green

T1.4 should add the first actual remote fetch implementation behind this
contract, still for one adapter only.
