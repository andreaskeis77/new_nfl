# Chat-Handoff 2026-04-22 15:00 — T2.5C Players-Domäne + erste reale Dedupe-Anwendung abgeschlossen

## Trigger

§2.1 „Tranche-Abschluss + thematischer Wechsel zwischen Substreams": **T2.5C ist vollständig abgeschlossen** (Players-Slice, `core.player`, `mart.player_overview_v1`, erste reale Dedupe-Anwendung gegen live `core.player`, Protocol-Refactor `CoreLoadResultLike`). Der nächste Bolzen **T2.5D — Rosters zeitbezogen** ist qualitativ anders: **erste Domäne mit Bitemporalität** (`valid_from`/`valid_to`), Trade-Erkennung durch Wochenüberschneidung, erste Window-Funktionen — die drei bisherigen Domänen (Teams, Games, Players) waren snapshot-basiert. Das ist ein **Komplexitätssprung**, der eine eigene Chat-Session verdient.

Zusätzlich §2.1 „Kontext-Druck": Diese Session hat T2.5A → T2.5B → T2.5C in einem Zug ausgeführt — drei Domänen-Tranchen, acht Commits, +21 Testcases (136 → 157), die erste reale HTTP-Runde produktiv nachgewiesen, der erste reale Dedupe-Run gegen eine Live-Domäne verifiziert, zwei ADRs neu (ADR-0031 `Proposed` → `Accepted`) plus Protocol-Refactor. Vor dem Eintauchen in die Bitemporalitäts-Frage ist ein sauberer Cut sinnvoll.

## Was wurde in dieser Session erreicht

### T2.5A — Teams-Domäne (Commit `bde4783`)
- Adapter-Slice-Registry [src/new_nfl/adapters/slices.py](../../src/new_nfl/adapters/slices.py) — ein `adapter_id` kann mehrere Slices bedienen.
- `(nflverse_bulk, teams)` Primary, `(official_context_web, teams)` Cross-Check (Fixture-Pfad).
- `core.team` mit Idempotent-Rebuild, Tier-A-Dominanz, Tier-B-Diskrepanzen öffnen pro `team_id` eine aggregierte `meta.quarantine_case`.
- `mart.team_overview_v1` spalten-tolerant.
- Ontologie-Terme `conference` + `division` ergänzt.
- ADR-0031 → `Proposed`.

### T2.5B — Games-Domäne + erste reale HTTP-Runde (Commit `df84ee3`)
- Slices `(nflverse_bulk, games)` + `(official_context_web, games)`.
- `core.game` mit `LOWER(TRIM(game_id))`-Dedupe, Tier-A/B-Konflikt auf Scores + Venue-Metadaten.
- `mart.game_overview_v1` mit abgeleitetem `is_completed` und `winner_team` (`home_team`/`away_team`/`TIE`/NULL).
- Echter HTTP-Roundtrip: stdlib-`ThreadingHTTPServer` + `urllib.request.urlopen` end-to-end, keine neuen Testabhängigkeiten.
- CLI `list-slices` als pipe-separierter Registry-View.
- ADR-0031 → `Accepted`.

