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
| ADR-0031 | Adapter-Slice-Strategie (ein Adapter, N Slices via Code-Registry) | T2.5A / T2.5B (Accepted) |
| ADR-0032 | Bitemporale Roster-Modellierung (valid_from_week / valid_to_week + System-Time) | T2.5D (Proposed) |

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
