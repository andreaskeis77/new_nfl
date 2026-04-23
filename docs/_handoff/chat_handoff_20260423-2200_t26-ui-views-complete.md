# Chat-Handoff 2026-04-23 22:00 — T2.6 vollständig abgeschlossen (alle Pflicht-UI-Views live)

## Trigger

§2.1 „Tranche-Abschluss + thematischer Wechsel zwischen Substreams": **T2.6A–H komplett** (UI-Fundament + sieben Pflicht-Views aus `USE_CASE_VALIDATION_v0_1.md` §5.4). Der letzte Bolzen der Tranche (T2.6H Run-Evidence-Browser) schließt die Lücke: ab sofort ist **jede Pipeline-Evidenz** über die UI erreichbar — Freshness, Seasons/Weeks/Games, Teams, Players, Game-Detail, Provenance und Runs. Der nächste Substream **T2.7 — Resilienz und Observability** ist qualitativ anders (Health-Endpunkte, strukturiertes Logging, Backup-/Replay-Drills, keine neuen Views) und verdient eine eigene Chat-Session.

Zusätzlich §2.1 „Kontext-Druck": Diese Session hat T2.6E → T2.6F → T2.6G → T2.6H in einem Zug ausgeführt (autonomer Modus). Vier UI-Views, vier neue Mart-Projektionen (player_profile-Aggregate bereits da, game_detail-Bundle, `mart.provenance_v1`, drei `mart.run_*`-Projektionen unter einem Mart-Key), +71 Testcases (252 → 323), vier Lessons-Learned-Drafts. Vor der Observability-Tranche ist ein sauberer Cut sinnvoll.

## Was wurde in dieser Session erreicht