### T2.5C — Players-Domäne + erste reale Dedupe + Protocol-Refactor (Commits `446f2ac`, `5ec3e29`)
- Slices `(nflverse_bulk, players)` + `(official_context_web, players)`.
- `core.player` ([src/new_nfl/core/players.py](../../src/new_nfl/core/players.py)) mit `UPPER(TRIM(player_id))`-Kanonicalisierung, TRY_CAST für numerische/Datum-Felder.
- Tier-B-Diskrepanzen auf `display_name`, `position`, `current_team_id`, `jersey_number` öffnen `meta.quarantine_case` mit `scope_type='player'`.
- `mart.player_overview_v1` ([src/new_nfl/mart/player_overview.py](../../src/new_nfl/mart/player_overview.py)) mit `full_name`-Fallback, `is_active = (last_season IS NULL)` und best-effort `position_is_known` gegen die aktive Ontologie-Version (`meta.ontology_value_set_member` für `position`-Term; `NULL` wenn keine aktive Version geladen).
- **Erste echte Dedupe-Anwendung:** [src/new_nfl/dedupe/core_player_source.py](../../src/new_nfl/dedupe/core_player_source.py) projiziert `core.player` in `RawPlayerRecord` mit `EXTRACT(YEAR FROM birth_date)`; CLI `dedupe-run --domain players --source core-player` ersetzt das Demo-Set durch reale Rows. Test verifiziert Auto-Merge-Cluster für zwei Mahomes-Player-IDs.
- **Protocol-Refactor:** `CoreLoadResultLike` ([src/new_nfl/core/result.py](../../src/new_nfl/core/result.py)) als `@runtime_checkable`-Protocol mit elf Kern-Attributen; CLI-Dispatch für Teams/Games/Players kollabiert von drei `isinstance`-Branches auf einen.

### Test-Suite
- **157 Tests grün** (von 136 am Session-Start).
- Neu: `tests/test_teams.py` (5), `tests/test_games.py` (7), `tests/test_players.py` (9).

### Doku
- `PROJECT_STATE.md`, `T2_3_PLAN.md` §4, `LESSONS_LEARNED.md` nach jeder Tranche aktualisiert.
- ADR-0031 final `Accepted` seit T2.5B; Implementierungsnotizen bleiben gepflegt.
- Lessons-Learned-Drafts T2.5A/T2.5B/T2.5C liegen jetzt zur Operator-Freigabe.

## Aktueller Arbeitsstand

- **Phase:** T2.5C abgeschlossen, Übergang zu T2.5D (Rosters zeitbezogen).
- **Letzter erfolgreicher Pflichtpfad:** `pytest` 157/157 grün.
- **Letzter Commit:** `5ec3e29 docs: T2.5C closed + Lessons Learned + next bolt T2.5D` (HEAD `origin/main`).
- **Nächster konkreter Schritt:** **T2.5D — Rosters zeitbezogen** gemäß `T2_3_PLAN.md` §4.
- **Git-Status:** sauber, alle Commits gepusht nach `origin/main`.

## Was ist offen / unklar / Risiko

### Backlog aus T2.5A/B-Lessons (für T2.5D und später)
- **`meta.adapter_slice` als Runtime-Registry noch nicht projiziert** — Slices leben nur im Code; eine Observability-Sicht „welche Slices sind registriert" braucht einen Python-Interpreter. Für T2.6 Freshness-Dashboard zu lösen.
- **Tier-B `remote_url=""` bleibt stiller Vertrag** — Operator pinnt pro Lauf via `--remote-url`. Dokumentiert im SliceSpec-`notes`-Feld, aber nicht selbst-erklärend beim Lesen von `list-slices` (zeigt `has_url=no`).
- **Kein isolierter Mart-Test für `winner_team='TIE'`/`position_is_known`-Zweige** — Integrationsebene fängt sie ab, Feingranular-Test fehlt.

### Backlog aus T2.5C-Lessons (dringlich)
- **`position_is_known` ist ohne Ontology-Load immer `NULL`** — Bootstrap aktiviert keine Default-Version. UI-Konsumenten müssen dreiwertige Logik rendern, solange `bootstrap_local_environment` die Ontologie nicht auto-aktiviert. **Lösung geplant in T2.6A** (UI-Tranche mit erstem Ontology-Konsumenten).
- **`CoreLoadResultLike`-Round-Trip-Contract-Test fehlt** — T2.5D soll einen Instantiierungs-Test mitbringen, der beweist, dass die neue `CoreRosterLoadResult` dem Protocol genügt (Import + Zuweisung).
- **`_CROSS_CHECK_FIELDS` wiederholt sich pro Domäne** — bei vier Listen (Rosters kommt dazu) Kandidat für `SliceSpec.cross_check_fields`, wenn T2.5D die vierte Instanz begründet.

