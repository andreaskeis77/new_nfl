# T2.3+ Tranche-Plan zum v1.0-Ziel

**Status:** Draft for adoption
**Last Updated:** 2026-04-13
**Zielkorridor:** v1.0 feature-complete bis Ende Juni 2026, Testphase Juli, produktiv vor Preseason-Start Anfang August 2026.
**Ausgangsstand:** T2.2A abgeschlossen (siehe `PROJECT_STATE.md`).

## 0. Lesehilfe

Jede Tranche hat:
- **Ziel** — fachlich verständlich.
- **Ergebnisartefakte** — was am Ende existiert.
- **Pflichtpfade** — operative CLI-/UI-Pfade, die grün sein müssen.
- **Definition of Done** — gemäß Manifest §9.
- **Kalenderfenster** — grobe Zuordnung im Zielkorridor.

Tranchen sind **klein und sequenziell**. Abhängigkeiten sind explizit. Parallelarbeit nur, wo markiert.

## 1. Phasen-Übersicht

| Phase | Kalenderfenster | Inhalt |
|---|---|---|
| **T2.2** Abschluss | KW 16 (lfd.) | VPS-Runbook abgeschlossen, lokale Preview stabil — *fast fertig* |
| **T2.3** Foundation Hardening | KW 17–18 | Job-/Run-Modell, Quarantäne, Read-Modell-Trennung, ADRs |
| **T2.4** Ontology Runtime | KW 19 | Ontologie-as-Code, Dedupe-Pipeline-Skelett |
| **T2.5** Domain Expansion | KW 20–22 | Phase-1-Domänen 2–7 (Teams, Games, Players, Rosters, Stats) |
| **T2.6** Web-UI v1.0 | KW 23–25 | Style-Guide-Implementierung, alle Pflicht-Views |
| **T2.7** Resilienz und Observability | KW 26 | Health, Freshness, Backup-Drill, Replay-Drill |
| **T2.8** v1.0 Cut auf DEV-LAPTOP | KW 26 (Ende Juni) | Release-Tag, Smoke, Handoff |
| **T3.0** Testphase auf DEV-LAPTOP | Juli 2026 | echte Saison-nahe Last, Bugfixes |
| **T3.1** VPS-Migration | Ende Juli / Anfang August | Deploy auf Contabo Windows-VPS, Cloudflare/Tailscale |
| **Produktiv** | vor Preseason-Start | live |

## 2. T2.3 — Foundation Hardening (KW 17–18)

### T2.3A — Job-/Run-Modell-Skeleton ✅ (abgeschlossen 2026-04-13)
- **Ziel:** `meta.job_definition`, `meta.job_schedule`, `meta.job_queue`, `meta.job_run`, `meta.run_event`, `meta.run_artifact`, `meta.retry_policy` als DuckDB-Tabellen mit Migration.
- **Artefakte:** Migration über `TABLE_SPECS`/`ensure_metadata_surface` in `src/new_nfl/metadata.py`, Modul `src/new_nfl/jobs/model.py` mit Pydantic-Modellen und Service-Funktionen, Tests (`tests/test_jobs_model.py`, `tests/test_jobs_cli.py`).
- **Pflichtpfade:** `cli list-jobs`, `cli describe-job`, `cli register-job`, `cli register-retry-policy` verfügbar.
- **DoD:** Tests grün (73/73), Schema dokumentiert in ADR-0025.

### T2.3B — Internal Runner ✅ (abgeschlossen 2026-04-13)
- **Ziel:** Worker-Loop, der `job_queue` claimt (Idempotency-Key, atomarer Update-claim), Job ausführt, Run schreibt, Retries gemäß Policy macht.
- **Artefakte:** `src/new_nfl/jobs/runner.py` (Claim-Loop, Executor-Registry, Retry-Logik, `replay_failed_run`), geteilter DB-Helper `src/new_nfl/_db.py`, CLI `run-worker --once|--serve` und `replay-run --job-run-id`.
- **Pflichtpfade:** `fetch-remote` und `stage-load` routen verpflichtend über den Runner; jedes CLI-Invocation erzeugt `meta.job_run`-Evidence (Manifest §3.13).
- **Defaults:** Concurrency-Key = `target_ref` (i. d. R. `adapter_id`), Backoff exponentiell `base=30s`, `factor=2`, `max=30min`, Serve-Tick 5 s idle-sleep.
- **DoD:** Replay eines fehlgeschlagenen Runs reproduziert deterministisch (verifiziert in `tests/test_jobs_runner.py::test_replay_failed_run_reproduces_deterministically`); Suite grün (90/90); ADR-0025 final accepted.

