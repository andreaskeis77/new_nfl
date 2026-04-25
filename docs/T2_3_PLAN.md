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
| **T2.7** Resilienz und Observability | KW 26 | Health, Freshness, Backup-Drill, Replay-Drill — **✅ abgeschlossen 2026-04-23** |
| **T2.8** v1.0 Cut auf DEV-LAPTOP | KW 26 (Ende Juni) | Release-Tag, Smoke, Handoff — **✅ abgeschlossen 2026-04-24** |
| **T3.1** VPS-Migration (vorgezogen) | Juni-Ende / Anfang Juli 2026 | Deploy auf Contabo Windows-VPS, Tailscale-only (keine Cloudflare-Route für NEW NFL) — **Reihenfolge geflippt, siehe [ADR-0034](adr/ADR-0034-vps-first-before-testphase.md)** |
| **T3.0** Testphase auf VPS | Juli 2026 | echte Saison-nahe Last, Bugfixes — läuft auf VPS, nicht auf DEV-LAPTOP |
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

### T2.4A — Ontology-as-Code-Skelett ✅ (2026-04-16)
- **Ziel:** Verzeichnis `ontology/` mit Quelldateien für Begriffe, Aliases, Value Sets. Loader, der in `meta.ontology_term`, `meta.ontology_alias`, `meta.ontology_value_set` projiziert.
- **Ergebnis:** TOML statt YAML (stdlib `tomllib`, keine neue Runtime-Abhängigkeit) — siehe ADR-0026 Implementierungs-Notizen. `ontology/v0_1/` mit drei Termen (`position`, `game_status`, `injury_status`), 8 Aliases, 4 Value Sets, 34 Members. Loader idempotent über `content_sha256`. Sechs `meta.ontology_*`-Tabellen (inkl. `ontology_mapping`-Skeleton für T2.5). CLI `ontology-load --source-dir … [--version-label] [--no-activate]`, `ontology-list`, `ontology-show --term-key <key|alias>`. Pydantic-Service `load_ontology_directory`/`list_terms`/`describe_term`. ADR-0026 final `Accepted`.
- **Artefakte:** [ontology/v0_1/](../ontology/v0_1), [src/new_nfl/ontology/loader.py](../src/new_nfl/ontology/loader.py), [tests/test_ontology.py](../tests/test_ontology.py).
- **DoD:** Erfüllt — Bootstrap legt `meta.ontology_*` an, `ontology-load` stempelt `meta.ontology_version` mit `content_sha256`, `is_active`-Flag pro Quellverzeichnis.

### T2.4B — Dedupe-Pipeline-Skelett ✅ (2026-04-16)
- **Ziel:** Stub-Pipeline mit klaren Stufen (normalize → block → score → cluster → review-queue), zunächst nur deterministische Normalisierung implementiert, probabilistischer Score als TODO mit Interface.
- **Ergebnis:** Fünf Module unter [src/new_nfl/dedupe/](../src/new_nfl/dedupe) (`normalize`, `block`, `score`, `cluster`, `review`) plus `pipeline.py`. Stdlib-only Normalisierung (NFKD, Suffix-Erkennung Jr./Sr./II–V). `RuleBasedPlayerScorer` (`kind=rule_based_v1`) mit sechs Score-Stufen 1.00/0.95/0.80/0.70/0.60/0.50; `Scorer`-Protocol bleibt offen für ML-Erweiterung. Connected-Components-Cluster mit Singleton-Erhalt. `meta.dedupe_run` + `meta.review_item` als Evidence. CLI `dedupe-run --domain players --demo`, `dedupe-review-list`. ADR-0027 final `Accepted`.
- **Artefakte:** [src/new_nfl/dedupe/](../src/new_nfl/dedupe), [tests/test_dedupe.py](../tests/test_dedupe.py).
- **DoD:** Erfüllt — Demo-Set (6 QB-Records inkl. Mahomes-Twin, A. Rodgers-Initial-Match, Tom-Brady-Singleton) durchläuft die Pipeline und produziert Auto-Merge + Review + No-Match in einem Lauf, persistiert in `meta.dedupe_run`/`meta.review_item`.

## 4. T2.5 — Domain Expansion (KW 20–22)

Sequenz pro Domäne identisch: Adapter → Stage-Load → Core-Promotion → Read-Modell.

### T2.5A — Teams (KW 20) ✅ (2026-04-22)
- **Ziel:** nflverse (Tier-A) + `official_context_web` (Tier-B) als Quellen, Tier-A vs Tier-B Konfliktfall absichtlich provoziert und gelöst.
- **Ergebnis:** Adapter-Slice-Registry [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) — ein `adapter_id` kann mehrere Slices bedienen; `(nflverse_bulk, teams)` als Primary auf `teams_colors_logos.csv`, `(official_context_web, teams)` als Cross-Check (Fixture-Pfad in T2.5A, reale HTTP folgt in T2.5B). `core.team` ([src/new_nfl/core/teams.py](../src/new_nfl/core/teams.py)) mit Idempotent-Rebuild (`ROW_NUMBER OVER PARTITION BY UPPER(TRIM(team_id))`), TRY_CAST für Saison-Ints, Tier-A gewinnt (ADR-0007), Tier-B-Diskrepanzen (`team_abbr`, `team_name`, `team_conference`, `team_division`, `team_color`) erzeugen pro `team_id` je einen `meta.quarantine_case` mit `reason_code='tier_b_disagreement'` und aggregierten `evidence_refs_json`. Read-Modell `mart.team_overview_v1` ([src/new_nfl/mart/team_overview.py](../src/new_nfl/mart/team_overview.py)) spalten-tolerant mit `is_active = (last_season IS NULL)` und lowercased Suchspalten. Ontologie-Terme `conference` + `division` ergänzt. CLI-Flag `--slice` an `fetch-remote`/`stage-load`/`core-load`; Default-Slice `schedule_field_dictionary` hält T2.0A-Pfade bit-kompatibel. ADR-0031 `Proposed`.
- **Artefakte:** [docs/adr/ADR-0031-adapter-slice-strategy.md](adr/ADR-0031-adapter-slice-strategy.md), [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py), [src/new_nfl/core/teams.py](../src/new_nfl/core/teams.py), [src/new_nfl/mart/team_overview.py](../src/new_nfl/mart/team_overview.py), [ontology/v0_1/term_conference.toml](../ontology/v0_1/term_conference.toml), [ontology/v0_1/term_division.toml](../ontology/v0_1/term_division.toml), [tests/test_teams.py](../tests/test_teams.py).
- **DoD:** Erfüllt — Suite grün (141/141); Tier-B-Diskrepanz auf `KC.color` + `SF.team_name` öffnet zwei Quarantäne-Cases, Operator-Override schließt Case, Tier-A-Werte bleiben in `core.team` erhalten.

### T2.5B — Games / Schedules / Results (KW 20) ✅ (2026-04-22)
- **Ziel:** Slice `(nflverse_bulk, games)` nach `core.game`, Cross-Check aus `(official_context_web, games)`, identisches Muster wie T2.5A. Erste reale HTTP-Implementierung des `official_context_web`-Adapters, Quarantäne nicht länger fixture-getrieben.
- **Ergebnis:** Zwei neue Einträge in [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) (`(nflverse_bulk, games)` primär, `(official_context_web, games)` cross_check). `core.game` ([src/new_nfl/core/games.py](../src/new_nfl/core/games.py)) mit Idempotent-Rebuild (`ROW_NUMBER OVER PARTITION BY LOWER(TRIM(game_id))`), TRY_CAST für `season`/`week`/Scores/Overtime als Integer und `gameday` als DATE, UPPER-Canonicalization der Team-Codes. Tier-A gewinnt (ADR-0007); Tier-B-Diskrepanzen auf `home_score`, `away_score`, `stadium`, `roof`, `surface` öffnen pro `game_id` je einen `meta.quarantine_case` mit `scope_type='game'` und `reason_code='tier_b_disagreement'`. Read-Modell `mart.game_overview_v1` ([src/new_nfl/mart/game_overview.py](../src/new_nfl/mart/game_overview.py)) spalten-tolerant über `DESCRIBE` + `_opt()`, abgeleitet `is_completed = (home_score IS NOT NULL AND away_score IS NOT NULL)` und `winner_team ∈ {home_team, away_team, 'TIE', NULL}`, lowercased Filter-Spalten `game_id_lower`/`home_team_lower`/`away_team_lower`. Operator-CLI `list-slices` als pipe-separierte Registry-Sicht. Erste reale HTTP-Runde für `official_context_web` end-to-end durch stdlib-`ThreadingHTTPServer` (Port 0, Daemon-Thread, CSV-Bytes) ohne neue Testabhängigkeiten — `urllib.request.urlopen` in `execute_remote_fetch` ist damit produktiv nachgewiesen. ADR-0031 final `Accepted`.
- **Artefakte:** [docs/adr/ADR-0031-adapter-slice-strategy.md](adr/ADR-0031-adapter-slice-strategy.md) (Status `Accepted` + Implementierungsnotizen), [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py), [src/new_nfl/core/games.py](../src/new_nfl/core/games.py), [src/new_nfl/mart/game_overview.py](../src/new_nfl/mart/game_overview.py), [src/new_nfl/core_load.py](../src/new_nfl/core_load.py) (Dispatch auf `core.game`), [src/new_nfl/jobs/runner.py](../src/new_nfl/jobs/runner.py) (`game_overview_v1`-Mart-Build), [src/new_nfl/cli.py](../src/new_nfl/cli.py) (`list-slices`, `CoreGameLoadResult`-Print-Branch, `--mart-key game_overview_v1`), [tests/test_games.py](../tests/test_games.py) (7 Tests inklusive ThreadingHTTPServer-Roundtrip).
- **DoD:** Erfüllt — Suite grün (148/148); Tier-A-Fixture aus vier Games (Gewinn auswärts, Gewinn zu Hause, Tie, ungespielt/NULL) rebuilden `core.game` und `mart.game_overview_v1` mit korrekten `winner_team`/`is_completed`-Ableitungen; Tier-B-Fixture mit abweichendem SF-`home_score` und KC/DEN-`stadium` öffnet zwei `meta.quarantine_case`-Einträge, Operator-Override schließt Case, Tier-A-Werte bleiben in `core.game` erhalten; echter HTTP-Roundtrip durch `urllib.request.urlopen` gegen lokalen stdlib-HTTP-Server beweist Tier-B-Flow end-to-end.

### T2.5C — Players Stammdaten (KW 21) ✅ (2026-04-22)
- **Ziel:** Slice `(nflverse_bulk, players)` nach `core.player`, Cross-Check aus `(official_context_web, players)`, erste echte Dedupe-Anwendung (T2.4B) gegen live `core.player`, gemeinsamer Result-Typ für Teams/Games/Players.
- **Ergebnis:** Zwei neue Einträge in [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) (`(nflverse_bulk, players)` primär auf `players.csv`, `(official_context_web, players)` cross_check). `core.player` ([src/new_nfl/core/players.py](../src/new_nfl/core/players.py)) mit Idempotent-Rebuild (`ROW_NUMBER OVER PARTITION BY UPPER(TRIM(player_id))`), TRY_CAST für `birth_date`/`height`/`weight`/`rookie_season`/`last_season`/`jersey_number`/`draft_year`/`draft_round`/`draft_pick`, UPPER für `position`/`current_team_id`/`draft_club`. Tier-A gewinnt (ADR-0007); Tier-B-Diskrepanzen auf `display_name`, `position`, `current_team_id`, `jersey_number` öffnen pro `player_id` je einen `meta.quarantine_case` mit `scope_type='player'`. Read-Modell `mart.player_overview_v1` ([src/new_nfl/mart/player_overview.py](../src/new_nfl/mart/player_overview.py)) spalten-tolerant über `DESCRIBE` + `_opt()`, abgeleitet `full_name = COALESCE(display_name, first_name || ' ' || last_name)`, `is_active = (last_season IS NULL)` und `position_is_known` aus der aktiven Ontologie-Version (`meta.ontology_value_set_member` für den `position`-Term; fällt auf `NULL` zurück wenn keine aktive Version geladen). Erste echte Dedupe-Anwendung: [src/new_nfl/dedupe/core_player_source.py](../src/new_nfl/dedupe/core_player_source.py) projiziert `core.player` in `RawPlayerRecord` mit `EXTRACT(YEAR FROM birth_date)` als `birth_year`; CLI `dedupe-run --domain players --source core-player` ersetzt das Demo-Set durch reale Rows. Result-Refactor: Protocol `CoreLoadResultLike` ([src/new_nfl/core/result.py](../src/new_nfl/core/result.py)) kapselt den gemeinsamen Result-Typ (`run_mode`, `run_status`, `pipeline_name`, `ingest_run_id`, `qualified_table`, `source_row_count`, `row_count`, `invalid_row_count`, `load_event_id`, `mart_qualified_table`, `mart_row_count`); CLI-Dispatch für Teams/Games/Players kollabiert von drei `isinstance`-Branches auf einen mit `_core_load_distinct_field` als Label-Helper.
- **Artefakte:** [src/new_nfl/core/result.py](../src/new_nfl/core/result.py), [src/new_nfl/core/players.py](../src/new_nfl/core/players.py), [src/new_nfl/mart/player_overview.py](../src/new_nfl/mart/player_overview.py), [src/new_nfl/dedupe/core_player_source.py](../src/new_nfl/dedupe/core_player_source.py), [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) (+2 SliceSpecs), [src/new_nfl/core_load.py](../src/new_nfl/core_load.py) (Dispatch auf `core.player`), [src/new_nfl/jobs/runner.py](../src/new_nfl/jobs/runner.py) (`player_overview_v1`-Mart-Build), [src/new_nfl/cli.py](../src/new_nfl/cli.py) (Dispatch-Refactor + `--source core-player`), [tests/test_players.py](../tests/test_players.py) (9 Tests).
- **DoD:** Erfüllt — Suite grün (157/157); Tier-A-Fixture aus fünf Players (komplett, minimal, retired, active, dedupe-Zwilling) rebuildet `core.player` und `mart.player_overview_v1` mit korrekten `full_name`/`is_active`-Ableitungen; Tier-B-Fixture mit abweichendem Rodgers-`jersey_number` und Brady-`current_team_id` öffnet zwei `meta.quarantine_case`-Einträge, Operator-Override schließt Case, Tier-A-Werte bleiben in `core.player` erhalten; echter HTTP-Roundtrip durch `urllib.request.urlopen` gegen lokalen stdlib-HTTP-Server beweist Tier-B-Flow end-to-end; Dedupe-from-Core clustert die beiden Mahomes-Player-IDs (`00-0033873` + `00-0099999`) in einen Auto-Merge-Cluster.