### Backlog aus ADR-0027 §Offene Punkte (Teil-offen nach T2.5C)
- `meta.cluster_assignment` als persistente Cluster-Tabelle — bisher werden Cluster nur pro `dedupe_run` zurückgegeben, nicht persistiert.
- `dedupe-review-resolve` CLI parallel zu `quarantine-resolve`.
- Runner-Executor `dedupe_run` parallel zu `mart_build` (aktuell nur operator-getriggert, nicht schedulbar).

### Pre-existing
- **Ruff-Befunde (~11)** bleiben unangetastet — nicht aus dieser Session.

## Strategische Analyse für die nächste Session

### Wo wir global im Projekt stehen (Stand HEAD `5ec3e29`, 2026-04-22, KW 17)

**Zielkorridor v1.0:**
- feature-complete: Ende Juni 2026 (KW 26) — **noch 9 Wochen**.
- Testphase: Juli 2026 (T3.0).
- Produktiv auf Windows-VPS: vor Preseason-Start Anfang August 2026 (T3.1).

**Schedule-Realität:**
- **Domain-Expansion (T2.5) lief in dieser Session schneller als geplant.** Ursprünglicher Plan: KW 20–22 für T2.5A–F (6 Sub-Tranches). Stand jetzt: T2.5A, B, C in KW 17 abgeschlossen — drei Wochen Vorsprung auf den ursprünglichen Plan. Die Slice-Abstraktion aus T2.5A zahlt sich ab der zweiten Domäne aus.
- **Aber:** der Rest von T2.5 (Rosters, Team-Stats, Player-Stats) wird **nicht** linear schneller. T2.5D bringt Bitemporalität, T2.5E/F bringen Window-Funktionen und Tier-Konflikt-Auflösung auf Aggregat-Ebene — Komplexitätssprünge gegenüber dem schlanken Teams/Games/Players-Muster.
- **UI (T2.6, 8 Sub-Tranches)** ist der typisch-unterschätzte Brocken. ADR-0030 ist noch `Proposed`. Der Puffer aus dem Domain-Vorsprung fließt sinnvoll hier hin.

### Was die Foundation jetzt liefert (Stand HEAD `5ec3e29`)

1. **Internal Job Runner** mit atomarem Claim, Retry-Policies, Replay (T2.3A/B).
2. **Quarantäne als First-Class-Domäne** mit Auto-Hook + `scope_type ∈ {team, game, player}` (T2.3C + T2.5A/B/C).
3. **`mart.*` als alleiniger Read-Pfad** mit AST-Lint-Guard (T2.3D).
4. **Ontologie-as-Code v0_1** mit idempotentem Loader (T2.4A) — jetzt auch im Mart konsumiert via `position_is_known`.
5. **Dedupe-Pipeline** mit pluggable `Scorer`-Protocol (T2.4B) und **erster realer Anwendung** gegen `core.player` (T2.5C).
6. **Adapter-Slice-Registry** (ADR-0031) — drei Primary-Domänen, drei Cross-Check-Domänen, reale HTTP-Variante end-to-end.
7. **`CoreLoadResultLike`-Protocol** für uniformen Result-Vertrag quer über Teams/Games/Players.

### Was T2.5D zum ersten Mal orchestriert

T2.5D ist nicht „vierte Kopie des T2.5A-Musters", sondern **erste bitemporale Domäne**:

- `core.roster_membership` trägt `player_id`, `team_id`, `season`, `week`, `valid_from`, `valid_to` — nicht mehr einen Snapshot, sondern eine Historie.
- Trade-Erkennung durch Überschneidung: wenn ein `player_id` innerhalb einer Season `team_id` wechselt, muss das als Event in `meta.dedupe_run` oder einer neuen `meta.roster_event`-Tabelle sichtbar werden.
- `mart.roster_current_v1` und `mart.roster_history_v1` sind zwei separate Read-Modelle (aktueller Zustand vs. vollständige Historie) — die Trennung nach ADR-0029 erzwingt das.
- **`core.player.current_team_id` aus T2.5C wird redundant** — die aktive Team-Zugehörigkeit pro `player_id` wandert in die Roster-Sicht. `current_team_id` bleibt als Snapshot-Feld, ist aber nicht mehr die Quelle der Wahrheit für „spielt gerade für X".

