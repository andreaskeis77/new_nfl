# ADR Index

Architectural Decision Records, neueste oben. Status-Quelle ist immer das ADR-Dokument selbst.

| ADR | Titel | Status | Tranche / Anker |
|---|---|---|---|
| [ADR-0031](ADR-0031-adapter-slice-strategy.md) | Adapter-Slice-Strategie (ein Adapter, N Slices via Code-Registry) | Proposed | T2.5A |
| [ADR-0030](ADR-0030-ui-tech-stack.md) | UI tech stack: Jinja + Tailwind + htmx + Plot | Proposed | T2.6A |
| [ADR-0029](ADR-0029-read-model-separation.md) | Read-model separation (`mart.*` only for UI/API) | Accepted (2026-04-14) | T2.3D |
| [ADR-0028](ADR-0028-quarantine-as-first-class-domain.md) | Quarantine as first-class domain | Accepted (2026-04-14) | T2.3C |
| [ADR-0027](ADR-0027-dedupe-pipeline-as-explicit-stage.md) | Dedupe pipeline as explicit stage | Accepted (2026-04-16) | T2.4B |
| [ADR-0026](ADR-0026-ontology-as-code-with-runtime-projection.md) | Ontology-as-code with runtime projection | Accepted (2026-04-16) | T2.4A |
| [ADR-0025](ADR-0025-internal-job-and-run-model.md) | Internal job and run model in DuckDB metadata | Accepted (2026-04-13) | T2.3A / T2.3B |
| [ADR-0024](ADR-0024-stage-load-contract-and-provenance-columns.md) | Stage-load contract and provenance columns | Accepted | T1.5 |
| [ADR-0023](ADR-0023-first-normalized-staging-load.md) | First normalized staging load | Accepted | T1.5 |
| [ADR-0022](ADR-0022-remote-fetch-asset-manifest-and-checksum-receipt.md) | Remote fetch asset manifest and checksum receipt | Accepted | T1.4 |
| [ADR-0021](ADR-0021-first-true-remote-fetch-implementation.md) | First true remote fetch implementation | Accepted | T1.4 |
| [ADR-0020](ADR-0020-dry-run-vs-execute-adapter-contract.md) | Dry-run vs execute adapter contract | Accepted | T1.3 |
| [ADR-0019](ADR-0019-first-fetch-contract-and-raw-landing-receipt.md) | First fetch contract and raw landing receipt | Accepted | T1.3 |
| [ADR-0018](ADR-0018-adapter-registry-binding-and-dry-run-contract.md) | Adapter registry binding and dry-run contract | Accepted | T1.2 |
| [ADR-0017](ADR-0017-source-adapter-abstraction.md) | Source adapter abstraction | Accepted | T1.2 |
| [ADR-0016](ADR-0016-metadata-registry-service-surface.md) | Metadata registry service surface | Accepted | T1.1 |
| [ADR-0015](ADR-0015-quality-gates-and-bootstrap-scope.md) | Quality gates and bootstrap scope | Accepted | T1.0 |
| [ADR-0014](ADR-0014-project-layout-and-entrypoints.md) | Project layout and entrypoints | Accepted | T1.0 |
| [ADR-0013](ADR-0013-python-runtime-and-toolchain.md) | Python runtime and toolchain | Accepted | T1.0 |
| [ADR-0012](ADR-0012-canonical-schema-family-boundaries.md) | Canonical schema family boundaries (`raw`/`stg`/`core`/`mart`/`meta`) | Accepted | A0 |
| [ADR-0011](ADR-0011-metadata-registry-and-audit-schema.md) | Metadata registry and audit schema | Accepted | A0 |
| [ADR-0010](ADR-0010-physical-storage-and-directory-layout.md) | Physical storage and directory layout | Accepted | A0 |
| [ADR-0009](ADR-0009-entity-identity-and-canonical-keys.md) | Entity identity and canonical keys | Accepted | A0 |
| [ADR-0008](ADR-0008-provenance-and-audit-model.md) | Provenance and audit model | Accepted | A0 |
| [ADR-0007](ADR-0007-source-tiering-and-fallback-policy.md) | Source tiering and fallback policy | Accepted | A0 |
| [ADR-0006](ADR-0006-phase1-scope-boundary.md) | Phase-1 scope boundary | Accepted | A0 |
| [ADR-0005](ADR-0005-scheduler-and-vps-runtime-model-frame.md) | Scheduler and VPS runtime model (frame) | Accepted | A0 |
| [ADR-0004](ADR-0004-web-application-strategy-frame.md) | Web application strategy (frame) | Accepted | A0 |
| [ADR-0003](ADR-0003-ingestion-layering.md) | Ingestion layering | Accepted | A0 |
| [ADR-0002](ADR-0002-data-platform-and-storage-decision-frame.md) | Data platform and storage decision (frame) | Accepted | A0 |
| [ADR-0001](ADR-0001-repo-and-operating-model.md) | Repository and operating model | Accepted | A0 |

## Konvention

- Neue ADRs werden fortlaufend nummeriert (`ADR-0031`, `ADR-0032`, …) und am Tabellenkopf eingefügt.
- Status-Werte: `Proposed`, `Accepted`, `Superseded by ADR-NNNN`, `Deprecated`.
- Tranche / Anker referenziert die Tranche aus `T2_3_PLAN.md` bzw. die Phase, in der die Entscheidung umgesetzt wurde.
- Bei `Accepted` wird das Datum (YYYY-MM-DD) hier mitgeführt und steht zusätzlich im ADR selbst.
