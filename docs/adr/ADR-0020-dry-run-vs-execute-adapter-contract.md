# ADR-0020 Dry Run vs Execute Adapter Contract

## Status

Accepted

## Decision

Adapter execution is split into two modes:
- dry run
- execute

Dry run must be side-effect free.
Execute may create raw landed artifacts and metadata state.

## Rationale

NEW NFL needs a safe planning mode for local validation and future scheduler
use, while still allowing a real execution envelope for adapter contracts.

## Consequences

Dry run:
- no ingest run
- no landed files
- no metadata mutation

Execute:
- ingest run is created
- landed files are written
- load event is recorded
- pipeline state is updated