### T2.5D — Rosters zeitbezogen (KW 21) ✅ (2026-04-22)
- **Ziel:** Slice `(nflverse_bulk, rosters)` nach `core.roster_membership`, erste bitemporale Domäne mit Business-Time-Intervallen (`valid_from_week`/`valid_to_week`) und System-Time (`_loaded_at`); Trade-Erkennung durch Wochenüberschneidung; `meta.roster_event` als Event-Stream; zwei Read-Modelle `mart.roster_current_v1` + `mart.roster_history_v1`.
- **Ergebnis:** Zwei neue Einträge in [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) (`(nflverse_bulk, rosters)` primär auf `weekly_rosters.csv`, `(official_context_web, rosters)` cross_check). `core.roster_membership` ([src/new_nfl/core/rosters.py](../src/new_nfl/core/rosters.py)) mit CTE-Kaskade `normalized` → `deduped` (dedupe duplicate week rows by `_loaded_at DESC`) → `one_per_week` → `season_max` (global MAX(week) per season) → `grouped` (Gap-Trick: `week - ROW_NUMBER() OVER (PARTITION BY player_id, team_id, season, position, jersey_number, status ORDER BY week)` identifiziert zusammenhängende Intervalle) → `intervals` (`GROUP BY grp`) und finalem CASE für `valid_to_week = NULL ⇔ raw_valid_to_week >= global_max_week`. UPPER-Canonicalization für `player_id`/`team_id`/`position`, TRY_CAST für `season`/`week`/`jersey_number`, LOWER für `status`. `meta.roster_event`-Rebuild Python-seitig: Scan pro `(player_id, season)` über chronologisch sortierte Intervalle — Release+Signup bei Lücke, Trade bei adjacent Teamwechsel, Promoted/Demoted bei Status-Transition innerhalb desselben Teams (idempotent per DELETE-before-INSERT pro Saison). Tier-B-Konflikt-Erkennung im Grain `(player_id, team_id, season, week)` auf `position`/`jersey_number`/`status`; `scope_ref` formatiert als `PLAYER:TEAM:SEASON:Wxx`. Read-Modelle: `mart.roster_current_v1` ([src/new_nfl/mart/roster_current.py](../src/new_nfl/mart/roster_current.py)) filtert auf `valid_to_week IS NULL`, `mart.roster_history_v1` ([src/new_nfl/mart/roster_history.py](../src/new_nfl/mart/roster_history.py)) zeigt vollen Timeline mit abgeleitetem `is_open`-Boolean; beide best-effort-JOIN auf `core.player`/`core.team` (mit NULL-Fallback über `DESCRIBE`). `CoreRosterLoadResult` erfüllt `CoreLoadResultLike`-Protocol; Round-Trip-Test `isinstance(result, CoreLoadResultLike)` fixiert die T2.5C-Erweiterung. ADR-0032 `Proposed`.
- **Artefakte:** [docs/adr/ADR-0032-bitemporal-roster-membership.md](adr/ADR-0032-bitemporal-roster-membership.md), [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py), [src/new_nfl/core/rosters.py](../src/new_nfl/core/rosters.py), [src/new_nfl/mart/roster_current.py](../src/new_nfl/mart/roster_current.py), [src/new_nfl/mart/roster_history.py](../src/new_nfl/mart/roster_history.py), [src/new_nfl/core_load.py](../src/new_nfl/core_load.py) (Dispatch auf `core.roster_membership`), [src/new_nfl/jobs/runner.py](../src/new_nfl/jobs/runner.py) (`roster_current_v1` + `roster_history_v1`-Mart-Builds), [src/new_nfl/cli.py](../src/new_nfl/cli.py) (`CoreRosterLoadResult`-Print-Branch mit `INTERVAL_COUNT`/`OPEN_INTERVAL_COUNT`/`EVENT_COUNT`/`TRADE_EVENT_COUNT`/`HISTORY_QUALIFIED_TABLE`/`HISTORY_ROW_COUNT`; `--mart-key` Help-Text mit `roster_current_v1`/`roster_history_v1`), [tests/test_rosters.py](../tests/test_rosters.py) (10 Tests).
- **DoD:** Erfüllt — Suite grün (167/167); Tier-A-Fixture mit Anker-Spieler (BUF Wochen 1..9 für Saison-Max-Setzung) + KC→LV-Trade-Kandidat + Player mit Lücke (Release+Signup) + Promoted-Transition rebuildet `core.roster_membership` mit korrekten Intervallen und offenem `valid_to_week IS NULL` für aktive Spieler; `meta.roster_event` trägt `signed`/`released`/`trade`-Events an den richtigen Wochen; Tier-B-Fixture mit abweichender Rodgers-`position` in BUF Week 2 öffnet `meta.quarantine_case` mit `scope_ref='00-0034796:BUF:2024:W02'`, Operator-Override schließt Case; `mart.roster_current_v1` zeigt nur offene Intervalle, `mart.roster_history_v1` zeigt abgeschlossene plus offene Intervalle für Mahomes (KC abgeschlossen, LV offen); Protocol-Round-Trip-Test `test_core_roster_result_satisfies_core_load_protocol` bestätigt `isinstance(result, CoreLoadResultLike)`.

### T2.5E — Team Stats Aggregate (KW 22) ✅ (2026-04-22)
- **Ziel:** Slice `(nflverse_bulk, team_stats_weekly)` nach `core.team_stats_weekly`, erste aggregierende Domäne im Grain `(season, week, team_id)`; Cross-Check aus `(official_context_web, team_stats_weekly)` auf Kernmetriken; zwei Read-Modelle `mart.team_stats_weekly_v1` (Passthrough mit abgeleiteten Differenzen) + `mart.team_stats_season_v1` (Saison-Aggregat mit Bye-Week-Toleranz).
- **Ergebnis:** Zwei neue Einträge in [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) (`(nflverse_bulk, team_stats_weekly)` primär, `(official_context_web, team_stats_weekly)` cross_check). `core.team_stats_weekly` ([src/new_nfl/core/team_stats.py](../src/new_nfl/core/team_stats.py)) mit `UPPER(TRIM(team_id))`-Kanonicalisierung und TRY_CAST für `season`/`week`/`points_for`/`points_against`/`yards_for`/`yards_against`/`turnovers`/`penalties_for`. Dedupe via `ROW_NUMBER() OVER (PARTITION BY season, week, team_id ORDER BY _loaded_at DESC NULLS LAST, _source_file_id DESC)` + `WHERE _rn = 1` — letzter Load gewinnt bei Reprocessing, Reprocessing-Toleranz. Tier-B-Cross-Check im Grain `(season, week, team_id)` auf `points_for`/`points_against`/`yards_for`/`turnovers` (vier Kernmetriken) öffnet pro Konflikt einen `meta.quarantine_case` mit `scope_type='team_stats_weekly'` und `scope_ref={team_id}:{season}:W{week:02d}`. Read-Modelle: `mart.team_stats_weekly_v1` ([src/new_nfl/mart/team_stats_weekly.py](../src/new_nfl/mart/team_stats_weekly.py)) als Passthrough mit abgeleitetem `point_diff` und `yard_diff` (`CASE WHEN points_for IS NOT NULL AND points_against IS NOT NULL THEN points_for - points_against END`); `mart.team_stats_season_v1` ([src/new_nfl/mart/team_stats_season.py](../src/new_nfl/mart/team_stats_season.py)) als GROUP BY `(season, team_id)`-Aggregat mit `SUM(points_for)`, `SUM(points_against)`, `SUM(yards_for)`, `SUM(yards_against)`, `SUM(turnovers)`, `SUM(penalties_for)` und entscheidend `COUNT(points_for) AS games_played` — eine fehlende Wochen-Zeile (Bye-Week, nicht nachgeladen) erhöht `games_played` nicht. Beide Marts mit best-effort LEFT-JOIN auf `core.team` via `DESCRIBE`-Fallback (Team-Name/Abbreviation angereichert wenn vorhanden, sonst NULL). `CoreTeamStatsLoadResult` erfüllt `CoreLoadResultLike`-Protocol; eigene Round-Trip-Test `test_core_team_stats_result_satisfies_core_load_protocol`.
- **Artefakte:** [src/new_nfl/core/team_stats.py](../src/new_nfl/core/team_stats.py), [src/new_nfl/mart/team_stats_weekly.py](../src/new_nfl/mart/team_stats_weekly.py), [src/new_nfl/mart/team_stats_season.py](../src/new_nfl/mart/team_stats_season.py), [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) (+2 SliceSpecs), [src/new_nfl/core_load.py](../src/new_nfl/core_load.py) (Dispatch auf `core.team_stats_weekly`), [src/new_nfl/jobs/runner.py](../src/new_nfl/jobs/runner.py) (`team_stats_weekly_v1` + `team_stats_season_v1`-Mart-Builds), [src/new_nfl/mart/__init__.py](../src/new_nfl/mart/__init__.py) (Re-Exports), [src/new_nfl/cli.py](../src/new_nfl/cli.py) (`CoreTeamStatsLoadResult`-Print-Branch mit `SEASON_MART_QUALIFIED_TABLE`/`SEASON_MART_ROW_COUNT`; `--mart-key` Help-Text mit `team_stats_weekly_v1`/`team_stats_season_v1`; neuer `distinct_team_season_week_count`-Label-Branch), [tests/test_team_stats.py](../tests/test_team_stats.py) (8 Tests).
- **DoD:** Erfüllt — Suite grün (175/175); Tier-A-Fixture mit KC 3 Wochen (1/3/4, darunter `points_for=27`) + BAL 2 Wochen + Bye-Week-Fixture (6 Wochen im Saisonkalender 1-7 mit fehlender Woche 5) rebuildet `core.team_stats_weekly` im korrekten Grain; `mart.team_stats_weekly_v1` enthält `point_diff=7` und `yard_diff=40` für KC Week 1; `mart.team_stats_season_v1` zeigt für das Bye-Week-Team `games_played=6` (nicht 7), `SUM(points_for)` und `SUM(yards_for)` über tatsächliche 6 Wochen; Duplicate-Stage-Fixture mit zwei KC-Week-1-Rows (`points_for=17` mit älterem `_loaded_at`, `points_for=27` mit neuerem) dedupiert auf den letzten Load (`points_for=27`); Tier-B-Fixture mit abweichendem `points_for=24` für KC-Week-1 (Tier-A: 27) öffnet `meta.quarantine_case` mit `scope_ref='KC:2024:W01'`, Tier-A-Wert bleibt in `core.team_stats_weekly`; Operator-Override via `resolve_quarantine_case(action='override')` schließt Case; CoreLoad-Dispatch routet `slice_key='team_stats_weekly'` auf `execute_core_team_stats_load` und liefert `CoreTeamStatsLoadResult` mit `qualified_table='core.team_stats_weekly'`, `mart_qualified_table='mart.team_stats_weekly_v1'`, `season_mart_qualified_table='mart.team_stats_season_v1'`; Protocol-Round-Trip bestätigt `isinstance(result, CoreLoadResultLike)`.

### T2.5F — Player Stats Aggregate (KW 22) ✅ (2026-04-22)
- **Ziel:** Slice `(nflverse_bulk, player_stats_weekly)` nach `core.player_stats_weekly`, zweite aggregierende Domäne im Grain `(season, week, player_id)`; Cross-Check aus `(official_context_web, player_stats_weekly)` auf Kernmetriken; drei Read-Modelle `mart.player_stats_weekly_v1` (Passthrough + abgeleitete `total_yards`/`total_touchdowns`), `mart.player_stats_season_v1` (Saison-Aggregat mit Multi-Position-Tolerance) und `mart.player_stats_career_v1` (Karriere-Aggregat über mehrere Saisons).
- **Ergebnis:** Zwei neue Einträge in [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) (`(nflverse_bulk, player_stats_weekly)` primär, `(official_context_web, player_stats_weekly)` cross_check). `core.player_stats_weekly` ([src/new_nfl/core/player_stats.py](../src/new_nfl/core/player_stats.py)) mit `UPPER(TRIM(player_id))`-Kanonicalisierung und TRY_CAST für alle numerischen Stat-Spalten plus `team_id`/`position`/`season`/`week`. Dedupe via `ROW_NUMBER() OVER (PARTITION BY season, week, player_id ORDER BY _loaded_at DESC NULLS LAST, _source_file_id DESC)` + `WHERE _rn = 1` — letzter Load gewinnt bei Reprocessing. Tier-B-Cross-Check im Grain `(season, week, player_id)` auf `passing_yards`/`rushing_yards`/`receiving_yards`/`touchdowns` (vier Kernmetriken) öffnet pro Konflikt einen `meta.quarantine_case` mit `scope_type='player_stats_weekly'` und `scope_ref={player_id}:{season}:W{week:02d}`. Read-Modelle: `mart.player_stats_weekly_v1` ([src/new_nfl/mart/player_stats_weekly.py](../src/new_nfl/mart/player_stats_weekly.py)) als Passthrough mit abgeleitetem `total_yards = COALESCE(passing_yards,0) + COALESCE(rushing_yards,0) + COALESCE(receiving_yards,0)` und `total_touchdowns = COALESCE(touchdowns, COALESCE(passing_tds,0) + COALESCE(rushing_tds,0) + COALESCE(receiving_tds,0))`; `mart.player_stats_season_v1` ([src/new_nfl/mart/player_stats_season.py](../src/new_nfl/mart/player_stats_season.py)) als GROUP BY `(season, player_id)`-Aggregat mit `MODE(position) AS primary_position` (Multi-Position-tolerant — Taysom Hill QB/TE/RB aggregiert positions-agnostisch), `SUM()` über alle Stat-Metriken, und entscheidend `COUNT(CASE WHEN passing_yards IS NOT NULL OR rushing_yards IS NOT NULL OR receiving_yards IS NOT NULL OR touchdowns IS NOT NULL THEN 1 END) AS games_played` (bye-week-tolerant + stat-präsenzgeprüft); `mart.player_stats_career_v1` ([src/new_nfl/mart/player_stats_career.py](../src/new_nfl/mart/player_stats_career.py)) als GROUP BY `player_id`-Aggregat über alle Saisons mit `MIN(season) AS first_season`, `MAX(season) AS last_season`, `COUNT(DISTINCT CASE WHEN <has-any-stat> THEN season END) AS seasons_played` (scratched seasons ohne Stats zählen nicht) und allen Karriere-Summen; alle drei Marts mit best-effort LEFT-JOIN auf `core.player`/`core.team` via `DESCRIBE`-Fallback (display_name + team_name/abbr angereichert wenn vorhanden, sonst NULL). `CorePlayerStatsLoadResult` erfüllt `CoreLoadResultLike`-Protocol; eigene Round-Trip-Test `test_core_player_stats_result_satisfies_core_load_protocol`.
- **Artefakte:** [src/new_nfl/core/player_stats.py](../src/new_nfl/core/player_stats.py), [src/new_nfl/mart/player_stats_weekly.py](../src/new_nfl/mart/player_stats_weekly.py), [src/new_nfl/mart/player_stats_season.py](../src/new_nfl/mart/player_stats_season.py), [src/new_nfl/mart/player_stats_career.py](../src/new_nfl/mart/player_stats_career.py), [src/new_nfl/adapters/slices.py](../src/new_nfl/adapters/slices.py) (+2 SliceSpecs), [src/new_nfl/core_load.py](../src/new_nfl/core_load.py) (Dispatch auf `core.player_stats_weekly`), [src/new_nfl/jobs/runner.py](../src/new_nfl/jobs/runner.py) (drei neue Mart-Build-Branches), [src/new_nfl/mart/__init__.py](../src/new_nfl/mart/__init__.py) (Re-Exports), [src/new_nfl/cli.py](../src/new_nfl/cli.py) (`CorePlayerStatsLoadResult`-Print-Branch mit `SEASON_MART_*`/`CAREER_MART_*`; `--mart-key` Help-Text mit `player_stats_weekly_v1`/`player_stats_season_v1`/`player_stats_career_v1`; `distinct_player_season_week_count`-Label-Branch), [tests/test_player_stats.py](../tests/test_player_stats.py) (8 Tests).
- **DoD:** Erfüllt — Suite grün (183/183); Mahomes QB 3 Wochen (W1 `passing_yards=340`/`passing_tds=4`) + McCaffrey RB 2 Wochen rebuildet `core.player_stats_weekly` im korrekten Grain; `mart.player_stats_weekly_v1` zeigt für Mahomes W1 `total_yards=340`/`total_touchdowns=4`; `mart.player_stats_season_v1` zeigt für Mahomes 2024 `passing_yards=930`/`touchdowns=10`; `mart.player_stats_career_v1` zeigt für McCaffrey `first_season=2024`/`rushing_yards=215`/`receiving_yards=43`. Taysom-Hill-Edge-Case mit `player_id='00-0033357'` QB-W1/TE-W2/RB-W3 2023 + TE-W1 2024 liefert Season 2023: `games_played=3`/`passing_yards=180`/`rushing_yards=115`/`receiving_yards=67`/`touchdowns=4`, Career: `first_season=2023`/`last_season=2024`/`seasons_played=2`/`games_played=4`/`passing=180`/`rushing=120`/`receiving=107`. Duplicate-Stage-Fixture mit zwei Rows für gleiches `(season, week, player_id)` dedupiert auf den letzten `_loaded_at` (`passing_yards=300` gewinnt über `passing_yards=250`). Tier-B-Fixture mit abweichendem `passing_yards=290` (Tier-A: 300) öffnet `meta.quarantine_case` mit `scope_ref='00-0033873:2024:W01'`, Tier-A-Wert bleibt in Core. Operator-Override via `resolve_quarantine_case(action='override', triggered_by='andreas')` schließt Case. CoreLoad-Dispatch routet `slice_key='player_stats_weekly'` auf `execute_core_player_stats_load` und liefert `CorePlayerStatsLoadResult` mit `qualified_table='core.player_stats_weekly'`, `mart_qualified_table='mart.player_stats_weekly_v1'`, `season_mart_qualified_table='mart.player_stats_season_v1'`, `career_mart_qualified_table='mart.player_stats_career_v1'`; Protocol-Round-Trip bestätigt `isinstance(result, CoreLoadResultLike)`.

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

