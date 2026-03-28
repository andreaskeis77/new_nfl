# ADR-0021 First True Remote Fetch Implementation

Status: Accepted

## Decision
The first real remote fetch implementation is introduced for `nflverse_bulk` only.

## Rationale
- smallest controlled step from contract-only execution to actual network IO
- good fit to the bulk-adapter posture already chosen for T1.x
- limits failure modes while proving remote fetch, receipt writing, and metadata capture