### T2.3C — Quarantäne-Domäne ✅ (abgeschlossen 2026-04-14)
- **Ziel:** `meta.quarantine_case`, `meta.recovery_action` mit CLI-Surface.
- **Artefakte:** Modul `src/new_nfl/jobs/quarantine.py` (Dedupe per `(scope_type, scope_ref, reason_code)` über offene Status, Severity-Eskalation, Evidence-Merge); Auto-Quarantäne-Hook `_auto_quarantine_failed_run` in `jobs/runner.py` bei `runner_exhausted`; CLI `list-quarantine --status`, `quarantine-show --quarantine-case-id`, `quarantine-resolve --action replay|override|suppress --note "…"`; Tests (`tests/test_quarantine.py`).
- **DoD:** Künstlich erzeugter Parser-Fehler landet in Quarantäne, Resolve `--action replay` erzeugt nachweisbar neuen `job_run_id` und schließt den Case (`tests/test_quarantine.py::test_quarantine_replay_resolves_case_on_success`); Suite grün (103/103); ADR-0028 final accepted.

### T2.3D — Read-Modell-Trennung formalisieren ✅ (abgeschlossen 2026-04-14)
- **Ziel:** Schema `mart` in DuckDB mit ersten Read-Modellen (`mart.schedule_field_dictionary_v1`). Web-Preview und CLI-Browse lesen ausschließlich aus `mart.*`.
- **Artefakte:** `src/new_nfl/mart/schedule_field_dictionary.py` (Builder mit Spalten-Tolerantem Select über `core.schedule_field_dictionary`); Runner-Executor `mart_build` in `jobs/runner.py`; CLI `mart-rebuild --mart-key …`; `core_load` triggert Mart-Build implizit am Ende des Execute-Pfads (`CoreLoadResult.mart_qualified_table` / `mart_row_count` neu); Refactor `core_browse.py`/`core_lookup.py`/`core_summary.py` auf `mart.*` (mit pre-lowercased `field_lower`/`data_type_lower`); Tests `tests/test_mart.py` (9) mit Lint-Test, der Direktzugriffe auf `core.*`/`stg.*`/`raw/` in den Read-Modulen über AST-Walk verbietet.
- **DoD:** AST-Lint-Test (`tests/test_mart.py::test_read_modules_do_not_reference_core_or_stg_directly`) ist grün, alle Read-Module zeigen `qualified_table='mart.schedule_field_dictionary_v1'`; Suite grün (112/112); ADR-0029 final accepted.

### T2.3E — ADR-Block schreiben ✅ (abgeschlossen 2026-04-14)
- **Ziel:** ADR-0025 bis ADR-0030 inhaltlich aufgesetzt und im Index verankert.
- **Ergebnis:** ADR-0025 (T2.3A/B), ADR-0028 (T2.3C), ADR-0029 (T2.3D) sind final `Accepted` mit Implementierungs-Notizen. ADR-0026 (Ontology), ADR-0027 (Dedupe), ADR-0030 (UI Stack) bleiben sinnvollerweise `Proposed` bis zur Umsetzung in der jeweils gekoppelten Tranche (T2.4A/T2.4B/T2.6A) — premature Acceptance widerspräche Manifest §3.7 (Entscheidungen im Implementierungs-Druck).
- **Artefakte:** `docs/adr/README.md` als vollständiger Index ADR-0001–ADR-0030 mit Status + Tranchen-Anker.
- **DoD:** Index zeigt jeden ADR mit Status; alle T2.3-eigenen ADRs sind `Accepted`; offene Proposed-ADRs sind dem Operator transparent.

## 3. T2.4 — Ontology Runtime (KW 19)

### T2.4A — Ontology-as-Code-Skelett
- **Ziel:** Verzeichnis `ontology/` mit YAML-Quelldateien für Begriffe, Aliases, Value Sets. Loader, der in `meta.ontology_term`, `meta.ontology_alias`, `meta.ontology_value_set` projiziert.
- **Artefakte:** `ontology/v0_1/*.yaml`, `src/new_nfl/ontology/loader.py`, `cli ontology-load`, `cli ontology-show <term>`.
- **DoD:** Bootstrap erzeugt Ontologie-Tabellen, Versionsstempel in `meta.ontology_version`.