### T2.6A — UI-Fundament (KW 23) ✅ (2026-04-23)
- **Ziel:** ADR-0030 final `Accepted`, Jinja2-basierter Server-Renderer unter `src/new_nfl/web/` mit Komponenten-Macros, Tailwind-kompatible CSS-Token-Schicht mit Dark/Light-Umschaltung ohne Rekompilierung, erstes `base.html` + `home.html` als Skelett, AST-Lint-Test auf das neue Web-Modul erweitert.
- **Ergebnis:** `jinja2>=3.1` als Pflicht-Dependency in [pyproject.toml](../pyproject.toml) (+ `MarkupSafe` transitiv), `[tool.setuptools.package-data]` paketiert Templates und statische Assets unter `new_nfl.web`. Modul [src/new_nfl/web/__init__.py](../src/new_nfl/web/__init__.py) exportiert `StaticAssetResolver`/`WebRenderer`/`build_renderer`/`render_home`. [src/new_nfl/web/assets.py](../src/new_nfl/web/assets.py) kapselt `templates_dir()` + `static_dir()` + `StaticAssetResolver` mit konfigurierbarer `base_path`, Helper-Methoden `css()`/`js()`/`icon_sprite()`/`font()`. [src/new_nfl/web/renderer.py](../src/new_nfl/web/renderer.py) baut eine Jinja-Environment mit `FileSystemLoader`, `autoescape=select_autoescape(('html','xml'))`, `trim_blocks/lstrip_blocks`; zwei Filter `relative_time` (deutsche Angaben `vor X min`/`vor X h`/`vor X Tagen`) und `fmt_number` (Non-Breaking-Thousands-Separator via `\u00a0`, `—` für `None`, `Ja`/`Nein` für `bool`); `WebRenderer.render(...)` injiziert Theme, Nav-Items, Breadcrumb, Page-Title und Asset-Resolver idempotent als Template-Globals. Template-Baum: [src/new_nfl/web/templates/base.html](../src/new_nfl/web/templates/base.html) mit Pre-FOUC-Theme-Bootstrap-Script vor dem Stylesheet-Link, `<main>`-Wrapper und Footer; [src/new_nfl/web/templates/home.html](../src/new_nfl/web/templates/home.html) als Skelett-Page mit Hero, 4-Spalten-StatTile-Grid, Freshness-Card und Vorschau-Tabelle; Komponenten-Macros unter `templates/_components/`: `navbar.html` mit aktivem Nav-Marker + Theme-Toggle-Button, `breadcrumb.html` mit `aria-current="page"` für die Endstation, `card.html` mit `{% call %}`-Slot, `stat_tile.html` mit Tabular-Nums und Delta-Status-Farbe, `data_table.html` mit konfigurierbaren Spalten (`key`/`label`/`align`/`mono`) und automatischer `fmt_number`-Projektion für mono-Spalten, `freshness_badge.html` mit Status-Pill und relativer Zeitangabe, `empty_state.html` mit Titel/Body/CLI-Hint-Block. [src/new_nfl/web/static/css/app.css](../src/new_nfl/web/static/css/app.css) als hand-assemblierter Tailwind-Subset mit CSS-Custom-Properties für Zinc-Palette (Dark/Light-Varianten unter `html[data-theme='dark']` und `html[data-theme='light']`), Emerald-Akzent, Status-Farben aus Style-Guide §3.3, Typografie-Tokens, Layout-Utilities (Flex/Grid/Padding/Spacing), Card/Stat-Tile/Data-Table/Badge/Empty-State-Komponenten-Styles, `:focus-visible`-Ring mit Accent, `prefers-reduced-motion`-Reset. [src/new_nfl/web/static/js/theme.js](../src/new_nfl/web/static/js/theme.js) als minimale Event-Delegation auf `[data-theme-toggle]`, persistiert Theme in `localStorage` und flipt das `data-theme`-Attribut ohne Reload. [src/new_nfl/web/static/icons/lucide-sprite.svg](../src/new_nfl/web/static/icons/lucide-sprite.svg) als Skelett-Sprite mit Home/Check/Alert/Clock/Chevron-Right-Icons (MIT, Strichstärke 1.5). AST-Lint-Test in [tests/test_mart.py](../tests/test_mart.py) um `src/new_nfl/web/__init__.py` + `assets.py` + `renderer.py` erweitert; eigener rekursiver AST-Lint-Test in [tests/test_web_fundament.py](../tests/test_web_fundament.py) über `src/new_nfl/web/**.py`.
- **Artefakte:** [docs/adr/ADR-0030-ui-tech-stack.md](adr/ADR-0030-ui-tech-stack.md) (Status `Accepted` + Implementierungs-Notizen + Begründung Hand-Subset vs Node-CLI), [pyproject.toml](../pyproject.toml) (`jinja2>=3.1` in `dependencies`, `include-package-data=true`, `[tool.setuptools.package-data]` Glob für Templates/CSS/JS/Icons/Fonts), [src/new_nfl/web/](../src/new_nfl/web/) (Python-Modul + Templates + Static), [tests/test_web_fundament.py](../tests/test_web_fundament.py) (16 Tests), [tests/test_mart.py](../tests/test_mart.py) (`READ_MODULES` erweitert).
- **DoD:** Erfüllt — Suite grün (199/199); `render_home()` produziert valides `<!DOCTYPE html>` mit `data-theme="dark"` im Standard-Theme, `data-theme="light"` bei `theme='light'`, Fallback auf Default bei unbekanntem Theme (`theme='neon'` → `dark`); Stat-Tile „Spieler" formatiert `3072` als `3\u00a0072` (Non-Breaking-Thousand); Freshness-Badges rendern `—` für `updated_at=None`; Breadcrumb-End-Station rendert ohne `href` und mit `aria-current="page"`; Empty-State greift bei leeren Preview-Rows und rendert die CLI-Hint-Zeile mit `core-load`; Theme-Bootstrap-Script läuft im Template vor dem Stylesheet-Link (Pre-FOUC-Check per String-Index); CSS enthält beide `data-theme`-Varianten und die drei Kern-Tokens `--bg-canvas`/`--text-primary`/`--accent`; relative Zeit-Filter liefert `vor 12 min`/`vor 3 h`/`vor 5 Tagen` und akzeptiert ISO-String-Input; AST-Lint in `src/new_nfl/web/` findet keine verbotenen `core.`/`stg.`/`raw/`-Literale; ruff clean auf allen T2.6A-scoped Files.

### T2.6B — Home / Freshness-Dashboard (KW 23) ✅ (2026-04-23)
- **Ziel:** Erste echte UI-View, die ausschließlich aus `mart.*` liest. Home zeigt pro Core-Domäne eine Freshness-Kachel (`<FreshnessBadge>`-Pill mit Status-Farbe + relativer Zeit) und einen Quarantäne-Zähler, sobald offene Cases existieren.
- **Ergebnis:**
  - Neuer Mart `mart.freshness_overview_v1` ([src/new_nfl/mart/freshness_overview.py](../src/new_nfl/mart/freshness_overview.py)) aggregiert `meta.load_events` + `meta.quarantine_case` über die sechs erwarteten Core-Domänen (`team`, `game`, `player`, `roster_membership`, `team_stats_weekly`, `player_stats_weekly`): `ARG_MAX(…, recorded_at)` je `(target_schema, target_object)` für `last_ingest_run_id`/`last_event_kind`/`last_event_status`/`last_row_count`, plus `COUNT(*)` als `event_count`. `open_quarantine_count` und `quarantine_max_severity` kommen per LEFT JOIN aus `meta.quarantine_case WHERE status NOT IN ('resolved','closed','dismissed')`.
  - Abgeleitete Spalte `freshness_status` mit Kaskade `stale → fail → warn → ok` (NULL-Event → `stale`, `event_status='failed'` → `fail`, offene Quarantäne → `warn`, sonst → `ok`).
  - Cold-Start-Sicherheit: Die Projektion führt intern eine `expected_domains`-CTE, sodass immer sechs Zeilen herauskommen — auch bevor irgendein Core-Load lief.
  - Read-Service [src/new_nfl/web/freshness.py](../src/new_nfl/web/freshness.py) mit `HomeOverview`-Dataclass (Totals, Domänen-Buckets `ok`/`warn`/`stale`/`fail`), fängt fehlende Mart-Tabelle ab und liefert synthetische `stale`-Zeilen.
  - `render_home_from_settings(settings)` in [src/new_nfl/web/renderer.py](../src/new_nfl/web/renderer.py) liest den Service und rendert die echte Freshness-Liste plus Q-Badge wenn `open_quarantine_count > 0`. Die alte Demo-Context-Pfad (`render_home()` ohne Argument) bleibt erhalten für Tests, die den UI-Skelettpfad prüfen.
  - Runner-Executor `mart_build` kennt `mart_key='freshness_overview_v1'`.
  - AST-Lint-Test und `tests/test_mart.py::READ_MODULES` erweitert um `src/new_nfl/web/freshness.py`, damit die ADR-0029-Invariante (nur `mart.*` aus Read-Modulen) auch die neue Datei überwacht.
  - Neuer Test-Satz [tests/test_freshness.py](../tests/test_freshness.py) mit 19 Tests: Empty-Cold-Start (alle sechs Domänen `stale`), Latest-Event-Dedupe via `ARG_MAX`, Warn-Auf-Quarantäne, Fail-auf-`event_status='failed'`, Resolved-Cases ignoriert, Non-Core-Schemas ignoriert, Service-Fallback, Overview-Aggregation, End-to-End `render_home_from_settings`, Runner-Executor-Akzeptanz für den neuen `mart_key`, Read-Surface-Invariante.
- **DoD:** Erfüllt — Suite grün (218/218); Mart liefert sechs Zeilen auf leerer DB; `freshness_status='warn'` bei offener Quarantäne; `freshness_status='fail'` bei `event_status='failed'`; Resolved Cases erzeugen keine Warnung; Non-Core-Schemas werden ignoriert; Service gibt synthetische `stale`-Zeilen zurück wenn Mart fehlt; `render_home_from_settings` rendert alle sechs Domänen-Labels; Q-Badge taucht nur bei `open_quarantine_count > 0` auf; Runner akzeptiert `mart_key='freshness_overview_v1'`; ruff clean auf allen T2.6B-scoped Files.

### T2.6C — Season → Week → Game-Liste (KW 24) ✅ (2026-04-23)
- **Ziel:** Drilldown-Navigation `Seasons → Week → Games` als erste navigatorische View, Breadcrumb inkrementell, Empty-States je Ebene.
- **Ergebnis:**
  - Read-Service [src/new_nfl/web/games_view.py](../src/new_nfl/web/games_view.py) mit drei Funktionen `list_seasons`/`list_weeks`/`list_games`, alle Plain-Selects gegen `mart.game_overview_v1`. `SeasonSummary`/`WeekSummary`/`GameRow` als frozen Dataclasses mit abgeleiteten Properties (`is_complete`, `GameRow.label`, `GameRow.score_label` mit `—` für Unplayed, `GameRow.status` → `'final'`/`'scheduled'`).
  - Drei neue Templates [src/new_nfl/web/templates/seasons.html](../src/new_nfl/web/templates/seasons.html), [season_weeks.html](../src/new_nfl/web/templates/season_weeks.html), [week_games.html](../src/new_nfl/web/templates/week_games.html), alle extend `base.html`, konsumieren `card`+`empty_state` aus T2.6A.
  - Drei Renderer-Entrypoints `render_seasons_page`/`render_season_weeks_page`/`render_week_games_page` in [src/new_nfl/web/renderer.py](../src/new_nfl/web/renderer.py) mit inkrementell aufgebautem Breadcrumb-Tuple (`Home`, `Seasons`, `Season N`, `Woche W`), `active_nav='seasons'` markiert die Navbar.
  - `GameRow` macht im Template `data-testid="game-row"` + `data-game-id=…` verfügbar — liest sich sauber in zukünftigen htmx-Partial-Responses (T2.6F) und erlaubt Tests deterministisches Matching.
  - AST-Lint-Schutz erweitert: `tests/test_mart.py::READ_MODULES` kennt den neuen Service, `tests/test_web_fundament.py`-`rglob('*.py')` findet ihn automatisch.
  - Neuer Test-Satz [tests/test_games_view.py](../tests/test_games_view.py) mit 15 Tests: Cold-Start (leeres Tuple), Season-Ordering DESC, Counts+min/max_week, Week-Filter per Saison, Game-Ordering (gameday NULLS LAST → gametime → home_team), Score-Dash für Null-Scores, Drei-Render-Pfade, Breadcrumb-Chain, Empty-States je Ebene, Nav-Active-Marker.