### T2.6E — Player-Profil (Commit `3d0e32f`, doc `e6b2c7a` — aus vorheriger Teil-Session)
- Read-Service [src/new_nfl/web/player_view.py](../../src/new_nfl/web/player_view.py): `list_players` paginiert mit Team-Join-Fallback, `get_player_profile` case-insensitive über `player_id_lower`, vier Mart-Zugriffe in einem `PlayerProfile`-Bundle (Stammdaten, Karriere-Totale, Saison-Historie, Roster-Intervalle).
- UX-Properties auf Service-Dataclass: `height_label` (inch→ft'in"), `weight_label`, `draft_label`, `seasons_label` (`2017–heute` vs. `2000–2022`), `week_range_label` (`W1–offen` bei is_open=true).
- Templates `players.html`/`player_profile.html` mit `data-testid="player-row"`/`data-player-id`, Pagination mit `data-testid="player-pagination"`.
- 19 neue Tests decken Empty-State je Mart, Ordering, Team-Join-Fallback, Pagination, case-insensitive Lookup, Draft-Label, Open-Intervall, 404.

### T2.6F — Game-Detail Pre/Post (Commit `d4e9f7c`, doc `f5e1c7d`)
- Read-Service [src/new_nfl/web/game_view.py](../../src/new_nfl/web/game_view.py): `get_game_detail` orchestriert vier Marts (game_overview, team_overview, team_stats_weekly, player_stats_weekly) in einem `GameDetail`-Bundle mit Pre/Post-Slots.
- Pre-Game: beide Teams mit `record_label` + avg Points-For/Against aus `team_stats_weekly_v1` `WHERE week < current`.
- Post-Game: finale Score mit `Final` / `Final (OT)`, Wochenzeile je Team, Top-10-Boxscore per `ORDER BY total_yards DESC LIMIT 10`.
- UX-Properties: `score_label` (`27 – 20`), `matchup_label` (`BAL @ KC`), `winner_label` (Name · `Unentschieden` bei TIE · `—` pre-game), `kickoff_label`, `venue_label`.
- Jede Mart-Dependency degradiert unabhängig (fehlendes `team_overview` → Team-Name fällt auf Abbr, fehlendes `team_stats_weekly` → form/week None, fehlendes `player_stats_weekly` → Boxscore leer).
- Template `game_detail.html` mit 404-Karte bei `detail is None`, Breadcrumb `Home › Seasons › Season N › Woche W › {matchup_label}`.
- 13 neue Tests.

### T2.6G — Provenance-Drilldown (Commits `8a01ed0`, `e97f404`)
- Neues Mart [src/new_nfl/mart/provenance.py](../../src/new_nfl/mart/provenance.py) als `mart.provenance_v1` im Grain `(scope_type, scope_ref)`.
- UNION-ALL über sechs Core-Domänen (team, game, player, team_stats_weekly, player_stats_weekly, roster_membership) mit defensivem `_table_exists`-Guard pro Domäne — fresh DB liefert leere Projektion.
- Source-Aggregation per `LIST(DISTINCT …) FILTER (WHERE … IS NOT NULL)` für `source_file_ids`/`source_adapter_ids` (DuckDB array-nativ, kein String-Join-Hack).
- Quarantäne-Aggregation per LEFT-JOIN auf `meta.quarantine_case` mit `COUNT(*) FILTER (WHERE status NOT IN ('resolved','closed','dismissed'))` und `ARG_MAX(reason_code, last_seen_at)` für den jüngsten Case.
- Abgeleiteter `provenance_status` Kaskade: `warn` (offene Cases) · `unknown` (weder Source noch Quarantäne) · sonst `ok`.
- Read-Service [src/new_nfl/web/provenance_view.py](../../src/new_nfl/web/provenance_view.py) mit `list_provenance` (paginiert, Scope-Type-Filter) + `get_provenance` (case-insensitive über beide `*_lower`-Spalten).
- Templates `provenance.html`/`provenance_detail.html` mit Filter-Header und Adapter-Liste.
- Navbar-Eintrag `Provenance` zwischen Players und Runs.
- 16 neue Tests.

### T2.6H — Run-Evidence-Browser (Commits `ec0ae5c`, `10093df`)
- Neues Mart [src/new_nfl/mart/run_evidence.py](../../src/new_nfl/mart/run_evidence.py) mit **einem Builder `build_run_evidence_v1` und drei Read-Projektionen** unter **einem Mart-Key `run_evidence_v1`**:
  - `mart.run_overview_v1` im Grain `job_run_id` — aggregiert `meta.job_run` + `meta.job_definition` + Event-/Artefakt-CTEs mit `event_count`/`error_event_count`/`warn_event_count`/`artifact_count` + abgeleitetem `duration_seconds = EXTRACT(EPOCH FROM (finished_at - started_at))`.
  - `mart.run_event_v1` + `mart.run_artifact_v1` als Passthroughs mit `*_lower`-Shadow-Spalten für case-insensitive Reads.
- Cold-Start-Sicherheit via `_ensure_metadata_tables`-Hook (CREATE TABLE IF NOT EXISTS-Stubs für `meta.job_definition`/`meta.job_run`/`meta.run_event`/`meta.run_artifact`) — idempotent auf leerer DB.
- Read-Service [src/new_nfl/web/run_view.py](../../src/new_nfl/web/run_view.py) mit `list_runs(settings, *, offset, limit, status=None)` (case-insensitive Status-Filter + Pagination im `RunListPage`-Bundle) und `get_run_detail(settings, job_run_id)` (case-insensitive Lookup, lädt Events + Artefakte nur wenn Mart existiert).
- UX-Properties auf `RunSummary`: `status_label` (DE-Mapping `success→OK`, `failed→Fehlgeschlagen`, `running→Läuft`, `pending→Wartend`, `retrying→Wiederholung`, `quarantined→Quarantäne`), `duration_label` (`—` · `<1s` · `{s}s` · `{m}m {s}s` · `{h}h {m}m`), `job_label` (Fallback job_key→job_def_id→`—`), `attempt_label`, `evidence_label` (`N Events · M err · K warn · L Artefakte`).
- Templates `runs.html` (Index mit Status-Badges + Pagination) / `run_detail.html` (Stammdaten + Event-Stream + Artefakte mit Empty-States).
- Runner-Registry kennt `mart_key='run_evidence_v1'` (ein `mart_build`-Job baut alle drei Tabellen gemeinsam).
- 23 neue Tests decken: Builder-Cold-Start, Happy-Runset (3 Runs — success/failed/running — `duration_seconds=42.0`, `error_event_count=3`), idempotent-on-rebuild, list-Empty bei fehlendem Mart, list-Ordering (newest first), Status-Filter case-insensitive, Pagination (`page_range_label='1–2 von 3'`), Duration-Label-Format, Status-Label-DE-Mapping, Evidence-Label-Format, get-Unknown→None, get case-insensitive, get-mit-Events-und-Artefakten (Ordering + ref_label), get-Empty-Streams, Render-Empty-Hint, Render-mit-Rows (Testids + Status-Label), Render-Status-Filter-Breadcrumb, Render-404, Render-Happy, Render-Events-Only, Render-Cold-Start, Runner-Integration, Mart-Table-Präsenz (DESCRIBE).

### Test-Suite
- **323 Tests grün** (von 252 am T2.6E-Start).
- Verteilung der +71 Testcases: T2.6E +19, T2.6F +13, T2.6G +16, T2.6H +23.

### Doku
- `PROJECT_STATE.md` nach jedem Bolzen aktualisiert (Phase-Header, Completed-List, Runtime-Posture, Preferred-Next-Bolt).
- `T2_3_PLAN.md` §5 mit Done-Blöcken für T2.6E/F/G/H (Ziel/Scope/Entscheidungen/DoD).
- `LESSONS_LEARNED.md` — vier neue Drafts (T2.6E/F/G/H) warten auf Operator-Freigabe.

## Aktueller Arbeitsstand

- **Phase:** T2.6 vollständig abgeschlossen, Übergang zu T2.7 (Resilienz und Observability).
- **Letzter erfolgreicher Pflichtpfad:** `pytest` 323/323 grün (Full-Suite-Laufzeit ~9:42).
- **Letzter Commit:** `10093df docs: T2.6H closed + Lessons Learned + next Final-Handoff T2.7` (HEAD `origin/main`).
- **Nächster konkreter Schritt:** **T2.7A — Health-Endpunkte** gemäß `T2_3_PLAN.md` §6: `/livez`, `/readyz`, `/health/deps`, `/health/freshness` mit JSON-Responses.
- **Git-Status:** sauber, alle Commits gepusht nach `origin/main`.

## Was ist offen / unklar / Risiko

### Direkt für T2.7A
- **`/readyz` braucht Retention-Entscheidung für `meta.run_event`:** Die Tabelle wächst linear mit allen `recorded_at`-Events aller Runs. Ein `readyz`-Check, der den Event-Stream liest, muss eine obere Grenze haben. Zwei Optionen: (a) `readyz` liest nur den Overview-Mart (aggregiert, konstante Kosten), (b) explizite Retention in T2.7 via CLI `trim-run-events --older-than 30d`. Operator-Entscheidung empfohlen vor T2.7A-Start.
- **`/health/freshness` ist quasi schon gebaut — nur JSON-Serialisierung fehlt:** `mart.freshness_overview_v1` aus T2.6B liefert die Daten. `/health/freshness` kann als Spiegel von `render_home` ohne HTML gebaut werden. Erste Aktion: Endpunkte-Stub mit `HomeOverview` als JSON-Encoding.
- **Healthz-Endpunkt-Pfad-Konvention:** `/healthz` (Kubernetes-Style, einzelner Endpoint) vs. `/livez`+`/readyz` (getrennt) vs. `/health/*` (Namespace). T2_3_PLAN §6 listet beide (`/livez`, `/readyz`, `/health/deps`, `/health/freshness`) — Inkonsistenz sollte vor Implementierung aufgelöst werden.

### Backlog aus T2.6E–H-Lessons (ungelöst)
- **Ontology-Auto-Aktivierung im Bootstrap**: `position_is_known` in `mart.player_overview_v1` ist NULL-wertig auf fresh DB, weil keine aktive Ontologie-Version geladen ist. T2.6E hat das akzeptiert, aber die Bootstrap-Frage bleibt — möglicherweise T2.7 oder T2.8.
- **Schema-DESCRIBE-Fallback ohne Cache**: Jetzt ~10 Marts rufen pro Rebuild DESCRIBE auf `core.team`/`core.player`. Das skaliert nicht linear mit UI-Requests. Cache-Strategie für `web.renderer` oder pro-Settings-Singleton ist offen.
- **Run-Event-Retention**: siehe oben; T2.7A-Blocker.
- **Quarantäne-Case → Run-Drilldown einseitig**: Ein `meta.quarantine_case` speichert `job_run_id` als String; der UI-Pfad führt vom Run zum Case (Evidence-Label) und vom Scope zum Case (Provenance-Detail), aber ein direkter Link `quarantine_case.job_run_id → /runs/<id>` fehlt im Provenance-Template. Aufnehmbar in T2.7B oder als T2.6I-Mini-Bolzen.
- **`_ensure_metadata_tables` im Builder ist schreibend**: Das Mart-Build-Executor darf `CREATE TABLE IF NOT EXISTS` auf `meta.*`. Ok für Cold-Start, aber die Idempotenz-Logik ist jetzt im Builder, nicht im `bootstrap_local_environment`. Gegensatz-Check: `bootstrap_local_environment` dedupliziert immer. Wenn Bootstrap später verschärft wird, darf der Builder-Stub die Schemata nicht erweitern, sondern nur anlegen.

### Backlog aus T2.5-Lessons (bleibt)
- `meta.adapter_slice` als Runtime-Registry (Slices leben nur im Code).
- Aggregierende Marts ohne expliziten Saison-Filter (Playoff-Trennung via `season_type`).
- Trade-Heuristik konservativ (`released+signed` bei Lücke statt `trade`).

## Starter-Prompt für die nächste Session

> NEW NFL — Fortsetzung nach abgeschlossener Phase T2.6 (sieben UI-Pflicht-Views + UI-Fundament live, 323 Tests grün).
>
> **Kontext:** Stand `origin/main` bei Commit `10093df`, 323 Tests grün, alle sieben Pflicht-Views aus `USE_CASE_VALIDATION_v0_1.md` §5.4 sichtbar (Home/Freshness, Seasons/Weeks/Games, Teams, Players, Game-Detail, Provenance, Runs). Zehn Marts insgesamt. Lessons Learned T2.6E/F/G/H liegen als Drafts vor, warten auf Operator-Freigabe.
>
> **Nächster Bolt:** T2.7A — Health-Endpunkte
> 1. Operator-Entscheidung Pfad-Konvention: `/livez`+`/readyz`+`/health/deps`+`/health/freshness` (getrennt) vs. `/healthz` + `/health/*`-Namespace.
> 2. `/livez` — trivial, immer `200 OK` wenn der Prozess lebt.
> 3. `/readyz` — prüft DB-Connect + aktiv geladene Marts (`mart.freshness_overview_v1` mindestens vorhanden); Kostengrenze: **nur Overview-Marts lesen, nicht Event-Streams**.
> 4. `/health/freshness` — JSON-Spiegel von `render_home`, nutzt `mart.freshness_overview_v1`.
> 5. `/health/deps` — Adapter-Slice-Registry + letzter `meta.load_events`-Timestamp je Adapter.
> 6. Retention-Entscheidung für `meta.run_event` (wenn T2.7A sich sinnvoll nicht davon entkoppeln lässt, als Sub-Bolzen T2.7A.1 aufnehmen).
>
> **Pflichtlektüre vor Beginn:**
> - `docs/PROJECT_STATE.md`
> - `docs/T2_3_PLAN.md` §6
> - `docs/OBSERVABILITY.md`
> - `docs/LESSONS_LEARNED.md` (neueste vier Einträge: T2.6H, T2.6G, T2.6F, T2.6E — alle Status `draft`)
>
> **Qualitätsgates:**
> - `pytest` grün zwischen Bolzen.
> - Keine neuen ruff-Warnungen auf T2.7A-scoped Dateien.
> - AST-Lint-Test (`mart.*`-only in Read-Pfaden) bleibt grün; Health-Endpunkte lesen exklusiv aus `mart.*`, **niemals** aus `meta.*` direkt.
> - Jeder neue Endpunkt liefert JSON mit Content-Type `application/json` und einer stabilen Schema-Version.
>
> **Arbeitsrhythmus:**
> - Pfad-Konvention zuerst entscheiden (Operator-Frage oder pragmatische Default-Entscheidung mit Begründung).
> - `/livez` + `/readyz` in einem Commit.
> - `/health/freshness` + `/health/deps` im zweiten Commit.
> - Doku-Updates (PROJECT_STATE/T2_3_PLAN/LESSONS_LEARNED) im dritten Commit.
> - Push nach jedem Commit.

## Referenzen

- Manifest §2.1 (Chat-Handoff-Trigger), §3.9 (Evidence-first), §3.13 (Evidence-as-Code), §3.7 (ADRs unter Implementierungs-Druck).
- System-Konzept §2 (VPS-Deploy vertagt), §6 (UI-Pfad), §7 (Observability).
- ADR-0029 (Read-Modell-Trennung), ADR-0030 (UI Stack — Accepted seit T2.6A), ADR-0031 (Adapter-Slice-Strategy), ADR-0032 (Bitemporale Roster-Modellierung — Proposed).
- Letzter Handoff: `chat_handoff_20260422-2300_t25f-player-stats-done.md`.