### T2.4B — Dedupe-Pipeline-Skelett
- **Ziel:** Stub-Pipeline mit klaren Stufen (normalize → block → score → cluster → review-queue), zunächst nur deterministische Normalisierung implementiert, probabilistischer Score als TODO mit Interface.
- **Artefakte:** `src/new_nfl/dedupe/`, `cli dedupe-run --domain <name>`, ADR-0027 (bereits in T2.3E).
- **DoD:** Player-Stammdaten laufen einmal durch die Pipeline ohne Crash.

## 4. T2.5 — Domain Expansion (KW 20–22)

Sequenz pro Domäne identisch: Adapter → Stage-Load → Core-Promotion → Read-Modell.

### T2.5A — Teams (KW 20)
nflverse + ESPN als Quellen, Tier-A vs Tier-B Konfliktfall absichtlich provoziert und gelöst.

### T2.5B — Games / Schedules / Results (KW 20)
Verfeinerung des bestehenden Schedule-Pfads zu vollständigen Games (Endstand, Boxscore-Referenz).

### T2.5C — Players Stammdaten (KW 21)
nflverse + ESPN. Erste echte Dedupe-Anwendung (T2.4B).

### T2.5D — Rosters zeitbezogen (KW 21)
RosterMembership mit `valid_from`/`valid_to`, Trade-Erkennung.

### T2.5E — Team Stats Aggregate (KW 22)
Saison- und Wochen-Aggregate, Konfliktauflösung über Tiering.

### T2.5F — Player Stats Aggregate (KW 22)
Saison- und Karriere-Aggregate, mit `display_name` (vollständige offizielle Form, siehe Style Guide §1).

**Pflichtpfade nach T2.5:**
```
cli run-worker --once                  # Scheduler-Tick
cli list-ingest-runs --recent
cli quarantine-list --open
mart.team_overview_v1
mart.game_detail_v1
mart.player_overview_v1
mart.team_stats_season_v1
mart.player_stats_season_v1
```

## 5. T2.6 — Web-UI v1.0 (KW 23–25)

### T2.6A — Tailwind-Setup und Komponenten-Skelett (KW 23)
- Tailwind-Build-Pipeline in `src/new_nfl/web/`.
- Jinja-Layout (`base.html`), `_components/` mit `<Card>`, `<StatTile>`, `<DataTable>`, `<FreshnessBadge>`, `<Breadcrumb>`, `<EmptyState>`.
- Inter + JetBrains Mono self-hosted.
- Dark/Light-Toggle.
- Lucide-Icon-Sprite.

### T2.6B — Home / Freshness-Dashboard (KW 23)
liest `mart.freshness_overview_v1` und `meta.job_run` neueste, zeigt pro Domäne `<FreshnessBadge>` und Quarantäne-Counter.

### T2.6C — Season → Week → Game-Liste (KW 24)
Drilldown-Navigation, Breadcrumb.

### T2.6D — Team-Profil (KW 24)
Stammdaten, aktuelles Roster (top-25), Saisonstats, Spielhistorie.

### T2.6E — Player-Profil (KW 24)
Stammdaten, Team-Zugehörigkeit, Karriere-Stats, Stat-Tabellen mit `tnum`.

### T2.6F — Game-Detail Pre/Post (KW 25)
Pre: Aufstellung, Form. Post: Endstand, Boxscore. (Wetter, Verletzungen, Lines, Gossip kommen mit Phase-1.5.)

### T2.6G — Provenance-Drilldown (KW 25)
`<ProvenancePopover>` an Stat-Werten, Detail-Route `/provenance/<run_id>`.

### T2.6H — Run-Evidence-Browser (KW 25)
Liste der Runs mit Status, Dauer, Row Counts, Fehler. Liest `meta.job_run` + `meta.run_event`.

**Pflichtpfade nach T2.6:** alle 7 Pflicht-Views aus `USE_CASE_VALIDATION_v0_1.md` §5.4 sichtbar und gegen `mart.*` validiert.

## 6. T2.7 — Resilienz und Observability (KW 26)

### T2.7A — Health-Endpunkte
`/livez`, `/readyz`, `/health/deps`, `/health/freshness` mit JSON-Responses.