### Risiken & Vorschläge für T2.5D

- **Bitemporalität ist ADR-würdig.** Empfehlung: **ADR-0032 — Bitemporale Modellierung von Roster-Mitgliedschaften** als `Proposed`-Skelett anlegen, bevor T2.5D-Code entsteht. Inhalt: Zeit-Dimensionen (System-Time via `_loaded_at` + Business-Time via `valid_from`/`valid_to`), Überschneidungs-Semantik, Snapshot-vs-Historie-Trennung.
- **Verfügbarkeit der Quelldaten prüfen:** nflverse liefert wöchentliche Roster-Snapshots, keine fertigen `valid_from`/`valid_to`-Intervalle. Der Stage-Load muss die wöchentlichen Snapshots in Intervalle transformieren — das ist der einzige wirklich neue Algorithmus in T2.5D.
- **Thresholds für Trade-Erkennung offen:** ein Player fehlt in Woche N aus Team X und taucht in Woche N+1 bei Team Y auf — Trade oder Cut+Signing? Ohne Transaktions-Feed (nflverse liefert keine expliziten Transaktionen in der Standard-CSV) ist die Erkennung Heuristik. Dokumentations-Verpflichtung für ADR-0032.
- **Time-Box:** T2.5D ist der erste echte Komplexitätssprung. Wenn nach 1 Woche (= KW 18) kein grüner Smoke, Operator-Check und Re-Slice prüfen.

### Was *nicht* in T2.5D gehört

- **UI-Arbeit** — bleibt T2.6.
- **VPS-Deploy** — T3.1.
- **Persistentes Cluster-Assignment für Dedupe** — ADR-0027 Offene Punkte; eigenes Bolt nach T2.5F.
- **Transaktions-Tracking (explizite Trades, Cuts, Signings)** — Phase 1.5.

## Geänderte / neue Dokumente in dieser Session

### Neu
- `src/new_nfl/adapters/slices.py` (+ 7 SliceSpec-Einträge über T2.5A/B/C)
- `src/new_nfl/core/teams.py`, `src/new_nfl/core/games.py`, `src/new_nfl/core/players.py`
- `src/new_nfl/core/result.py` (CoreLoadResultLike Protocol)
- `src/new_nfl/mart/team_overview.py`, `src/new_nfl/mart/game_overview.py`, `src/new_nfl/mart/player_overview.py`
- `src/new_nfl/dedupe/core_player_source.py` (dedupe-from-core)
- `tests/test_teams.py`, `tests/test_games.py`, `tests/test_players.py`
- `ontology/v0_1/term_conference.toml`, `ontology/v0_1/term_division.toml`
- `docs/adr/ADR-0031-adapter-slice-strategy.md`
- Dieses Handoff-Dokument

### Geändert
- `src/new_nfl/core/__init__.py`, `src/new_nfl/mart/__init__.py`, `src/new_nfl/dedupe/__init__.py` (Re-Exports)
- `src/new_nfl/core_load.py` (Union-Return, Dispatch auf Teams/Games/Players)
- `src/new_nfl/remote_fetch.py`, `src/new_nfl/stage_load.py` (Slice-Dispatch)
- `src/new_nfl/jobs/runner.py` (`team_overview_v1`/`game_overview_v1`/`player_overview_v1`-Mart-Build)
- `src/new_nfl/cli.py` (`--slice`-Flag, `list-slices`, `--source core-player`, Dispatch-Refactor)
- `docs/PROJECT_STATE.md`, `docs/T2_3_PLAN.md`, `docs/LESSONS_LEARNED.md`
- `docs/adr/README.md` (ADR-0031 von `Proposed` auf `Accepted`)

