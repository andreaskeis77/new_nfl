# ADR-0018 Adapter Registry Binding and Dry-Run Contract

## Status

Accepted

## Context

NEW NFL needs a safe step between metadata-only setup and real ingestion. The project also uses
strict green-gate rules, so the first adapter tranche must provide observable behavior without
creating network dependencies.

## Decision

Each adapter must support a dry-run planning contract that reports:

- adapter identifier
- source name
- registry binding status
- transport
- extraction mode
- raw landing prefix
- stage dataset target
- source status
- implementation notes

The CLI exposes this contract through `describe-adapter`. The command may bootstrap the local
metadata surface, but it must not perform external fetches.

## Consequences

Positive:

- adapter selection can be validated before first ingestion code
- raw landing naming is stabilized early
- registry drift becomes visible through adapter binding state

Negative:

- the dry-run plan is intentionally incomplete and must later be expanded with file manifests,
  request policies, and run-registration details
