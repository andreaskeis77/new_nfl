# Project State

## Current phase

**T2.3 Foundation Hardening** — T2.3A abgeschlossen, bereit für T2.3B

## Architektur-Baseline (freigegeben am 2026-04-13)

- `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md` — verbindlicher Architektur-Anker
- `ENGINEERING_MANIFEST_v1_3.md` — verbindliche Engineering-Regeln
- `UI_STYLE_GUIDE_v0_1.md` — verbindliche UI-Regeln
- `T2_3_PLAN.md` — aktiver Tranche-Plan zum v1.0-Ziel (Ende Juni 2026)
- `USE_CASE_VALIDATION_v0_1.md` — abgenommene Use Cases
- ADR-0025 bis ADR-0030 — neue Architekturentscheidungen (Proposed)
- `CHAT_HANDOFF_PROTOCOL.md`, `LESSONS_LEARNED_PROTOCOL.md` — Methode
- Letzter Chat-Handoff: `docs/_handoff/chat_handoff_20260413-1700_t23a-job-run-skeleton-done.md`

## Completed

- A0 architecture and method foundation
- T1.0 local bootstrap
- T1.1 metadata registry
- T1.2 adapter skeleton
- T1.3 first fetch contract
- T1.4 first true remote fetch
- T1.5 first normalized staging load for `nflverse_bulk`
- T1.5 repair 01: remove the `stage_load` circular export and restore the import/collection gate
- T1.x method hardening for artifact apply and validation workflow
- T2.0 entry cycle cut
- T2.0A first canonical dictionary core load
- T2.0B methodik bolt for separation of `Einordnung` and `Aktion`
- T2.0C first browseable core dictionary slice
- T2.0D exact core dictionary field lookup
- T2.0E negative lookup miss-path hardening
- T2.0F core dictionary browse with `data_type` filter
- T2.0G core dictionary summary by `data_type`
- T2.1A stage-load source-file pinning
- T2.1B source-file discovery for operators
- T2.1C local HTML preview for core dictionary
- T2.1D local mini webserver for preview
- T2.3A Job-/Run-Modell-Skeleton (meta.job_definition, job_schedule, job_queue, job_run, run_event, run_artifact, retry_policy + Pydantic-Modelle + CLI `list-jobs`/`describe-job`/`register-job`/`register-retry-policy`)

## Current runtime posture

- local Python package with CLI surface
- local DuckDB metadata surface
- seeded source registry
- adapter catalog
- raw landing receipts
- true remote fetch path with dry-run and execute modes
- source-file discovery and explicit `source_file_id` pinning
- first normalized staging load into `stg.nflverse_bulk_schedule_dictionary`
- first canonical core load into `core.schedule_field_dictionary`
- browse / exact lookup / summary over the core dictionary
- local HTML preview export
- local mini webserver for preview
- interner Job-/Run-Modell-Store in DuckDB (meta.job_*, meta.retry_policy, meta.run_event, meta.run_artifact) mit Pydantic-Modellen und CLI-Oberfläche

## Current release posture

The project now has a **local preview-release candidate**.

That means:
- data can be fetched and loaded locally
- the first canonical core object can be built locally
- the first web-facing preview can be rendered and served locally

What is still missing before the first VPS preview release:
- a pinned VPS runbook with exact operator steps
- a preview release cut that is replayed on the VPS
- a VPS smoke test covering `/healthz` and `/`
- an explicit rollback / restart note for the preview service

## Current cycle

T2.2 (lokales Preview + VPS-Runbook) ist abgeschlossen. **VPS-Deploy ist auf nach v1.0 verschoben** (Operator-Entscheidung, siehe `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md` §2). Der Fokus wechselt auf interne Foundation-Härtung, damit alle Phase-1-Domänen autonom, evidenz- und replay-fähig laufen.

## Preferred next bolt

**T2.3B — Internal Runner** gemäß `T2_3_PLAN.md` §2 und ADR-0025: Worker-Loop, der `meta.job_queue` atomar claimt, ausführt, Retries gemäß Policy fährt, `meta.job_run` + `meta.run_event` + `meta.run_artifact` schreibt.

## Zielkorridor v1.0

- feature-complete: Ende Juni 2026
- Testphase: Juli 2026
- produktiv (auf Windows-VPS): vor Preseason-Start Anfang August 2026