## Lessons-Learned-Einträge

Alle in `docs/LESSONS_LEARNED.md`, jeweils oberster Eintrag pro Tranche, **alle Status `draft` (wartet auf Operator-Freigabe):**
- 2026-04-22 — T2.5C Players-Domäne + erste reale Dedupe-Anwendung + Protocol-Refactor
- 2026-04-22 — T2.5B Games-Domäne + erste reale HTTP-Runde
- 2026-04-22 — T2.5A Teams-Domäne + Adapter-Slice-Registry

## Vor dem Wechsel noch zu tun (in dieser Session)

Keine Pending-Aktionen. Git ist sauber, Tests grün, docs synchronisiert, alle Commits auf `origin/main`.

**Empfohlen für die neue Session:**
1. Operator-Freigabe für die drei Lessons-Learned-Drafts (T2.5A/B/C) abfragen, bevor T2.5D-Code entsteht.
2. ADR-0032 (Bitemporale Roster-Modellierung) als `Proposed`-Skelett anlegen, bevor T2.5D-Implementierung startet — vermeidet Diskussion im Implementierungs-Druck (Manifest §3.7).

## Starter-Prompt für die neue Session

```text
Du übernimmst das Projekt **NEW NFL** (privates NFL-Daten-/Analysesystem,
Single-Operator, Python 3.12, DuckDB-Zentrum, Windows-VPS-Ziel ab v1.0).
Repo lokal: c:\projekte\newnfl
Repo remote: https://github.com/andreaskeis77/new_nfl
Arbeitssprache: Deutsch.

**Pflichtlektüre vor jedem größeren Schritt — in dieser Reihenfolge:**
1. docs/PROJECT_STATE.md
2. docs/_handoff/chat_handoff_20260422-1500_t25c-players-and-first-real-dedupe-done.md
3. docs/ENGINEERING_MANIFEST_v1_3.md
4. docs/concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md
5. docs/T2_3_PLAN.md (T2.5D ab §4)
6. docs/UI_STYLE_GUIDE_v0_1.md (für UI-Tranches ab T2.6)
7. docs/CHAT_HANDOFF_PROTOCOL.md
8. docs/LESSONS_LEARNED_PROTOCOL.md
9. docs/LESSONS_LEARNED.md (Top-3-Einträge sind T2.5A/B/C als draft —
   Operator-Freigabe einholen, bevor du T2.5D-Code schreibst)
10. docs/adr/README.md (insb. ADR-0027, ADR-0028, ADR-0029, ADR-0031)
11. docs/adr/ADR-0031-adapter-slice-strategy.md (Implementierungsnotizen
    T2.5A/B)

**Verbindliche Regeln:**
- Engineering Manifest v1.3 gilt vollständig (Prio-Reihenfolge §2,
  Prinzipien §3.1–3.13).
- Befehle immer mit Ausführungsort kennzeichnen: DEV-LAPTOP / VPS-USER /
  VPS-ADMIN. In dieser Phase ist alles DEV-LAPTOP.
- Vollständige Dateien liefern, keine Patch-Snippets (Manifest §7.5).
- Operator-Aktionen sind in v1.0 CLI-only, UI-Buttons erst v1.1.
- UI/API liest ausschließlich aus mart.* (ADR-0029).
- Quarantäne ist First-Class (ADR-0028), Replay aus immutable Raw ist
  Pflicht.
- Personen-/Teamnamen immer in offizieller Vollform (UI Style Guide §1).
- Neue Slices leben als SliceSpec-Einträge in
  src/new_nfl/adapters/slices.py (ADR-0031), nicht in source_registry.
- Jedes Core-Load-Modul gibt einen Result-Typ zurück, der
  CoreLoadResultLike genügt (src/new_nfl/core/result.py).
- Schlage proaktiv einen Chat-Handoff vor, sobald ein Trigger aus
  CHAT_HANDOFF_PROTOCOL.md §2.1 zutrifft.
- Aktualisiere PROJECT_STATE.md und T2_3_PLAN.md automatisch nach jedem
  Tranche-Abschluss.
- Erstelle nach jeder Tranche einen Lessons-Learned-Eintrag (draft) gemäß
  LESSONS_LEARNED_PROTOCOL.md.
- Termine werden gegen reale Tranche-Last validiert, bevor sie übernommen
  werden.

**Aktueller Stand (HEAD 5ec3e29, 2026-04-22, KW 17):**
- T2.5A (Teams), T2.5B (Games + real HTTP), T2.5C (Players + first real
  dedupe + CoreLoadResultLike-Protocol) sind abgeschlossen und gepusht.
- Test-Suite grün: 157/157.
- Drei Primary-Domänen (core.team, core.game, core.player) mit
  mart.*_overview_v1, Quarantäne-Hook auf Tier-A/B-Diskrepanz.
- Adapter-Slice-Registry mit 7 Einträgen (4 Primary + 3 Cross-Check).
- Erste reale Dedupe-Anwendung: `dedupe-run --domain players
  --source core-player` clustert Player-IDs über core.player.
- ADR-0027, ADR-0028, ADR-0029, ADR-0031 sind `Accepted`.
  ADR-0030 (UI Stack) bleibt `Proposed` bis T2.6A.
- Zielkorridor: v1.0 feature-complete bis Ende Juni 2026 (KW 26) —
  noch 9 Wochen; Domain-Teil ist 3 Wochen vor Plan.

**Konkreter nächster Schritt:**
**T2.5D — Rosters zeitbezogen** gemäß T2_3_PLAN.md §4.

Das ist der erste echte Komplexitätssprung in T2.5:
- `core.roster_membership` mit `player_id`, `team_id`, `season`, `week`,
  `valid_from`, `valid_to` (Bitemporalität erstmals in v1.0).
- Stage-Load: wöchentliche nflverse-Roster-Snapshots in
  `valid_from`/`valid_to`-Intervalle transformieren.
- Trade-Erkennung durch Wochen-Überschneidung pro `player_id`.
- `mart.roster_current_v1` (aktueller Zustand) und `mart.roster_history_v1`
  (vollständige Historie) als zwei separate Read-Modelle.
- `core.player.current_team_id` bleibt als Snapshot-Feld, ist aber nicht
  mehr Single Source of Truth für aktive Team-Zugehörigkeit.

**Empfohlene Reihenfolge:**
1. Zuerst Operator-Freigabe für die drei draft Lessons-Learned-Einträge
   (T2.5A/B/C) einholen — sonst bleiben sie auf draft.
2. **ADR-0032 — Bitemporale Modellierung von Roster-Mitgliedschaften**
   als Proposed-Skelett anlegen (Zeit-Dimensionen, Überschneidungs-
   Semantik, Snapshot-vs-Historie-Trennung, Trade-Heuristik-Grenzen).
3. CoreLoadResultLike-Round-Trip-Contract-Test für `CoreRosterLoadResult`
   einplanen (lehrt aus T2.5C §Backlog).
4. Erst dann T2.5D-Code.

Lies erst die Pflichtlektüre, dann bestätige Verständnis in 5 Bullets,
dann frage nach Freigabe für T2.5D (inkl. ADR-0032-Proposed-Skelett
voranstellen).
```

## Verweise

- `docs/CHAT_HANDOFF_PROTOCOL.md`
- `docs/LESSONS_LEARNED_PROTOCOL.md`
- `docs/T2_3_PLAN.md` (T2.5D ab §4)
- `docs/adr/ADR-0031-adapter-slice-strategy.md`
- `docs/adr/ADR-0027-dedupe-pipeline-as-explicit-stage.md` (Offene Punkte)
- `docs/adr/README.md`
- `docs/_handoff/chat_handoff_20260416-1900_t24-ontology-runtime-done.md` (Vor-Handoff)
