# Project State

## Current phase

**T2.5B Games-Domäne** — abgeschlossen (2026-04-22). Nächster Bolt: T2.5C (Players-Domäne).

## Architektur-Baseline (freigegeben am 2026-04-13)

- `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md` — verbindlicher Architektur-Anker
- `ENGINEERING_MANIFEST_v1_3.md` — verbindliche Engineering-Regeln
- `UI_STYLE_GUIDE_v0_1.md` — verbindliche UI-Regeln
- `T2_3_PLAN.md` — aktiver Tranche-Plan zum v1.0-Ziel (Ende Juni 2026)
- `USE_CASE_VALIDATION_v0_1.md` — abgenommene Use Cases
- ADR-0025, ADR-0026, ADR-0027, ADR-0028, ADR-0029, ADR-0031 — `Accepted`; ADR-0030 (UI Stack) bleibt `Proposed` bis T2.6A
- `CHAT_HANDOFF_PROTOCOL.md`, `LESSONS_LEARNED_PROTOCOL.md` — Methode
- Letzter Chat-Handoff: `docs/_handoff/chat_handoff_20260416-1900_t24-ontology-runtime-done.md`

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
- T2.3B Internal Runner (`src/new_nfl/jobs/runner.py`: atomarer Claim, Executor-Registry, Retry-Policy-Auswertung, Replay; geteilter DB-Helper `src/new_nfl/_db.py`; CLI `run-worker --once|--serve` und `replay-run`; `fetch-remote`/`stage-load` laufen nur noch über den Runner)
- T2.3C Quarantäne-Domäne (`src/new_nfl/jobs/quarantine.py`: `meta.quarantine_case`, `meta.recovery_action`; Dedupe per `(scope_type, scope_ref, reason_code)`; Auto-Quarantäne-Hook im Runner bei `runner_exhausted`; CLI `list-quarantine`, `quarantine-show`, `quarantine-resolve --action replay|override|suppress`; Replay erzeugt neuen `job_run_id` und schließt den Case bei Erfolg)
- T2.3D Read-Modell-Trennung (`src/new_nfl/mart/`: `mart.schedule_field_dictionary_v1` als versionierte Read-Projektion über `core.schedule_field_dictionary`; Runner-Executor `mart_build`; CLI `mart-rebuild --mart-key …`; `core-load --execute` triggert Mart-Build implizit; `core_browse`/`core_lookup`/`core_summary`/`web_preview`/`web_server` lesen ausschließlich aus `mart.*`; Lint-Test verbietet `core.*`/`stg.*`/`raw/` in Read-Modulen)
- T2.3E ADR-Block aktualisiert (`docs/adr/README.md` als vollständiger Index mit Status + Tranchen-Anker für ADR-0001 bis ADR-0030; ADR-0025/0028/0029 final `Accepted`; ADR-0026/0027/0030 bleiben `Proposed` bis zur jeweiligen Tranche T2.4A/T2.4B/T2.6A)
- T2.4A Ontology-as-Code-Skelett (`ontology/v0_1/term_*.toml`, `src/new_nfl/ontology/loader.py` mit `content_sha256`-Idempotenz; `meta.ontology_version`/`ontology_term`/`ontology_alias`/`ontology_value_set`/`ontology_value_set_member`/`ontology_mapping`; CLI `ontology-load`, `ontology-list`, `ontology-show --term-key <key|alias>`; Pydantic-Service `load_ontology_directory`/`list_terms`/`describe_term`; ADR-0026 final `Accepted`, TOML-Format statt YAML)
- T2.4B Dedupe-Pipeline-Skelett (`src/new_nfl/dedupe/` mit fünf Stufen `normalize → block → score → cluster → review` und `pipeline.py`; `meta.dedupe_run` + `meta.review_item`; `RuleBasedPlayerScorer` mit sechs Score-Stufen; `Scorer`-Protocol für spätere ML-Erweiterung; CLI `dedupe-run --domain players --demo` und `dedupe-review-list`; Demo-Set deckt Auto-Merge, Review und No-Match in einem Lauf; ADR-0027 final `Accepted`)
- T2.5A Teams-Domäne (Adapter-Slice-Registry `src/new_nfl/adapters/slices.py`; `core.team` mit Tier-A/Tier-B-Konflikt-Erkennung und automatischem `meta.quarantine_case`-Öffnen per `reason_code='tier_b_disagreement'`; Tier-A gewinnt nach ADR-0007; Read-Modell `mart.team_overview_v1`; Ontology-Terme `conference` + `division` ergänzt; CLI `--slice`-Flag für `fetch-remote`/`stage-load`/`core-load`; ADR-0031 `Proposed`)
- T2.5B Games-Domäne (Slices `(nflverse_bulk, games)` primär und `(official_context_web, games)` als Cross-Check; `core.game` mit `game_id`-Deduplikation via `ROW_NUMBER() OVER (PARTITION BY LOWER(TRIM(game_id)))`, Tier-A/B-Konflikt-Erkennung auf `home_score`, `away_score`, `stadium`, `roof`, `surface` und automatischem `meta.quarantine_case`-Öffnen; Read-Modell `mart.game_overview_v1` mit abgeleitetem `is_completed` und `winner_team` (`home_team`/`away_team`/`TIE`/NULL); CLI `list-slices` für Operator-Sicht über `SLICE_REGISTRY`; erste reale HTTP-Runde für `official_context_web` via stdlib-`ThreadingHTTPServer` end-to-end in `urllib.request.urlopen`-Pfad; ADR-0031 final `Accepted`)

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
- interner Job-Runner: atomares Claim auf `meta.job_queue`, Executor-Registry (`fetch_remote`, `stage_load`, `custom`), Retry-Policy-Auswertung, deterministischer Replay gescheiterter Runs; CLI `run-worker --once|--serve` und `replay-run --job-run-id`; `fetch-remote` und `stage-load` erzeugen nur noch über den Runner Evidence (Manifest §3.9, §3.13)
- First-class Quarantäne-Domäne: jeder `runner_exhausted`-Run öffnet einen `meta.quarantine_case` mit Evidence-Ref; Operator-Aktionen (`replay`, `override`, `suppress`) werden als `meta.recovery_action` persistiert und verlinken bei Replay den neuen `job_run_id` (ADR-0028)
- Read-Modell-Schicht `mart.*` als einziger Lesepfad für CLI-Browse/Web-Preview (ADR-0029): `mart.schedule_field_dictionary_v1` voll rebuildbar aus `core.*`, automatisch nach `core-load --execute` aufgefrischt, separat über CLI `mart-rebuild` als Runner-Job; Direktzugriffe aus Read-Modulen auf `core.*`/`stg.*`/`raw/` werden durch einen Lint-Test blockiert
- Ontologie-as-Code v0_1 (ADR-0026): TOML-Quellen unter `ontology/v0_1/` (Position, Game-Status, Injury-Status), Loader idempotent über `content_sha256`, Projektion in `meta.ontology_*`; CLI `ontology-load`/`ontology-list`/`ontology-show` mit Alias-Auflösung; `meta.ontology_version` markiert die aktive Version pro Quellverzeichnis
- Dedupe-Pipeline-Skelett (ADR-0027): fünf explizite Stufen unter `src/new_nfl/dedupe/`, regel-basierter Scorer mit Pluggable-Interface, Auto-Merge ab `score >= 0.85`, Review-Queue für `0.50 <= score < 0.85`; Evidence in `meta.dedupe_run`; offene Pairs in `meta.review_item`; CLI `dedupe-run --domain players --demo` und `dedupe-review-list`
- Adapter-Slice-Registry (ADR-0031 Accepted seit T2.5B): ein `adapter_id` kann mehrere Slices bedienen; slice-spezifische `remote_url`, `stage_target_object`, `core_table`, `mart_key` + Rolle (`primary`/`cross_check`); Registry nach T2.5B: `(nflverse_bulk, schedule_field_dictionary)`, `(nflverse_bulk, teams)`, `(nflverse_bulk, games)` als Primary plus `(official_context_web, teams)` und `(official_context_web, games)` als Cross-Check; Quarantäne-Hook auf Tier-A/B-Diskrepanz in `core.team` und `core.game`; Operator-CLI `list-slices` für Registry-Sicht
- `core.game` slice-zentrisch aus `(nflverse_bulk, games)` mit Tier-A-Dominanz, `mart.game_overview_v1` als Read-Projektion (abgeleitet: `is_completed`, `winner_team`), `(official_context_web, games)` als erste reale HTTP-getriebene Tier-B-Quelle

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

**T2.5C — Players-Domäne** gemäß `T2_3_PLAN.md` §4: Slice `(nflverse_bulk, players)` mit `core.player` + `mart.player_overview_v1`; identisches Muster wie T2.5A/B (primary + optionaler Cross-Check, Quarantäne auf Diskrepanz). Ontology-Term `position` aus T2.4A wird als Controlled-Vocabulary-Projektion für `core.player.position` angehängt.

## Zielkorridor v1.0

- feature-complete: Ende Juni 2026
- Testphase: Juli 2026
- produktiv (auf Windows-VPS): vor Preseason-Start Anfang August 2026