- **DoD:** Erfüllt — Suite grün (233/233); `list_seasons` sortiert DESC; `list_weeks` filtert per `season`-Param und sortiert ASC; `list_games` ordnet `gameday → gametime → home_team`; `render_seasons_page` zeigt Empty-State wenn Mart fehlt; Week-Ansicht zeigt `—` statt Score bei Unplayed; Breadcrumb-Chain hat `href="/"`, `href="/seasons"`, `href="/seasons/2024"` und `aria-current="page"` an der Endstation; ruff clean auf allen T2.6C-scoped Files.

### T2.6D — Team-Profil (2026-04-23, abgeschlossen)
Stammdaten, aktuelles Roster, Saisonstatistiken und Spielhistorie je Team.

- Umgesetzt:
  - Neuer Read-Service [src/new_nfl/web/team_view.py](../src/new_nfl/web/team_view.py) orchestriert vier Mart-Zugriffe: `list_teams(settings)` rendert die Teams-Index-Karten mit LEFT-JOIN auf die aktuelle `mart.team_stats_season_v1`-Zeile (`ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY season DESC) = 1`), fällt bei fehlender Stats-Tabelle auf einen Plain-Select mit NULL-Stats zurück. `get_team_profile(settings, team_key, season=None)` ist der Single-Call für die Profil-Seite: case-insensitive Lookup über `team_id_lower`/`team_abbr_lower`, Roster aus `mart.roster_current_v1` (ORDER BY position, jersey_number, display_name), Saison-Historie aus `mart.team_stats_season_v1` DESC, Spielhistorie aus `mart.game_overview_v1` gefiltert auf `home_team_lower = ? OR away_team_lower = ?` in `selected_season`. `_load_game_seasons` liefert `available_seasons` DESC und wird als Picker im Template gerendert; fehlt die angefragte Saison in `available`, fällt der Service auf `available[0]` zurück, bei leerer Liste auf `None`.
  - Per-Team-Dataclasses: `TeamCard` (Index-Zeile mit Latest-Season-Kennzahlen), `TeamMeta` (Stammdaten + `is_active`), `RosterEntry` (mit `jersey_label`-Property), `TeamSeasonStatsRow` (mit `points_per_game`-Property), `TeamGameRow` mit `outcome ∈ {win,loss,tie,scheduled}` nach Team-Perspektive (dreht home/away zu `is_home`, `score_for`/`score_against`, `opponent`), `TeamProfile.record_label` rechnet daraus W–L / W–L–T.
  - Zwei neue Templates: [src/new_nfl/web/templates/teams.html](../src/new_nfl/web/templates/teams.html) mit `data-testid="team-row"` + `data-team-id`/`data-team-abbr` pro Zeile, Empty-State-Hint mit `core-load --slice teams --execute`; [src/new_nfl/web/templates/team_profile.html](../src/new_nfl/web/templates/team_profile.html) mit vier Sektionen (Stammdaten als `data-table`, Roster, Saison-Stats, Spielhistorie), Saison-Picker als inline-Liste mit aktiver Saison in `font-semibold`, 404-Zweig wenn `profile is None`.
  - Zwei neue Renderer-Entrypoints `render_teams_page`/`render_team_profile_page` in [src/new_nfl/web/renderer.py](../src/new_nfl/web/renderer.py); Breadcrumb `Home › Teams` bzw. `Home › Teams › {team_name}`; `active_nav='teams'` setzt den Nav-Active-Marker.
  - AST-Lint-Schutz erweitert: `tests/test_mart.py::READ_MODULES` kennt den neuen Service; `tests/test_web_fundament.py`-`rglob('*.py')` findet ihn automatisch.
  - Neuer Test-Satz [tests/test_team_view.py](../tests/test_team_view.py) mit 19 Tests: Cold-Start (Empty-Tuple), Conference/Division/Name-Ordering, Latest-Season-Join, `is_active`-Flag, 404-Pfad, case-insensitive Lookup, Roster-Ordering (position, jersey), Season-Stats-DESC, Game-Season-Default + explizit + unbekannt-Fallback, Perspektive-Inversion je `is_home`, Record-Label, Empty-State im Renderer, Template-Breadcrumb, Saison-Query-Param.
- **DoD:** Erfüllt — Suite grün (252/252); `list_teams` sortiert Conference → Division → Name; `get_team_profile` lädt vier Marts in einer Connection und gibt `None` bei unbekanntem Key; `TeamGameRow.outcome` mappt `win`/`loss`/`tie`/`scheduled` korrekt; Template rendert `data-testid="roster-row"`/`season-stats-row"`/`team-game-row"`; 404-Karte zeigt `requested_key` als Hint; ruff clean auf allen T2.6D-scoped Python-Files.

### T2.6E — Player-Profil (2026-04-23, abgeschlossen)
Stammdaten, aktuelle Team-Zugehörigkeit, Karriere-Totale, Saison-Historie und Roster-Timeline je Spieler.

