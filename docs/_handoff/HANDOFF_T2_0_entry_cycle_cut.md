# HANDOFF T2.0 Entry Cycle Cut

Status: ready for local validation

Scope:
- update `docs/PROJECT_STATE.md` so the repo stops presenting T1.5 as still in progress
- record that T1 is the completed ingestion-foundation cycle
- define the next preferred bolt as a narrow T2.0A canonical ingest slice
- keep this bolt docs-only

Why this bolt exists:
- the repo had reached a real T1.5 staging-load state, but `PROJECT_STATE.md` still described that work as in progress
- after the T1.5 circular-export repair and the apply-workflow hardening, the T1/T2 boundary should be explicit in the repo itself
- this bolt prevents a hidden cycle jump

What this bolt does not do:
- no `stg -> core` code
- no schema change
- no new CLI surface
- no browseable/query path claim

Preferred next step after local validation:
- T2.0A — First canonical reference slice from `stg.nflverse_bulk_schedule_dictionary` into a minimal `core` object