### T2.7B — Strukturiertes Logging
Pflichtfelder gemäß `OBSERVABILITY.md` und Manifest. Logs nach `data/logs/`.

### T2.7C — Backup-Drill
Lokal: DuckDB-File + `data/raw/` als ZIP exportieren, Restore-Befehl, Smoke nach Restore.

### T2.7D — Replay-Drill
Existierenden Run löschen aus `core.*`, von Raw-Artefakt replayen, Vergleich Pre/Post identisch.

## 7. T2.8 — v1.0 Cut auf DEV-LAPTOP (Ende KW 26)

- Tag `v1.0.0-laptop` auf `main`.
- Release-Notes mit Domänen-Coverage, bekannten Grenzen, Quarantäne-Stand.
- `PROJECT_STATE.md` aktualisiert auf „v1.0 feature-complete on DEV-LAPTOP".
- Handoff-Dokument für Testphase.

**Wichtig:** v1.0 läuft auf DEV-LAPTOP. **Kein** VPS-Deploy in T2.8.

## 8. ADR-Block (begleitend zu T2.3)

| ADR | Titel | Kopplung |
|---|---|---|
| ADR-0025 | Internal job and run model in DuckDB metadata | T2.3A/B |
| ADR-0026 | Ontology-as-code with runtime projection | T2.4A |
| ADR-0027 | Dedupe pipeline as explicit stage | T2.4B |
| ADR-0028 | Quarantine as first-class domain | T2.3C |
| ADR-0029 | Read-model separation (`mart.*` only for UI/API) | T2.3D |
| ADR-0030 | UI tech stack: Jinja + Tailwind + htmx + Plot | T2.6A |

ADR-Stubs werden zusammen mit diesem Plan ausgeliefert, „Accepted" wird mit Abschluss der jeweils gekoppelten Tranche gesetzt.

## 9. T3.0 — Testphase auf DEV-LAPTOP (Juli 2026)

- echte tägliche Scheduler-Ticks über mehrere Wochen.
- bewusste Quell-Ausfälle simulieren (Designed Degradation).
- Lasttest mit Backfill ~15 Saisons.
- Bugfix-Tranchen T3.0A, T3.0B, … nach Bedarf.
- DoD: 4 Wochen ununterbrochener Scheduler-Lauf ohne ungelöste Quarantäne-Eskalation.

## 10. T3.1 — VPS-Migration (Ende Juli / Anfang August)

Gemäß `RUNBOOK_VPS_PREVIEW_RELEASE.md` und VPS-Dossier:
- Tailscale-RDP validiert vor Beginn.
- Repo-Sync auf VPS, Python-Venv, DuckDB-Migration.
- Cloudflare Tunnel als Windows-Service.
- Cloudflare Access vor Web-UI.
- Smoke: `/healthz`, `/`, eine Game-Detail-Seite.
- Backup-Strategie: tägliche Provider-Snapshots des VPS (Operator-bestätigt).
- DoD: 7 Tage parallel-Lauf VPS + Laptop, identische Outputs.

## 11. Risiken und Gegenmaßnahmen

| Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|
| Quellen-API-Änderung mitten in T2.5 | Domain-Tranche verzögert | Adapter-Pattern erlaubt parallelen Fallback-Adapter |
| Dedupe-Härtefälle bei Players blockieren T2.5C | Verzögerung Stats | Review-Queue erlaubt Fortschritt mit offenen Fällen, Qualitätsmarker im UI |
| UI-Stack-Lernkurve (Tailwind/Plot/htmx) | T2.6 verzögert | T2.6A bewusst eine Woche Setup-Puffer |
| VPS-Migration-Probleme | T3.1 verzögert | bereits vorhandenes Runbook + Tailscale-Validierung vorab |
| Wetter-Backfill historisch nicht beschaffbar | Nur Phase-1.5 betroffen | dokumentiert opportunistisch |

## 12. Verweise

- `PROJECT_STATE.md`
- `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md`
- `ENGINEERING_MANIFEST_v1_3.md`
- `UI_STYLE_GUIDE_v0_1.md`
- `USE_CASE_VALIDATION_v0_1.md`
- `RUNBOOK_VPS_PREVIEW_RELEASE.md`
- ADR-0025 bis ADR-0030 (Stubs in `adr/`)
