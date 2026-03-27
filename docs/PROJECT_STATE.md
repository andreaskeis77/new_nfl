# NEW NFL Project State

Status: Active architecture definition  
Current Phase: A0.2  
Last Updated: 2026-03-27

## Current Position

The project is still intentionally **pre-implementation**.  
Method foundation is established, A0.1 system concept has been created, and A0.2 now tightens the architecture with an accepted data platform posture and a formal phase-1 scope boundary.

## Green State Summary

- method baseline established,
- repo hygiene and handoff structure established,
- architecture concept advanced from v0.1 to v0.2,
- ADR-0002 now accepted for DuckDB + Parquet phase-1 posture,
- phase-1 scope formally bounded,
- ingestion layering tightened.

## Current Accepted Decisions

- Repo and operating model: accepted
- Data platform and storage posture: accepted
- Ingestion layering: accepted
- Phase-1 scope boundary: accepted

## Still Open

- exact physical data root convention,
- first canonical entity field contracts,
- operational metadata schema,
- initial source registry design,
- web query surface details,
- scheduler/runtime implementation choice.

## Next Recommended Step

Proceed to **A0.3** to define:

- source governance,
- source registry structure,
- reconciliation classes,
- dataset freshness classes,
- initial metadata schema expectations.

## Guardrail

No runtime implementation should start until A0.3 resolves the first source-governance and metadata-model decisions.