- Umgesetzt:
  - Neuer Read-Service [src/new_nfl/web/player_view.py](../src/new_nfl/web/player_view.py) orchestriert vier Mart-Zugriffe: `list_players(settings, offset=0, limit=50)` liefert eine paginierte Liste aus `mart.player_overview_v1` sortiert `is_active DESC, last_season DESC NULLS LAST, display_name, player_id` mit LEFT-JOIN auf `mart.team_overview_v1` (`team_id_lower`) für `current_team_abbr`; fällt bei fehlender Team-Mart auf einen Plain-Select ohne Team-Anreicherung zurück und gibt bei fehlender Player-Mart eine leere `PlayerListPage` zurück. `get_player_profile(settings, player_id)` macht case-insensitive Lookup über `player_id_lower`, lädt Stammdaten aus `mart.player_overview_v1` (mit Team-Join für `current_team_abbr`/`current_team_name`), Karriere-Snapshot aus `mart.player_stats_career_v1` (`LIMIT 1`), Saison-Historie aus `mart.player_stats_season_v1` DESC und Roster-Intervalle aus `mart.roster_history_v1` DESC. Slices, die fehlen, werden als `None`/leeres Tuple zurückgegeben, nicht als Exception.
  - Per-Player-Dataclasses: `PlayerCard` (Index-Zeile mit `jersey_label`/`seasons_label`/`status_label`/`display_label`-Kaskade display_name → full_name → player_id), `PlayerMeta` (Stammdaten mit `height_label` inch→ft'in", `weight_label`, `draft_label` `2017 · R1·P10 · KC`, `seasons_label` `2017–heute`/`2000–2022`), `PlayerCareerSnapshot` (mit `span_label`), `PlayerSeasonStatsRow` (Passthrough DESC), `PlayerRosterInterval` (mit `week_range_label` `W1–offen`/`W1–W17` basierend auf `is_open` aus ADR-0032-Roster-Mart), `PlayerProfile` (Bundle mit `season_count`/`team_count`-Properties), `PlayerListPage` (Pagination-Dataclass mit `has_prev`/`has_next`/`prev_offset`/`next_offset`/`page_range_label`).
  - Zwei neue Templates: [src/new_nfl/web/templates/players.html](../src/new_nfl/web/templates/players.html) mit `data-testid="player-row"` + `data-player-id` pro Zeile, Pagination-Links mit `data-testid="player-pagination"` und `offset`/`limit`-Query-Params, Empty-State-Hint mit `core-load --slice players --execute`; [src/new_nfl/web/templates/player_profile.html](../src/new_nfl/web/templates/player_profile.html) mit vier Karten (Stammdaten als `data-table`, Karriere-Totale als `data-table`, Saison-Historie als klassische Tabelle mit `data-testid="player-season-row"`, Roster-Historie mit `offen`/`geschlossen`-Badge pro Intervall), 404-Zweig wenn `profile is None`.
  - Zwei neue Renderer-Entrypoints `render_players_page`/`render_player_profile_page` in [src/new_nfl/web/renderer.py](../src/new_nfl/web/renderer.py); Breadcrumb `Home › Players` bzw. `Home › Players › {display_label}`; `active_nav='players'` setzt den Nav-Active-Marker.
  - AST-Lint-Schutz erweitert: `tests/test_mart.py::READ_MODULES` kennt den neuen Service; `tests/test_web_fundament.py`-`rglob('*.py')` findet ihn automatisch.
  - Neuer Test-Satz [tests/test_player_view.py](../tests/test_player_view.py) mit 19 Tests: Cold-Start (Empty-PlayerListPage), `is_active DESC → last_season DESC NULLS LAST → display_name`-Ordering, Team-Abbr-Anreicherung via JOIN, Fallback ohne Team-Mart, Pagination (offset/limit/disjoint-pages), Seasons-Label, 404-Pfad, case-insensitive Lookup, Team-Name-Join, Career-Span-Label, Height-Format, Draft-Label, Career-Missing-Returns-None-Slice, Season-Stats DESC, Roster-History mit offenen und geschlossenen Intervallen, Template-Breadcrumb.
- **DoD:** Erfüllt — Suite grün (271/271); `list_players` paginiert korrekt (`has_prev`/`has_next` stimmen mit `total` überein); `get_player_profile` lädt vier Marts in einer Connection und gibt `None` bei unbekanntem Player; `PlayerRosterInterval.week_range_label` liefert `W1–offen` für offene Intervalle; Template rendert `data-testid="player-row"`/`career-snapshot"`/`player-season-row"`/`player-roster-interval"`; 404-Karte zeigt `requested_key` als Hint; ruff clean auf allen T2.6E-scoped Python-Files.

### T2.6F — Game-Detail Pre/Post (2026-04-23, abgeschlossen)
- **Liefereinheiten:** [src/new_nfl/web/game_view.py](../src/new_nfl/web/game_view.py) (neuer Read-Service mit Bundle-Pattern: `get_game_detail(settings, game_id) → GameDetail | None` orchestriert vier Mart-Zugriffe in einer DuckDB-Connection); [src/new_nfl/web/templates/game_detail.html](../src/new_nfl/web/templates/game_detail.html) (Pre/Post-Branching-Template mit 404-Karte); [src/new_nfl/web/renderer.py](../src/new_nfl/web/renderer.py) (neuer Entrypoint `render_game_detail_page`); [src/new_nfl/web/__init__.py](../src/new_nfl/web/__init__.py) (Exports `GameMeta`/`GameDetail`/`TeamSideForm`/`TeamSideWeek`/`BoxscorePlayer`/`get_game_detail`/`render_game_detail_page`); [tests/test_game_view.py](../tests/test_game_view.py) (13 neue Tests: Empty-State je Mart, Pre- vs. Post-Branch, Score-/Status-/Winner-Label inkl. TIE → `Unentschieden`, OT-Suffix `Final (OT)`, case-insensitive Lookup, Form-Aggregation aus `point_diff`-Zeichen, Top-N-Boxscore-Ordering, Template-Rendering mit Breadcrumb-Chain); [tests/test_mart.py](../tests/test_mart.py) (READ_MODULES erweitert um `src/new_nfl/web/game_view.py`).
- **Entwurfsnotizen:**
  - Pre/Post-Split folgt `meta.is_completed` aus `mart.game_overview_v1`. Pre-Game lädt ausschließlich die Form beider Teams via `SUM(CASE WHEN point_diff > 0 ...)` aggregiert über `WHERE season=? AND week<? AND LOWER(team_id)=LOWER(?) AND point_diff IS NOT NULL`. Post-Game lädt zusätzlich die Wochenzeile (`week=?`) und den Top-10-Boxscore (`ORDER BY total_yards DESC NULLS LAST LIMIT 10`).
  - Bundle-Pattern aus T2.6D/T2.6E konsequent weitergeführt: eine Service-Funktion, eine Connection, ein nested Dataclass. Pre-Game vs. Post-Game sind *ein* Datentyp (`GameDetail`) mit unterschiedlich populierten Slots — das Template verzweigt nur über `detail.is_pre_game`.
  - UX-Labels leben auf dem Dataclass (`score_label`, `status_label`, `kickoff_label`, `venue_label`, `matchup_label`, `home_label`/`away_label`, `winner_label`, `record_label`). Das Template bleibt formatierungsfrei — Regel aus T2.6E-Lessons bestätigt.
  - `winner_team='TIE'` wird auf `winner_label='Unentschieden'` gemappt, damit das Template keine String-Logik braucht. `overtime>0` setzt `status_label='Final (OT)'`.
  - Drei unabhängige Cold-Start-per-Mart-Tests (kein team_overview → Team-Name None aber Meta ok, kein team_stats_weekly → form/week None, kein player_stats_weekly → Boxscore leer) beweisen das Slice-für-Slice-Degradieren.
  - JOIN zu `mart.team_overview_v1` ausschließlich via `team_id_lower` — die gleiche Regel wie in [src/new_nfl/web/player_view.py](../src/new_nfl/web/player_view.py). `team_abbr_lower` ist zwar ebenfalls vorhanden, aber nicht der kanonische Join-Key.
- **DoD:** Erfüllt — Suite grün (284/284); `get_game_detail` lädt bis zu vier Marts in einer Connection und gibt `None` bei unbekannter Game-ID; Pre/Post-Branch wählt korrekt zwischen Form vs. Wochenzeile+Boxscore; `GameMeta.winner_label` resolved `TIE` → `Unentschieden`, `overtime>0` → `Final (OT)`; Template rendert `data-testid="game-header"`/`pre-game`/`post-game-teams"`/`post-game-boxscore"`/`boxscore-row"`; Breadcrumb `Home › Seasons › Season N › Woche W › {matchup}`; 404-Karte zeigt `requested_key` als Hint; ruff clean auf allen T2.6F-scoped Python-Files.

### T2.6G — Provenance-Drilldown (KW 25) — **Done (2026-04-23)**
- **Ziel:** Vom Drilldown jeder Domain-Row (Team, Game, Player, Weekly-Stats, Roster) zurück zu den erzeugenden Source-Files und offenen Quarantäne-Cases navigieren — ohne die Read-Surface-Invariante (ADR-0029) zu brechen. Ein zentrales `/provenance`-Verzeichnis mit Detail-Route `/provenance/<scope_type>/<scope_ref>`.
- **Scope:**
  - Neues Mart `mart.provenance_v1` ([src/new_nfl/mart/provenance.py](../src/new_nfl/mart/provenance.py)) im Grain `(scope_type, scope_ref)` — eine Zeile pro beobachtbarem Objekt im Pipeline-Vokabular. Sechs Core-Domänen werden projiziert: `team` → `scope_ref=team_id`, `game` → `scope_ref=game_id`, `player` → `scope_ref=player_id`, `team_stats_weekly` → `scope_ref={team_id}:{season}:W{week:02d}`, `player_stats_weekly` → `scope_ref={player_id}:{season}:W{week:02d}`, `roster_membership` → `scope_ref={player_id}:{team_id}:{season}:W{week:02d}`.
  - Defensive Union: `_table_exists(con, schema, name)` prüft pro Domäne, ob die Core-Tabelle existiert, und überspringt sie sonst — auf einer frischen DB ohne Core-Loads liefert der Builder eine leere Projektion statt eines Exceptions.
  - Source-Aggregation: `LIST(DISTINCT field) FILTER (WHERE field IS NOT NULL) AS source_file_ids` + `source_adapter_ids`, `MIN(_canonicalized_at) AS first_seen_at`, `MAX(_canonicalized_at) AS last_canonicalized_at`, `COUNT(*) AS source_row_count`.
  - Quarantäne-Aggregation per LEFT-JOIN auf `meta.quarantine_case`: `COUNT(*) AS quarantine_case_count`, `COUNT(*) FILTER (WHERE status NOT IN ('resolved','closed','dismissed')) AS open_quarantine_count`, plus `ARG_MAX(reason_code, last_seen_at)` / `ARG_MAX(severity, last_seen_at)` / `ARG_MAX(status, last_seen_at)` / `MAX(last_seen_at) AS last_quarantine_at` für den jüngsten Case.
  - Abgeleiteter `provenance_status`: `open_quarantine_count > 0 → 'warn'` · `source_row_count = 0 AND quarantine_case_count = 0 → 'unknown'` · sonst `'ok'`.
  - `scope_type_lower`/`scope_ref_lower` als Shadow-Spalten — case-insensitive Reads ohne Cast zur Query-Zeit.
  - Read-Service [src/new_nfl/web/provenance_view.py](../src/new_nfl/web/provenance_view.py) liest ausschließlich aus `mart.provenance_v1`. `list_provenance(settings, *, offset=0, limit=50, scope_type=None)` sortiert `open_quarantine_count DESC, last_canonicalized_at DESC NULLS LAST, scope_type, scope_ref`. `get_provenance(settings, scope_type, scope_ref)` macht case-insensitive Lookup über beide `*_lower`-Spalten.
  - `ProvenanceRecord.quarantine_label` gibt UX-fertige Strings zurück: `—` (keine Cases), `1 offen` / `2 offen` (nur offen oder nur open==total), `1 offen / 2 total` (gemischt), `2 geschlossen` (alle zu).
  - `ProvenanceListPage` als Pagination-Bundle (`has_prev`/`has_next`/`prev_offset`/`next_offset`/`page_range_label`) — gleicher Pattern wie `PlayerListPage` aus T2.6E.
  - Zwei neue Templates: `provenance.html` (Index mit Filter-Header, Spalten Scope-Typ/Scope-Ref/Adapter/Files/Quelle/Quarantäne/Status/Drilldown, `data-testid="provenance-row"`, Pagination mit dynamischer base_url je Scope-Type-Filter) und `provenance_detail.html` (Header mit `data-testid="provenance-header"` + `data-scope-type`/`-ref`, Status-Badge, Adapter+Ingest-Tabelle, Quarantäne-Karte oder Empty-State, 404-Karte bei `record is None`).
  - Navbar: neuer Eintrag `Provenance` zwischen `Players` und `Runs` — vor Run-Evidence, aber hinter den Domain-Views.
  - Zwei neue Renderer-Entrypoints `render_provenance_page(settings, *, offset, limit, scope_type=None)` und `render_provenance_detail_page(settings, scope_type, scope_ref)` mit 2- bzw. 4-Level-Breadcrumb.
  - Runner-Registry kennt `mart_key='provenance_v1'` (elif-Branch in `_executor_mart_build`).
- **Entscheidungen:**
  - **Zentrale Route statt pro-Domain-Provenance:** Ein `/provenance/<scope_type>/<scope_ref>` deckt alle sechs Domänen ab. Der Nutzer bewegt sich immer in der gleichen UX, egal ob er von einem Game, einem Player oder einer Weekly-Stats-Row kommt. Alternative wäre `/teams/<abbr>/provenance`, `/games/<id>/provenance`, … — das hätte sechs parallele Routen und sechs parallele Templates bedeutet.
  - **Mart als Projektion, nicht direkter `meta.*`-Read:** ADR-0029 zwingt `mart.*`-only; die Alternative (LEFT-JOINs direkt aus `meta.load_events` / `meta.quarantine_case` im Read-Service) hätte die Invariante gebrochen. `mart.provenance_v1` ist die Projektion, die den AST-Lint passiert.
  - **UNION-ALL statt pro-Domain-Parallel-Table:** Ein einzelnes Mart mit sechs UNION-ALL-Branches ist einfacher zu cachen, einfacher zu filtern und einfacher zu paginieren als sechs separate Provenance-Marts. Die sechs Scope-Types bleiben als First-Class-Dimension ersichtlich (Filter-Header im Index).
  - **`LIST(DISTINCT …) FILTER (WHERE … IS NOT NULL)` für Array-Aggregation:** DuckDB's nativer Array-Support erlaubt deterministische Aggregation ohne String-Join-Hack. `source_file_ids`/`source_adapter_ids` sind `VARCHAR[]`-Spalten, die direkt an Jinja durchgereicht werden.
  - **Einen Datentyp statt Pre/Post-Split:** Scope-Types mit Source ohne Quarantäne (`ok`) und ohne Source aber mit Quarantäne (`unknown`/`warn`) werden durch **einen** Dataclass mit Optional-Slots abgebildet, analog zur T2.6F-Entscheidung `GameDetail is None`-Branch.
  - **`ARG_MAX` für jüngsten Quarantäne-Case:** Wenn ein Scope mehrere Cases hat, interessiert den Operator der jüngste — `ARG_MAX(reason_code, last_seen_at)` macht das deterministisch.
- **DoD:** Erfüllt — Full-Suite 300/300 grün; `mart.provenance_v1` baut idempotent (zweiter Build-Call liefert identische Projektion), defensiver per-Domain-`_table_exists`-Check lässt Builder auf leerer DB durchlaufen; `list_provenance` paginiert und filtert case-insensitive; `get_provenance` findet Scope case-insensitive und gibt `None` für unbekannte Kombinationen; Template rendert `data-testid="provenance-row"` im Index und `data-testid="provenance-header"`/`source-file-list` im Detail; 404-Karte bei `record is None`; Navbar-Item auf `provenance`; Breadcrumb-Chain 4-Level bis `{scope_type} › {scope_ref}`; AST-Lint (ADR-0029) auf `src/new_nfl/web/provenance_view.py` erweitert; ruff clean auf allen T2.6G-scoped Files.

### T2.6H — Run-Evidence-Browser (KW 25) — abgeschlossen 2026-04-23

- **Ziel:** Jeder interne Run (`fetch_remote`, `stage_load`, `core_load`, `mart_build`, `dedupe_run`) wird in der UI sichtbar: Status, Dauer, Event-Stream, Artefakte. Der Operator findet den verursachenden Run zu jeder Quarantäne / jedem Fehler in der UI ohne CLI-Dump.
- **Scope:**
  - Neues Mart-Modul [src/new_nfl/mart/run_evidence.py](../src/new_nfl/mart/run_evidence.py) mit **einem Builder `build_run_evidence_v1(settings)`** und **drei Read-Projektionen** unter **einem Mart-Key `run_evidence_v1`**:
    - `mart.run_overview_v1` im Grain `job_run_id` — aggregiert `meta.job_run` + `meta.job_definition` + Event-/Artefakt-CTEs. CTE `event_agg` mit `COUNT(*) AS event_count`, `SUM(CASE WHEN LOWER(severity) IN ('error','critical','fatal') THEN 1 ELSE 0 END) AS error_event_count`, `SUM(CASE WHEN LOWER(severity) IN ('warn','warning') THEN 1 ELSE 0 END) AS warn_event_count`, `MAX(recorded_at) AS last_event_recorded_at`; CTE `artifact_agg` mit `COUNT(*) AS artifact_count`; LEFT-JOIN per `job_run_id` / `job_def_id`. Abgeleitete Spalte `duration_seconds = EXTRACT(EPOCH FROM (finished_at - started_at))` gdw. beide NOT NULL; `run_status_lower` als Shadow-Spalte für case-insensitive Reads.
    - `mart.run_event_v1` als Passthrough über `meta.run_event` mit `job_run_id_lower`, `severity_lower`, `event_kind_lower`.
    - `mart.run_artifact_v1` als Passthrough über `meta.run_artifact` mit `job_run_id_lower`, `kind_lower`.
  - Cold-Start-Sicherheit: `_ensure_metadata_tables(con)` legt CREATE TABLE IF NOT EXISTS-Stubs für `meta.job_definition` / `meta.job_run` / `meta.run_event` / `meta.run_artifact` an — auf einer frischen DB ohne einen einzigen Run läuft der Builder idempotent durch und schreibt leere Projektionen.
  - Read-Service [src/new_nfl/web/run_view.py](../src/new_nfl/web/run_view.py) liest ausschließlich aus den drei `mart.run_*`-Tabellen (ADR-0029). `list_runs(settings, *, offset=0, limit=50, status=None)` sortiert `started_at DESC NULLS LAST, job_run_id` mit optionalem Status-Filter via `run_status_lower = LOWER(?)` und Pagination im `RunListPage`-Bundle. `get_run_detail(settings, job_run_id)` macht case-insensitive Lookup über `job_run_id_lower`, lädt Events + Artefakte nur wenn die jeweilige Mart-Tabelle existiert (DESCRIBE-Guard) und gibt `RunDetail(summary, events, artifacts)` zurück.
  - `RunSummary` mit UX-Properties: `status_label` (DE-Mapping `success→OK`, `failed→Fehlgeschlagen`, `running→Läuft`, `pending→Wartend`, `retrying→Wiederholung`, `quarantined→Quarantäne`), `duration_label` (`—` · `<1s` · `{s}s` · `{m}m {s}s` · `{h}h {m}m`), `job_label` (Fallback job_key→job_def_id→`—`), `attempt_label` (`Versuch N/M` oder `Versuch N`), `evidence_label` (`N Events · M err · K warn · L Artefakte`). `RunEventRow.severity_label` und `RunArtifactRow.ref_label` (Fallback ref_path→ref_id→`—`).
  - Zwei neue Templates:
    - `runs.html` (Index-Tabelle mit Spalten Start/Job/Typ/Status/Dauer/Attempt/Evidence/Drilldown, `data-testid="run-row"` + `data-job-run-id`, Status-Badges `success→status-success`, `failed`/`quarantined→status-warn`, sonst `status-neutral`, Pagination mit `data-testid="run-pagination"`, Empty-State-Hint `cli mart-rebuild --mart-key run_evidence_v1`).
    - `run_detail.html` (404-Branch bei `detail is None`; Header mit `data-testid="run-header"` + `data-job-run-id` + `data-run-status`; Stammdaten-Card mit Job-Key/Type/Worker/Start/Ende/Message; Event-Stream-Card mit `data-testid="run-event-row"` oder Empty-State `Keine Events für diesen Run`; Artefakte-Card mit `data-testid="run-artifact-row"` oder Empty-State `Keine Artefakte für diesen Run`).
  - Zwei neue Renderer-Entrypoints `render_runs_page(settings, *, offset, limit, status=None)` und `render_run_detail_page(settings, job_run_id)` in [src/new_nfl/web/renderer.py](../src/new_nfl/web/renderer.py), Breadcrumbs `Home › Runs` (oder `Home › Runs › {status}`) bzw. `Home › Runs › {job_run_id}`, `active_nav='runs'`. Der Navbar-Eintrag `Runs` existiert seit T2.6A und wurde damit jetzt erstmals mit einem echten View verdrahtet.
  - Runner-Registry kennt `mart_key='run_evidence_v1'` (elif-Branch in `_executor_mart_build`) — ein einziger `mart_build`-Job baut alle drei Projektionen gemeinsam.
- **Entscheidungen:**
  - **Drei Marts, ein Builder, ein Mart-Key:** Events und Artefakte haben andere Spalten-Sets und Kardinalität als die Overview-Zeile. Trotzdem gehören sie als Evidence zusammen und sollen nur **gemeinsam** neu aufgebaut werden. Analog zum T2.5E/F-Pattern (`team_stats_weekly_v1` + `team_stats_season_v1`, `player_stats_weekly_v1` + `player_stats_season_v1` + `player_stats_career_v1`) — aber diesmal fassen wir die drei unter **einem** Runner-Mart-Key zusammen, damit sie nicht drift-fähig werden. Alternative (nested-Arrays in Overview) hätte große `details_json`-Blobs erzeugt und die case-insensitive Detail-Queries erschwert.
  - **`_ensure_metadata_tables`-Stub im Builder:** Auf einer frisch gebootstrappten DB existiert `meta.job_run` noch nicht, bis der erste Runner-Tick durchgelaufen ist. Statt den Builder zu failen (und den Home-Aufruf über `cli web-preview` zu brechen), stampft er die vier `meta.*`-Tabellen vorsichtig ein — das ist ein idempotentes `CREATE TABLE IF NOT EXISTS` und bleibt Seiteneffekt-frei, wenn die Tabellen bereits bestehen.
  - **DE-Localization auf der Service-Dataclass, nicht im Template:** Status-Labels und Duration-Formate leben als `@property` auf `RunSummary`/`RunEventRow`/`RunArtifactRow`. Gleiches Pattern wie T2.6D (`TeamProfile.record_label`), T2.6E (`PlayerMeta.height_label`), T2.6F (`GameMeta.score_label`). Das Template bleibt Format-agnostisch.
  - **LEFT-JOIN auf Events/Artefakte, nicht INNER:** Runs ohne Events (z. B. `pending`-Runs kurz nach `enqueue_job`) müssen trotzdem in der Overview erscheinen. `event_count = 0` ist eine valide Information.
  - **Passthroughs mit `*_lower`-Shadow-Spalten:** Events und Artefakte sind klein genug, dass ein Projektion-Overhead vernachlässigbar ist; der Gewinn ist case-insensitive `get_run_detail` ohne Query-Zeit-Cast.
  - **Event-Retention vorerst NICHT im Scope:** `meta.run_event` kann über Monate wachsen. Wir bauen den Browser vollständig und verlassen Retention/Pagination-Strategien (Trimming alter Runs) auf T2.7A (Health-Endpunkte) oder später.
- **DoD:** Erfüllt — Full-Suite 323/323 grün; `build_run_evidence_v1` baut idempotent auf leerer DB ohne Exception (zweiter Build-Call liefert identische Projektionen); alle drei Mart-Tabellen sind per DESCRIBE auffindbar und haben die erwarteten `*_lower`-Shadow-Spalten; `list_runs` paginiert und filtert Status case-insensitive; `get_run_detail` findet Run case-insensitive und gibt `None` für unbekannte `job_run_id`; Template rendert `data-testid="run-row"`/`run-event-row"`/`run-artifact-row"`; 404-Karte bei `detail is None`; Navbar-Item auf `runs`; Breadcrumb-Chain mit Status-Filter-Variante; AST-Lint (ADR-0029) auf `src/new_nfl/web/run_view.py` erweitert; ruff clean auf allen T2.6H-scoped Files.

**Pflichtpfade nach T2.6:** alle 7 Pflicht-Views aus `USE_CASE_VALIDATION_v0_1.md` §5.4 sichtbar und gegen `mart.*` validiert. — **Mit T2.6H vollständig erfüllt.**

## 6. T2.7 — Resilienz und Observability (KW 25–26, parallelisiert)

Nach Abschluss von T2.6 hat das Projekt einen Umfang erreicht, bei dem sequenzielle Einzel-Session-Entwicklung teurer ist als parallele Streams mit klarer Scope-Trennung. T2.7 wird daher in **einen Vorbereitungs-Bolzen plus drei parallele Feature-Streams plus eine Integrations-Session** zerlegt. Details zur Stream-Architektur, Branch-Strategie und Risiko-Matrix stehen in [PARALLEL_DEVELOPMENT.md](PARALLEL_DEVELOPMENT.md).

### T2.7P — Parallelisierungs-Prep (KW 25, sequenziell, vor den Streams) — abgeschlossen (2026-04-23)

**Ziel:** Die drei Konflikt-Zonen aus dem Code-Review (Mart-Builder if/elif in `jobs/runner.py`, 50+ Subcommands in monolithischem `cli.py`, Re-Export-Hubs in `web/__init__.py` und `mart/__init__.py`) auflösen, damit die drei Feature-Streams additiv arbeiten können, ohne an zentralen Files zu mergen.

**Umgesetzter Scope (siehe [ADR-0033](adr/ADR-0033-registry-pattern-for-parallel-development.md) Accepted 2026-04-23):**
- [src/new_nfl/mart/_registry.py](../src/new_nfl/mart/_registry.py) mit `@register_mart_builder(mart_key)`-Decorator; alle **14 Mart-Builder** (für 16 Mart-Tabellen — `run_evidence_v1` bündelt `run_overview_v1`/`run_event_v1`/`run_artifact_v1` unter einem Builder) tragen den Decorator; `_executor_mart_build` in [src/new_nfl/jobs/runner.py](../src/new_nfl/jobs/runner.py) auf 3-Zeilen-Registry-Lookup reduziert (Side-Effect-Import `import new_nfl.mart` + `get_mart_builder(mart_key)(settings)`).
- [src/new_nfl/cli_plugins.py](../src/new_nfl/cli_plugins.py) mit `CliPlugin`-Dataclass (`name`, `register_parser`, `dispatch`) und `register_cli_plugin`; neuer Namespace [src/new_nfl/plugins/](../src/new_nfl/plugins/) als Side-Effect-Heimat; Referenz-Plugin [src/new_nfl/plugins/registry_inspect.py](../src/new_nfl/plugins/registry_inspect.py) bindet `new-nfl registry-list --kind mart`. Strangler-Fig-Migration: die 1461-zeilige monolithische `cli.py` bleibt unverändert — neue Subcommands gehen über die Plugin-Registry, bestehende 50+ bleiben im Monolith.
- **Web-Route-Registry deferred**: Scope-Reality-Check während der Umsetzung hat ergeben, dass `web_server.py` eine lokale Core-Dictionary-Preview ist, die Jinja-`render_*_page`-Funktionen reine Library-API ohne HTTP-Mount sind — es existiert schlicht kein Router, den man registry-fähig machen könnte. Deferral in ADR-0033 dokumentiert (wird bei nächstem echten Router-Landing — voraussichtlich T2.6I oder T2.9 — nachgeholt).
- [tests/test_registry.py](../tests/test_registry.py) mit 9 Smoke-Tests (alle 14 erwarteten mart_keys via frozenset-Vergleich; unknown-key→`ValueError`; duplicate-registration→`ValueError`; idempotent-self-reregistration→returns existing; CLI-Plugin-Listing; CLI-Plugin-Duplicate; CLI-Plugin-Idempotenz; argparse-Round-Trip; end-to-end-dispatch mit stdout-Capture).

**DoD:** Erfüllt — Full-Suite **332/332 grün** (323 Baseline + 9 neu, 656.48s); Ruff sauber auf allen T2.7P-scope Files; ADR-0033 Status `Accepted (2026-04-23)`; Push nach `main` mit drei `feature/t27-*`-Branches vom neuen HEAD angelegt.

**Tatsächlich:** 1 Claude-Code-Session, 1 Tag (davon ~60% Dekorator-Batch-Edit + Ruff-Cleanup, ~20% CLI-Strangler-Fig-Design, ~20% Scope-Reality-Check auf Web-Router-Registry).

### T2.7A — Health-Endpunkte (KW 25, Stream A) ✅ (2026-04-23)

CLI `new-nfl health-probe --kind <live|ready|freshness|deps>` mit kanonischem JSON-Envelope `{schema_version:"1.0", checked_at, status, details}` und Shell-Exit-Codes `0=ok / 1=warn / 2=fail`. Kinds: `live` (PID, ohne DB, immer ok), `ready` (DB-Connect + `mart.freshness_overview_v1`-Presence), `freshness` (JSON-Spiegel von `build_home_overview()`, ADR-0029), `deps` (pro Primary-Slice letzte `meta.load_events`-Zeit). Aggregations-Policy: Severity-Ladder `ok=0<stale=1<warn=2<fail=3`, `stale` kollabiert zu `warn` (verhindert falsches Grün beim Cold-Start). HTTP-Mirror Phase 2 deferred bis echter Web-Router landet.

**Artefakte:** [src/new_nfl/plugins/health.py](../src/new_nfl/plugins/health.py), [tests/test_health.py](../tests/test_health.py) (16 Tests). Merge-Commit: `1eee163`.

### T2.7B — Strukturiertes Logging (KW 25, Stream A) ✅ (2026-04-23)

JSON-Line-Logger `new_nfl.observability.logging.get_logger(settings)` mit Pflicht-Envelope `{event_id(uuid4), ts(ISO-8601 UTC ms), level, msg, details}` und optionalen Kontext-Feldern `adapter_id`, `source_file_id`, `job_run_id`. Konfiguration nur über Settings-Properties `log_level` (Env `NEW_NFL_LOG_LEVEL`, default `INFO`) und `log_destination` (Env `NEW_NFL_LOG_DESTINATION`, `stdout`|`file:<dir>`; file-Destination schreibt `events_YYYYMMDD.jsonl`). Runner-Hook: je `_executor_*` (fetch_remote, stage_load, custom, mart_build) genau ein `executor_start` + `executor_complete`-Event.

**Artefakte:** [src/new_nfl/observability/logging.py](../src/new_nfl/observability/logging.py), Runner-Hooks in [src/new_nfl/jobs/runner.py](../src/new_nfl/jobs/runner.py), [tests/test_logging.py](../tests/test_logging.py) (12 Tests). Merge-Commit: `1eee163`.

### T2.7C — Backup-Drill (KW 25, Stream B) ✅ (2026-04-23)

CLI `new-nfl backup-snapshot|restore-snapshot|verify-snapshot`. `backup_snapshot(settings, target_zip)` baut verifizierbares ZIP aus DuckDB (CHECKPOINT) + `data/raw/`-Baum + `manifest.json`. `restore_snapshot(source_zip, target_dir)` extrahiert mit SHA-256-Verify und blockt Pfad-Traversal. `verify_snapshot(source_zip)` macht on-the-fly-Hash ohne Extract. `manifest.payload_hash` hasht nur `schema_version` + `db_filename` + `file_hashes(sorted)` + `row_counts(sorted)` — explizit ohne `created_at`/`duckdb_version`, damit identische Eingaben deterministisch denselben Hash produzieren. Additive Settings-Property `backup_destination_dir = data_root/"backups"` als Vorbereitung für Scheduler-Jobs.

**Artefakte:** [src/new_nfl/resilience/backup.py](../src/new_nfl/resilience/backup.py), `restore.py`, `verify.py`, [src/new_nfl/plugins/resilience.py](../src/new_nfl/plugins/resilience.py), Tests `test_backup.py` (14) + `test_restore.py` (8). Merge-Commit: `a7575dc`.

### T2.7D — Replay-Drill (KW 25, Stream B) ✅ (2026-04-23)

CLI `new-nfl replay-domain --domain <d> [--source-file-id ID] [--dry-run]`. `diff_tables(con_a, con_b, table, key_cols, exclude_cols=...)` liefert `TableDiff(only_in_a, only_in_b, changed)`. `replay_domain(settings, domain, source_file_id=None, dry_run=False)` macht snapshot+rerun+diff für sechs Kerndomains (team/game/player/roster_membership/team_stats_weekly/player_stats_weekly). pytz-frei gelöst: `_copy_table_to_snapshot` nutzt pure-SQL `ATTACH live_db AS src (READ_ONLY); CREATE TABLE … AS SELECT * FROM src.…; DETACH src` statt Python-Fetch; `_fetch_rows` castet TIMESTAMPTZ-Spalten on-the-fly zu VARCHAR. `test_replay_on_unchanged_raw_has_empty_diff` ist das Kern-Gate — wenn je failed, ist es ein Determinismus-Bug im Core-Load.

**Artefakte:** [src/new_nfl/resilience/replay.py](../src/new_nfl/resilience/replay.py), `diff.py`, Tests `test_diff.py` (9) + `test_replay.py` (6). Merge-Commit: `a7575dc`.

### T2.7E — Hardening-Backlog (KW 26, Stream C) ✅ (2026-04-23)

Abarbeitung der fünf dokumentierten Backlog-Punkte aus T2.5C/F und T2.6H Lessons Learned:

- **T2.7E-1 Event-Retention:** CLI `new-nfl trim-run-events --older-than 30d [--dry-run]` + `meta.retention` Backend, löscht abgeschlossene alte Runs mit zugehörigen Events und Artefakt-Referenzen (16 Tests).
- **T2.7E-2 Schema-DESCRIBE-Cache:** [src/new_nfl/meta/schema_cache.py](../src/new_nfl/meta/schema_cache.py) als TTL-Cache über `id(settings)`-Key, API `.describe(con, qualified_table) / .column_names(...)` als drop-in-Ersatz. 9 Mart-Module per reinem Textersatz auf den Cache migriert; `CREATE OR REPLACE TABLE` + Column-Set-Semantik sichert bit-identischen Rebuild. Additive Settings-Property `schema_cache_ttl_seconds` (Env `NEW_NFL_SCHEMA_CACHE_TTL_SECONDS`, default 300s, `0` deaktiviert Caching). (11 Tests.)
- **T2.7E-3 Ontology-Auto-Aktivierung:** `bootstrap_local_environment` lädt automatisch `ontology/v0_1` + aktiviert, wenn keine aktive Version existiert; Opt-out via `NEW_NFL_SKIP_ONTOLOGY_AUTOLOAD=1`. Behebt den dreiwertigen `position_is_known`-Bug in `mart.player_overview_v1` auf Fresh-DB. (6 Tests.)
- **T2.7E-4 `meta.adapter_slice`-Runtime-Projektion:** `SLICE_REGISTRY` wird beim Bootstrap in `meta.adapter_slice`-Tabelle projiziert; CLI `new-nfl adapter-slice-sync` für manuelles Resync; UI/CLI können Slice-Metadaten ohne Python-Import lesen. (6 Tests.)
- **T2.7E-5 `dedupe-review-resolve`:** CLI `new-nfl dedupe-review-resolve --review-id … --action {merge,reject,defer}` + `review.resolve_…()`-Service zum Auflösen offener Review-Items. (9 Tests.)

**Artefakte:** neuer Namespace [src/new_nfl/meta/](../src/new_nfl/meta/), [src/new_nfl/plugins/hardening.py](../src/new_nfl/plugins/hardening.py), Bootstrap-Hooks in [src/new_nfl/bootstrap.py](../src/new_nfl/bootstrap.py), `resolve()`-Extension in [src/new_nfl/dedupe/review.py](../src/new_nfl/dedupe/review.py). Merge-Commit: `1cada42`.

### T2.7F — Integrations-Session (KW 26, sequenziell, zum Abschluss) ✅ (2026-04-23)

**Ergebnis:** drei Feature-Streams (A Observability, B Resilience, C Hardening) in `main` integriert, Merge-Reihenfolge A → B → C nach aufsteigendem Risiko. Merge-Commits `1eee163` (A) → `a7575dc` (B) → `1cada42` (C). Gates pro Merge: Tests hart (332 → 360 → 397 → 445), Ruff-Delta 0 gegenüber pre-existing Baseline-45 (UP035/UP037/E501/I001/B905/UP012/E741 — rule-drift aus Ruff 0.15.10, keine neue Regression aus den Merges). Konflikt-Erwartung war erfüllt: pro Merge genau zwei triviale Union-Konflikte in [src/new_nfl/plugins/__init__.py](../src/new_nfl/plugins/__init__.py) (Registry-Import-Liste) und [src/new_nfl/settings.py](../src/new_nfl/settings.py) (additive `@property`-Block), beide alphabetisch resolved. Finale Suite: **445 passed in 551.69s (9:11)** — exakt Baseline 332 + Stream A 28 + Stream B 37 + Stream C 48.

**Lessons-Konsolidierung:** Drei Stream-Drafts (`docs/_handoff/lessons_t27a.md`, `lessons_t27b.md`, `lessons_t27c.md`) zu einem kanonischen Eintrag in [docs/LESSONS_LEARNED.md](LESSONS_LEARNED.md) verschmolzen; Kern-Lesson: Registry-Pattern hält unter echter Parallelität, Shared-Workdir ist die eigentliche Kostenstelle — künftige parallele Tranchen starten mit `git worktree add`, nicht Branch-Flips.

**Pflichtpfade nach T2.7:** Health + Logging + Backup + Replay + alle fünf Hardening-Punkte live in `main`. ADR-0033 `Accepted` seit T2.7P; ADR-0030 (UI-Stack) weiterhin `Proposed` — Status-Flip auf T2.8-Handoff verschoben, weil T2.7F den UI-Stack nicht berührt hat. ADR-0032 (bitemporale Rosters) weiterhin `Proposed` bis Operator-Validation mit echten Daten (T2.5D-Folge-Bolt). Registry-Pattern etabliert und für T3.0 wiederverwendbar.

## 7. T2.8 — v1.0 Cut auf DEV-LAPTOP ✅ (abgeschlossen 2026-04-24)

**Ergebnis:** Rein dokumentarischer Cut — kein Code berührt gegenüber T2.7F-Integration (`50d2652`) + T2.7-Retro-Doc (`bcc5cc3`). Git-Tag `v1.0.0-laptop` auf `main` gesetzt. Release-Evidence in [docs/_ops/releases/v1.0.0-laptop.md](_ops/releases/v1.0.0-laptop.md) gemäß RELEASE_PROCESS.md §5 (Zweck, Definition-v1.0-Matrix, betroffene Dateien, Gates, bekannte Restrisiken, nächster Schritt, Referenzen, Artefakt-Manifest).

**Definition-v1.0-Matrix (USE_CASE_VALIDATION_v0_1.md §2.3):**
- ✅ Alle Phase-1-Datendomänen geladen: 6 Core-Domänen (`core.team`, `core.game`, `core.player`, `core.roster_membership`, `core.team_stats_weekly`, `core.player_stats_weekly`) über 14 Slices (7 primary + 7 cross-check).
- ✅ Web-UI liefert alle Pflicht-Views aus §5.4: Home/Freshness, Seasons/Weeks/Games-Drilldown, Teams, Players, Game-Detail Pre/Post, Provenance, Runs — 10 UI-Views insgesamt.
- ✅ Scheduler autonom mit Retry/Quarantäne: Internal Runner (T2.3B), Quarantäne-Domäne (T2.3C), CLI `run-worker --once|--serve`.
- ✅ Run-Evidence + Provenance vollständig: `mart.run_overview_v1`/`run_event_v1`/`run_artifact_v1` (T2.6H) + `mart.provenance_v1` (T2.6G).
- ⚠️ Backup/Restore + Replay infrastruktur-seitig erfüllt: 37 Tests inkl. Determinismus-Gate. **Operator-Validation gegen echte Produktions-Load bewusst nach T3.0 verschoben.**

**Gates:** 445 Tests grün (551.69s), Ruff-Delta 0 gegenüber Baseline-45 (Rule-Drift aus Ruff 0.15.10), AST-Lint `test_read_modules_do_not_reference_core_or_stg_directly` grün (ADR-0029-Invariante). Kein Operator-Smoke gegen Produktions-DB (T3.0), kein VPS-Smoke (T3.1), kein Backfill-Lasttest (T3.0).

**Bekannte Restrisiken:** ADR-0030 (UI-Stack) und ADR-0032 (Bitemporale Rosters) bleiben `Proposed` bis T3.0-Feedback; Ruff-Baseline 45 Rule-Drift-Errors; Backup fehlt als Runner-Job (CLI-only); HTTP-Mirror für Health-Probes deferred; `events_YYYYMMDD.jsonl` ohne Retention; `replay-domain --all` fehlt.

**Wichtig:** v1.0 läuft auf DEV-LAPTOP. **Kein** VPS-Deploy in T2.8 — VPS-Migration bleibt T3.1.

## 8. ADR-Block (begleitend zu T2.3)

| ADR | Titel | Kopplung |
|---|---|---|
| ADR-0025 | Internal job and run model in DuckDB metadata | T2.3A/B |
| ADR-0026 | Ontology-as-code with runtime projection | T2.4A |
| ADR-0027 | Dedupe pipeline as explicit stage | T2.4B |
| ADR-0028 | Quarantine as first-class domain | T2.3C |
| ADR-0029 | Read-model separation (`mart.*` only for UI/API) | T2.3D |
| ADR-0030 | UI tech stack: Jinja + Tailwind + htmx + Plot | T2.6A |
| ADR-0031 | Adapter-Slice-Strategie (ein Adapter, N Slices via Code-Registry) | T2.5A / T2.5B (Accepted) |
| ADR-0032 | Bitemporale Roster-Modellierung (valid_from_week / valid_to_week + System-Time) | T2.5D (Proposed) |
| ADR-0033 | Registry-Pattern für Mart-Builder + CLI-Subcommands (Web-Routen deferred) | T2.7P (Accepted 2026-04-23) |

ADR-Stubs werden zusammen mit diesem Plan ausgeliefert, „Accepted" wird mit Abschluss der jeweils gekoppelten Tranche gesetzt.

## 9. T3.0 — Testphase auf VPS (ab Juli 2026, Laufzeit ~4 Wochen)

**Reihenfolge-Hinweis:** T3.0 läuft **nach T3.1**, nicht davor. Siehe [ADR-0034](adr/ADR-0034-vps-first-before-testphase.md). Grund: DEV-LAPTOP läuft nicht always-on, ein 4-Wochen-Scheduler-Test ist dort nicht sauber nachweisbar.

**Zweck:** v1.0-Infrastruktur unter echter Operator-Last auf der Ziel-Umgebung (VPS) validieren. Ziel ist, die drei noch offenen Punkte aus dem v1.0-Cut zu schließen (ADR-0030-Flip, ADR-0032-Flip, 5. Definition-Kriterium Backup/Restore-Operator-Validation) und vier Wochen ununterbrochenen Scheduler-Lauf ohne ungelöste Quarantäne-Eskalation nachzuweisen.

**Vorbedingung:** T3.1 abgeschlossen — NEW NFL läuft auf dem Contabo-VPS unter `C:\newNFL`, Tailscale-erreichbar, `backup-snapshot` mechanisch einmal erfolgreich. Tag `v1.0.0-laptop` auf `main` (erfüllt seit 2026-04-24). Release-Evidence unter [docs/_ops/releases/v1.0.0-laptop.md](_ops/releases/v1.0.0-laptop.md).

### T3.0A — Tägliche Scheduler-Automation auf VPS (Woche 1)
- **Ziel:** `new-nfl run-worker --serve` läuft als `NewNFL-Worker`-Scheduled-Task auf dem VPS mit Auto-Restart-Policy.
- **Artefakte:** `deploy\windows-vps\vps_install_tasks.ps1` (idempotent, analog zu `capsule`-Muster) legt `NewNFL-Worker` sowie `NewNFL-Fetch-<slice>` für alle sieben Primary-Slices mit Daily-Trigger plus `NewNFL-Backup-Daily` an. Log-Destination `C:\newNFL\data\logs\` (T2.7B). Backup-Ablage `C:\newNFL-Backups\`. Task-Definitionen dokumentiert unter `docs/_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md`.
- **DoD:** Drei Tage stabiler Tick-Stream mit sichtbarem `executor_complete`-Event-Stream im JSONL-Log, `last_event_at`-Ticks im Home-Freshness-Dashboard (via Tailscale) und mindestens ein erfolgreicher `backup-snapshot`-Lauf pro Kalendertag.

### T3.0B — ADR-0032 Operator-Validation (Woche 1–2, parallel)
- **Ziel:** Bitemporale Roster-Modellierung gegen echte NFL-Saison (z. B. 2023 oder 2024 mit bekannten Trades/Releases) durchspielen.
- **Artefakte:** Test-Lauf-Protokoll: erwartete vs. beobachtete Events (`signed`/`released`/`trade`/`promoted`/`demoted`), insbesondere für bekannte Mid-Season-Trades; Operator-Befund zu Trade-Heuristik (konservativ: zusammenhängende Woche mit Team-Wechsel → `trade`, Lücke → `released`+`signed`); ADR-0032-Update auf `Accepted` mit Nachweis-Log.
- **DoD:** Mindestens fünf reale Mid-Season-Trades werden korrekt als `trade`-Event erkannt, keine falschen `released`+`signed`-Paare; `mart.roster_history_v1` zeigt lückenlose Intervalle.

### T3.0C — ADR-0030 Re-Review (Woche 2, parallel)
- **Ziel:** UI-Stack (Jinja + Tailwind-Subset + htmx + Plot) gegen realen Lasttest-Eindruck bewerten.
- **Artefakte:** Operator-Befund zu Render-Latenzen bei gewachsener DB, Theme-Toggle-Stabilität, Pagination-Verhalten auf Listenseiten mit echten Row-Counts; Entscheidung Flip `Accepted` oder gezielte Nachbesserung (z. B. Cache-Header, Static-Asset-Kompression, Pagination-Defaults).
- **DoD:** Entweder ADR-0030 auf `Accepted` geflippt, oder konkrete T3.0-Folge-Arbeitspakete benannt.

### T3.0D — Designed Degradation (Woche 2–3)
- **Ziel:** Resilience-Infrastruktur (Retry-Policy, Quarantäne-Auto-Hook) gegen bewusste Quell-Ausfälle testen.
- **Szenarien:** HTTP 5xx für 30 Minuten, HTTP-Timeout, leeres ZIP im `nflverse_bulk`-Endpoint, Schema-Drift (eine Spalte fehlt in einer Parquet-Datei), DuckDB-Connect-Fehler während `core-load`.
- **DoD:** Pro Szenario: Quarantäne-Case öffnet mit passendem `reason_code`, Replay nach manueller Auflösung reproduziert deterministisch, `mart.run_overview_v1` zeigt `retrying`-Status und abschließendes `failed`/`success`.

### T3.0E — Backfill-Lasttest ~15 Saisons (Woche 3)
- **Ziel:** System-Performance unter 15 Saisons × 32 Teams × 22 Wochen Rohdaten messen.
- **Artefakte:** Zeitmessung pro `core-load` über alle Primary-Slices vor/nach Backfill; DuckDB-File-Größe; Schema-Cache-Hit-Rate (T2.7E-2); UI-Render-Zeit auf Home/Teams/Seasons-Views.
- **DoD:** Kein `mart-rebuild` dauert länger als 60s; DuckDB bleibt unter 5 GB; UI-Views rendern unter 500ms.

### T3.0F — Backup/Restore-Drill real (Woche 3)
- **Ziel:** 5. Definition-v1.0-Kriterium aus `USE_CASE_VALIDATION_v0_1.md §2.3` von ⚠️ auf ✅ aufwerten.
- **Szenario:** `backup-snapshot` auf gewachsener DB → ZIP-Integrität per `verify-snapshot` bestätigen → DuckDB-File vollständig löschen → `restore-snapshot` → Pflichtpfad-Suite (Home-Freshness-View rendert, Runs-View zeigt letzte Ticks) verifizieren.
- **DoD:** Restore-zu-Restore-fähig, Payload-Hash deterministisch reproduzierbar, alle 10 UI-Views und sechs Core-Domänen nach Restore konsistent.

### T3.0G — Ruff-Baseline-Cleanup (Woche 4, optional)
- **Ziel:** 45 pre-existing Ruff-Rule-Drift-Errors (UP035/UP037/E501/I001/B905/UP012/E741) abbauen, wenn Testphase ruhig läuft.
- **Nicht Pflicht:** Gate bleibt „Delta 0 gegenüber Baseline"; Cleanup ist Bonus-Arbeit, nicht T3.0-Blocker.

### T3.0H+ — Bugfix-Tranchen nach Bedarf
- **Ad hoc** während der vier Wochen: ungeplante Bugs kriegen jeweils eigenen T3.0H/I/J-Bolt mit Mini-Scope, eigenem Test-Gate und Mini-Lesson-Learned-Eintrag.

**T3.0-DoD (gesamt):**
- 4 Wochen ununterbrochener Scheduler-Lauf ohne ungelöste Quarantäne-Eskalation
- ADR-0030 auf `Accepted` (oder benannte Nachbesserung)
- ADR-0032 auf `Accepted` (oder benannte Nachbesserung)
- 5. v1.0-Kriterium auf ✅ (Backup/Restore-Operator-Validation abgeschlossen)
- Full-Suite weiterhin grün, Ruff-Delta weiterhin 0 gegenüber Baseline

## 10. T3.1 — VPS-Migration (Juni-Ende / Anfang Juli 2026, **vor T3.0**) — final 2026-04-25

**Reihenfolge-Hinweis:** T3.1 ist gegenüber dem Original-Plan **vorgezogen** und läuft vor T3.0. Siehe [ADR-0034](adr/ADR-0034-vps-first-before-testphase.md).

**Zielumgebung:** Contabo-Windows-VPS, der bereits für das `capsule`-Projekt produktiv ist. Tailscale-RDP, Windows-Hardening und `cloudflared`-Service sind auf dem Gerät bereits aufgesetzt — NEW NFL benutzt Tailscale mit, verzichtet aber bewusst auf Cloudflare (Single-Operator-Setup, kein öffentlicher Zugriff nötig).

**Artefakte (neu in diesem Repo, im Rahmen von T3.1 anzulegen):**
- [docs/_ops/vps/VPS_DOSSIER.md](_ops/vps/VPS_DOSSIER.md) — NEW-NFL-spezifische VPS-Konventionen (Pfad, Port, Task-Präfix, Backup-Ablage, Tailscale-Erreichbarkeit). Referenziert die `capsule`-Runbooks für VPS-Grundausbau statt sie zu duplizieren.
- [docs/_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md](_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md) — Schritt-für-Schritt-Anweisungen mit Gerät-/User-/Shell-Prefix (`DEV-LAPTOP $`, `VPS-ADMIN PS>`).
- `deploy\windows-vps\vps_bootstrap.ps1` — klont Repo nach `C:\newNFL`, legt Venv an, `pip install -e .`, legt `C:\newNFL-Backups\` und `C:\newNFL\data\logs\` an.
- `deploy\windows-vps\vps_install_tasks.ps1` — Scheduled Tasks mit `NewNFL-*`-Präfix.
- `deploy\windows-vps\vps_smoke_test.ps1` — erster End-to-End-Smoke auf VPS.
- `deploy\windows-vps\vps_update_from_git.ps1` — idempotenter Update-Pfad (analog zu `capsule`-Muster).

**Betriebs-Entscheidungen (NEW-NFL-spezifisch):**
- **Repo-Pfad:** `C:\newNFL` (kurz, analog zu `capsule`). Daten und Logs unter `C:\newNFL\data\…` — gleiche Struktur wie auf DEV-LAPTOP für Migrations-Parität.
- **Backend-Port:** `8001` (capsule belegt `8000`). Bindung auf `127.0.0.1:8001`, Erreichbarkeit ausschließlich über Tailscale-IP.
- **Öffentlicher Zugriff:** bewusst **nicht** vorgesehen. Kein Cloudflare-Tunnel-Eintrag, keine Subdomain, kein Cloudflare-Access. Wenn später gewünscht, über zusätzlichen Tunnel oder Route nachrüstbar ohne Architektur-Änderung.
- **Scheduled-Task-Präfix:** `NewNFL-*` — getrennt vom `Capsule-*`-Namensraum.
- **Backup-Ablage:** `C:\newNFL-Backups\` lokal auf VPS. Offsite-Sync (Tailnet → DEV-LAPTOP) als Folgearbeit, nicht T3.1-Blocker.
- **Python-Venv:** `C:\newNFL\.venv`, kein globales Python. Version wird bei VPS-Inventarisierung festgelegt (mind. Python 3.11 wegen `tomllib`/`Self`-Typ aus ADR-0026).

**Pflichtpfade (DoD T3.1):**
- Tailscale-RDP validiert vor Beginn (aus `capsule`-Setup bereits erfüllt).
- Repo-Sync, Venv, `pip install -e .` erfolgreich; `new-nfl --help` gibt die erwartete Subcommand-Liste (inklusive Plugin-Registry-Commands aus ADR-0033).
- DuckDB-Migration: frische `new_nfl.db` auf VPS via `bootstrap_local_environment`; alle sechs Core-Domänen einmal mit `core-load` gefüllt; `mart-rebuild --all` grün; `backup-snapshot` + `verify-snapshot` + `restore-snapshot` einmal End-to-End validiert.
- Smoke über Tailscale-IP: `http://<tailscale-ip>:8001/` rendert Home-Dashboard, eine Game-Detail-Seite und `/health/*`-Probe; alle 10 Pflicht-Views aus USE_CASE_VALIDATION_v0_1.md §5.4 erreichbar.
- Full-Suite (`pytest -v`) läuft auf dem VPS grün — gleiche 445 Tests in vergleichbarer Zeit (VPS darf langsamer sein, aber keine Test-Regressionen).

**DoD:**
- 24-Stunden-Smoke-Lauf auf VPS ohne Quarantäne-Eskalation (ersetzt den entfallenen 7-Tage-Parallel-Lauf mit DEV-LAPTOP).
- Backup-Mechanik einmal manuell vollständig durchgespielt (Snapshot → verify → Löschen → Restore → Views grün).
- VPS ist ab diesem Zeitpunkt die **Source of Truth** für NEW-NFL-Runtime; DEV-LAPTOP wird Dev-only.

**Fortschritt (Stand 2026-04-25):**
- ✅ VPS-Bootstrap abgeschlossen: Repo unter `C:\newNFL`, Venv mit Python 3.12, 445 Tests grün auf VPS in 13:05.
- ✅ `seed-sources`-Bug in Bootstrap entdeckt und gefixt (Commit `25561f9`).
- ✅ URL-Drift-Fix für 7 Primary-Slices (Commit `f0e8d13`, siehe §10.1).
- ✅ Scheduled Tasks Step 1 installiert: `NewNFL-Backup-Daily` (04:00), `NewNFL-Fetch-Teams` (05:00). `Fetch-Teams` einmal manuell getriggert, `LastTaskResult=0`.
- ✅ Slice-Smoke nach Step 1: 4 von 7 Primary-Slices end-to-end grün (teams, games, schedule_field_dictionary, player_stats_weekly).
- ✅ **T3.1S Schema-Drift-Fix abgeschlossen (2026-04-25):** zentrale Column-Alias-Registry + Helper, drei Loader-Edits, 12 neue Unit-Tests, 8 neue Network-Smokes als `@pytest.mark.network`. Full-Suite **474 grün** (462 + 12), 8 deselected. Ruff Delta -1 vs Baseline 45. Siehe §10.1.
- ⏳ Operator-Re-Smoke auf VPS für `players`, `rosters`, `team_stats_weekly` mit T3.1S-Code (`run_slice.ps1 -Slice <key> -Season 2024`). Bestätigt T3.1S-DoD und triggert Lesson-Flip auf `accepted`.
- ⏳ Step 2 iterativer Rollout (restliche 6 Fetch-Tasks) — nach Operator-Re-Smoke.
- ⏳ Backup-Task-Manual-Smoke steht aus (Task selbst nie getriggert — `LastTaskResult=267011` = "not yet run"; Trigger 04:00 oder manuell via `Start-ScheduledTask -TaskName NewNFL-Backup-Daily`).

### 10.1 T3.1S — Core-Loader-Schema-Drift-Fix (Schema-Alias-Strategie) ✅

**Ziel:** die drei per-season-Slices, die am Core-Load-Gate hängen, endgültig grün bekommen. Rest-Blocker für die Aufnahme der restlichen 6 Fetch-Tasks (Step 2 des iterativen Rollouts) und damit für den T3.1-Abschluss.

**Status:** ✅ Code + Tests abgeschlossen 2026-04-25. Operator-Re-Smoke auf VPS steht aus (DoD-Punkt 1 unten).

**Entschieden:** Operator hat 2026-04-25 **Option B** (zentrale Column-Alias-Registry) freigegeben. Begründung: Single-Point-of-Truth, drei Loader bleiben konsistent, zukünftige Drifts kosten nur einen Registry-Eintrag.

**Geliefert:**
- [src/new_nfl/adapters/column_aliases.py](../src/new_nfl/adapters/column_aliases.py) — `ALIAS_REGISTRY` als dict `slice_key -> {upstream: canonical}` plus Helper `apply_column_aliases(con, qualified_table, slice_key)`. Idempotentes `ALTER TABLE ... RENAME COLUMN` mit case-insensitivem Match und Original-Case-Preservation. Defensiv bei fehlender Tabelle (no-op statt Exception) — wichtig für Cross-Check-Stages, die im fresh-DB-Fall nicht existieren.
- Registry-Inhalt: `players` → `gsis_id`/`player_id`; `rosters` → `gsis_id`/`player_id` + `team`/`team_id`; `team_stats_weekly` → `team`/`team_id`. `core/player_stats.py` ist nicht in der Registry — der Loader akzeptiert `team` bereits seit v1.0 (inline `_opt('team_id', ...)`-Pfad) und `player_id` ist im aktuellen File vorhanden.
- [src/new_nfl/core/players.py](../src/new_nfl/core/players.py), [src/new_nfl/core/rosters.py](../src/new_nfl/core/rosters.py), [src/new_nfl/core/team_stats.py](../src/new_nfl/core/team_stats.py) rufen `apply_column_aliases` vor `_assert_required_columns` auf — sowohl auf primary.stage_qualified_table als auch in einer Schleife auf jede cross_check.stage_qualified_table. Helper-Aufruf ist 2 Zeilen pro Loader; gesamter SQL-Code unverändert.
- pytest-Marker `network` registriert in [pyproject.toml](../pyproject.toml) via `markers = [ ... ]`; default-Run filtert via `addopts = -q -m 'not network'`. Network-Smokes sind opt-in über `pytest -m network`.
- 12 neue Unit-Tests in [tests/test_column_aliases.py](../tests/test_column_aliases.py): Registry-Shape pinnt die drei betroffenen Slices, `get_aliases_for_slice` Copy-Semantik, Helper-Verhalten (Rename, Idempotenz, fehlende Tabelle, kanonische Spalte schon vorhanden, unknown slice, case-insensitive `GSIS_ID` → `player_id`), drei End-to-End-Tests (jeder betroffene Loader läuft `execute=True` durch mit nflverse-Schema-Stage).
- 8 Network-Smokes in [tests/test_slices_network_smoke.py](../tests/test_slices_network_smoke.py): 7 parametrierte Probes über die Primary-Slices (4 statisch + 3 per-season auf `PINNED_SMOKE_SEASON=2024`) plus 1 Coverage-Test (Registry-Drift-Detect — fängt den Fall, dass eine künftige Slice ohne Smoke-Update hinzugefügt wird). HEAD-Probe mit GET-Fallback bei 405; CSV-Header-Heuristik (`,` in erster Zeile) als Sanity gegen 200-HTML-Error-Pages.

**DoD-Tracking:**
- ✅ Full-Suite **474 grün** (462 + 12 neue), 8 deselected (= 8 network smokes), in ~9:57 auf DEV-LAPTOP. Ruff Delta -1 gegenüber Baseline 45. AST-Lint grün.
- ✅ Operator-Re-Smoke auf VPS 2026-04-25: `players` (24408 rows, 0 invalid), `rosters` (10861 intervals aus 46579 source, 167 open, 234 trades), `team_stats_weekly` (570 rows, 32 season-aggregates) — alle drei `=== DONE ===`. Damit alle 7 Primary-Slices end-to-end grün auf VPS.
- ✅ 2026-04-24-Lesson auf `accepted` geflippt + T3.1S-Befund mit DoD-Beleg angehängt.

### 10.2 T3.1 Step 2 — restliche Fetch-Tasks (nach T3.1S)

**Status:** Code + Tests abgeschlossen 2026-04-25. Operator-Trigger auf VPS + 2 Tage Beobachtung sind die T3.1-final-Closer.

**Geliefert:**
- [deploy/windows-vps/vps_install_tasks_step2.ps1](../deploy/windows-vps/vps_install_tasks_step2.ps1) — neues Skript (statt Step-1-Skript zu erweitern), idempotenter Drop+Re-Register-Pfad pro Task. Sechs Tasks gestaffelt im 15-Minuten-Raster:
  - `05:15 NewNFL-Fetch-Schedule` (statisch, slice `schedule_field_dictionary`)
  - `05:30 NewNFL-Fetch-Games` (statisch, slice `games`)
  - `05:45 NewNFL-Fetch-Players` (statisch, slice `players`)
  - `06:00 NewNFL-Fetch-Rosters` (per-season, slice `rosters`)
  - `06:15 NewNFL-Fetch-TeamStats` (per-season, slice `team_stats_weekly`)
  - `06:30 NewNFL-Fetch-PlayerStats` (per-season, slice `player_stats_weekly`)
- Per-season-Tasks rufen `run_slice.ps1` ohne `-Season`-Parameter auf. Im Python-Pfad triggert das `default_nfl_season(today)` über `SliceSpec.remote_url_template` + `resolve_remote_url(spec, season=None)`. Das vermeidet, das Jahr in PowerShell und Python doppelt zu pflegen.
- 16 neue Tests in [tests/test_deploy_scripts.py](../tests/test_deploy_scripts.py) — statische Validierung aller fünf Deployment-Skripte: ASCII-only-Encoding (PowerShell-5.1-Falle aus 3c15751), keine `&&`/`||`-Pipeline-Chains (PS-5.1-Inkompatibilität), exakte Task-Namen + Trigger-Zeiten + Slice-Keys, kein hartcodiertes `-Season` in den Step-2-Task-Definitionen, idempotenter Re-Register-Pattern, `run_slice.ps1` reicht `--season` nur durch wenn explizit gesetzt.

**Erwartete Gesamt-Belegung nach Step 2 (Step 1 + Step 2):**
- 04:00 NewNFL-Backup-Daily
- 05:00 NewNFL-Fetch-Teams
- 05:15 NewNFL-Fetch-Schedule
- 05:30 NewNFL-Fetch-Games
- 05:45 NewNFL-Fetch-Players
- 06:00 NewNFL-Fetch-Rosters
- 06:15 NewNFL-Fetch-TeamStats
- 06:30 NewNFL-Fetch-PlayerStats

**Operator-Closer 2026-04-25 23:30 — durchgeführt:**
- VPS-Pull auf Commit `5a9e54c` und Skript-Lauf liefen ohne Fehler durch (sechs Tasks idempotent angelegt).
- Manueller Initial-Trigger pro Task (`Start-ScheduledTask -TaskName NewNFL-Fetch-<Slice>`) für alle sechs erfolgreich; jeder Task lief fetch+stage+core durch.
- `Get-ScheduledTask -TaskName NewNFL-* | Get-ScheduledTaskInfo` zeigt für **alle 8 Tasks** (1 Backup + 7 Fetches) `LastTaskResult=0` und nächsten Cron-Tick im erwarteten Slot.
- Backup-Task lief im 04:00-Tick desselben Tages mit `LastTaskResult=0`; zusätzlich manuell getriggert nach dem Step-2-Lauf.

**DoD T3.1 final:**
- ✅ Alle 7 Fetch-Tasks + 1 Backup-Task aktiv mit `LastTaskResult=0` (Operator-Closer 2026-04-25 23:30).
- ⏳ 2-Tage-Beobachtungsfenster läuft 2026-04-25 → 2026-04-27 — kein `meta.run_event` mit `severity in ('error','critical','fatal')` ausserhalb der dokumentierten Edge-Cases (z. B. die 7 invalid roster rows aus 2024).
- ⏳ Backup-End-to-End-Drill (Snapshot → `verify-snapshot` → Test-`restore-snapshot`) einmal durchspielen vor T3.0-Start.

## 11. Risiken und Gegenmaßnahmen

| Risiko | Wirkung | Gegenmaßnahme |
|---|---|---|
| Quellen-API-Änderung mitten in T2.5 | Domain-Tranche verzögert | Adapter-Pattern erlaubt parallelen Fallback-Adapter |
| Dedupe-Härtefälle bei Players blockieren T2.5C | Verzögerung Stats | Review-Queue erlaubt Fortschritt mit offenen Fällen, Qualitätsmarker im UI |
| UI-Stack-Lernkurve (Tailwind/Plot/htmx) | T2.6 verzögert | T2.6A bewusst eine Woche Setup-Puffer |
| VPS-Migration-Probleme | T3.1 verzögert | bereits vorhandenes Runbook + Tailscale-Validierung vorab |
| Wetter-Backfill historisch nicht beschaffbar | Nur Phase-1.5 betroffen | dokumentiert opportunistisch |
| Trade-Heuristik (ADR-0032) erkennt echte NFL-Trades nicht zuverlässig | T3.0B blockiert, ADR-0032-Flip verzögert | Konservativer Fallback `released`+`signed` ist korrekt, `trade`-Fehlklassifikation ist Bonus; Operator kann Einzelfälle manuell bestätigen |
| DuckDB wächst bei Backfill über 5 GB oder `mart-rebuild` > 60s | T3.0E blockiert, Lasttest zeigt Skalierungs-Grenze | Schema-Cache (T2.7E-2) bereits aktiv; Retention (T2.7E-1) für `meta.run_event` aktiv; Emergency: Mart-Partitionierung nach Saison als T3.0-Folge-Arbeit |
| 4-Wochen-Scheduler-Lauf bricht durch Windows-Update-Reboot | T3.0-DoD gefährdet | Auto-Restart-Shim + Health-Probe als Re-Arm-Mechanismus; DoD akzeptiert geplante Reboots wenn Service innerhalb 5min wieder läuft |
| Parallel-Entwicklung im geteilten Working-Tree | Session-übergreifende Überschreibungen, falsche Branch-Commits | Ab nächster paralleler Tranche Pflicht: `git worktree add c:/projekte/newnfl.wt/<stream>` (siehe `PARALLEL_DEVELOPMENT.md` Retro-Block + Memory-Feedback) |

## 12. Verweise

- `PROJECT_STATE.md`
- `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md`
- `ENGINEERING_MANIFEST_v1_3.md`
- `UI_STYLE_GUIDE_v0_1.md`
- `USE_CASE_VALIDATION_v0_1.md` (§2.3 Definition v1.0)
- `RUNBOOK_VPS_PREVIEW_RELEASE.md`
- `RELEASE_PROCESS.md` (§5 Mindestartefakte)
- `PARALLEL_DEVELOPMENT.md` (mit T2.7-Retro-Block + Worktree-Pflicht)
- `_ops/releases/v1.0.0-laptop.md` (v1.0-Cut Release-Evidence)
- `LESSONS_LEARNED.md` (inkl. T2.7-Konsolidierung)
- ADR-0025 bis ADR-0033 (Index unter `adr/README.md`)
