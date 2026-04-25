# Chat-Handoff 2026-04-25 17:00 — T3.1S Core-Loader-Schema-Drift-Fix abgeschlossen, T3.1 Step 2 als naechster Bolt

## Trigger

§2.1 **Major-Milestone + thematisch abgrenzbarer Naechst-Bolt:** T3.1S ist code-seitig durch (Column-Alias-Registry + 12 Unit-Tests + 8 Network-Smokes), die VPS-Re-Smoke hat alle drei vormals roten Slices auf gruen geflippt, die 2026-04-24-Lesson ist auf `accepted`. Der naechste Bolt T3.1 Step 2 (restliche 6 Fetch-Tasks) ist deployment-zentriert und thematisch separat. Natuerlicher Sitzungsschnitt.

## Was wurde in dieser Session erreicht

- **Column-Alias-Registry (T3.1S, Option B aus T2_3_PLAN.md §10.1):** Neues Modul [src/new_nfl/adapters/column_aliases.py](../../src/new_nfl/adapters/column_aliases.py) als Single-Point-of-Truth fuer nflverse-Schema-Drifts. `ALIAS_REGISTRY: dict[str, dict[str, str]]` mit drei Eintraegen — `players` (`gsis_id` → `player_id`), `rosters` (`gsis_id` → `player_id`, `team` → `team_id`), `team_stats_weekly` (`team` → `team_id`). Helper `apply_column_aliases(con, qualified_table, slice_key)` macht idempotenten `ALTER TABLE ... RENAME COLUMN`: case-insensitives Match, Original-Case fuer ALTER, no-op bei fehlender Tabelle / unbekanntem Slice / kanonischem Namen schon vorhanden. `core/player_stats.py` ist bewusst nicht in der Registry — der Loader akzeptierte `team` und `player_id` schon vor T3.1S.
- **Drei Core-Loader integriert:** [src/new_nfl/core/players.py](../../src/new_nfl/core/players.py), [src/new_nfl/core/rosters.py](../../src/new_nfl/core/rosters.py), [src/new_nfl/core/team_stats.py](../../src/new_nfl/core/team_stats.py) rufen `apply_column_aliases` vor `_assert_required_columns` auf, fuer die Tier-A-Stage und in einer Schleife fuer jede Tier-B-Cross-Check-Stage. Helper-Aufruf ist 4 Zeilen pro Loader; saemtlicher SQL-Code unveraendert. Idempotent ueber Re-Runs (zweiter Aufruf sieht die kanonischen Namen schon in place).
- **Lesson-Konsequenz aus 2026-04-24 umgesetzt:** `@pytest.mark.network`-Marker in [pyproject.toml](../../pyproject.toml) registriert; `addopts = -q -m 'not network'` schliesst Network-Tests vom Default-Run aus. Opt-in via `pytest -m network`.
- **8 neue Network-Smokes:** [tests/test_slices_network_smoke.py](../../tests/test_slices_network_smoke.py) probt alle 7 Primary-Slices der `nflverse_bulk`-Adapter (4 statisch + 3 per-season auf `PINNED_SMOKE_SEASON=2024`) gegen die echten `nflverse-data/releases/...`-URLs. HEAD-Probe mit GET-Fallback bei 405 + CSV-Header-Heuristik (`,` in erster Zeile) als Sanity gegen 200-HTML-Error-Pages. `PINNED_SMOKE_SEASON` ist deliberately not an `default_nfl_season()` gekoppelt — ein Kalenderflip mid-test darf den Smoke nicht von gruen auf rot kippen. Coverage-Test `test_all_seven_primary_slices_are_covered` pinnt das Set der primaeren Slice-Keys, sodass eine kuenftige Slice ohne Smoke-Update einen lauten Fehler erzeugt.
- **12 neue Unit-Tests** in [tests/test_column_aliases.py](../../tests/test_column_aliases.py): Registry-Shape gepinnt (gegen unbeabsichtigte Erweiterungen), `get_aliases_for_slice` Copy-Semantik, Helper-Verhalten (Rename, Idempotenz, fehlende Tabelle, kanonische Spalte schon vorhanden, unknown slice, case-insensitive `GSIS_ID` → `player_id`), drei End-to-End-Tests: jeder betroffene Loader laeuft `execute=True` durch wenn die Stage-Tabelle die nflverse-Spaltennamen traegt.
- **VPS-Re-Smoke 2026-04-25 (DoD-Bestaetigung):** `run_slice.ps1 -Slice <key> -Season 2024` fuer alle drei Slices, jeweils `=== DONE ===`:
  - `players`: 24408 source rows → core.player 24408 distinct, 0 invalid, 0 conflicts; mart.player_overview_v1 24408.
  - `rosters`: 46579 source rows → core.roster_membership 10861 intervals (3215 distinct players, 167 open), 7 invalid (Edge-Cases); meta.roster_event 852 mit 234 trades; mart.roster_current_v1 167, mart.roster_history_v1 10861.
  - `team_stats_weekly`: 570 source rows → core.team_stats_weekly 570 (570 distinct (team, season, week)), 0 invalid; mart.team_stats_weekly_v1 570, mart.team_stats_season_v1 32 (32 Franchises).
- **Lesson 2026-04-24 auf `accepted` geflippt** mit T3.1S-Folgeumsetzung-Block + VPS-Re-Smoke-Beleg.
- **Restrisiko #10 in [v1.0.0-laptop.md §5](../_ops/releases/v1.0.0-laptop.md) geschlossen** (#9 bleibt mit Folge-Hinweis offen, ist aber durch URL-Drift-Fix in T3.1 Step 1 ohnehin schon code-seitig adressiert).

## Was ist offen / unklar / Risiko

- **T3.1 Step 2 — restliche 6 Fetch-Tasks auf VPS** (siehe [T2_3_PLAN.md §10.2](../T2_3_PLAN.md)). Anpassung an `deploy/windows-vps/vps_install_tasks.ps1` oder ein neues `vps_install_tasks_step2.ps1`. Per-season-Slices brauchen `-Season`-Parameter beim Task-Argument (aktuelles `run_slice.ps1` durchreichen). DoD: 2 Tage Beobachtung aller 7 Fetches + Backup ohne Quarantaene-Eskalation = T3.1 final.
- **Backup-Task-Manual-Trigger steht weiterhin aus** (`LastTaskResult=267011` = "not yet run"). Loest sich entweder beim naechsten 04:00-Trigger automatisch oder per `Start-ScheduledTask -TaskName NewNFL-Backup-Daily`. Nicht T3.1-Step-2-blockierend, aber sollte vor T3.1 final mindestens einmal manuell durchgespielt sein.
- **Rosters-Edge-Cases (7 invalid rows):** Die Tier-A-Validierung verwirft 7 von 46579 Zeilen wegen fehlender `player_id`/`team_id`/`season`/`week`. Das ist erwartet bei nflverse-Snapshots am Saison-Anfang/Ende (Practice-Squad-Edge-Cases ohne stabile IDs). Kein Blocker, aber wenn die Zahl in T3.0 wachsen sollte, lohnt sich ein gezielter Spot-Check.
- **234 Trade-Events in 2024 sind hoeher als die ~50 echten NFL-Trades pro Saison.** Das bedeutet: ADR-0032-Heuristik klassifiziert auch practice-squad-Wechsel und IR-Activations als Trades (konservatives Default — `released`+`signed` haette die korrekte Klassifikation gefehlt, daher `trade` als Container). T3.0-Operator-Validierung gegen echte Trade-Listen ist explizit als ADR-0032-Flip-Trigger im Plan vorgesehen — nicht T3.1S-relevant.
- **Optionaler `pytest -m network`-Lauf** vor T3.1 Step 2 ist nicht zwingend, aber als zusaetzliches Pre-Release-Gate sinnvoll. Bisher noch nicht ausgefuehrt.
- **Push wurde 2026-04-25 zwischen T3.1S-Code-Commit und VPS-Re-Smoke ausgefuehrt** (Commit `17a529e` ist auf origin). HEAD jetzt nach Doku-Closer auf einem Folgecommit (siehe Aktueller Arbeitsstand).

## Aktueller Arbeitsstand

- **Phase:** T3.1 VPS-Migration laeuft. Step 1 + T3.1S durch; Step 2 ist der naechste Bolt. T3.0 Testphase folgt nach T3.1-Abschluss auf VPS, Juli 2026.
- **Git-Stand:** `main` bei `17a529e` plus diesem Handoff-Closer (Commit folgt). VPS bei `17a529e`. Working-Tree nach Handoff-Commit sauber.
- **Tests:** **474 gruen** (462 aus T3.1 Step 1 + 12 neue T3.1S-Tests), 8 deselected (= 8 `@pytest.mark.network`-Smokes). Laufzeit ~9:57 auf DEV-LAPTOP.
- **Ruff:** 44 Errors, Delta -1 gegenueber Baseline 45 (alle pre-existing UP035/UP037/E501/I001/B905/UP012/E741, keine neue Regression).
- **AST-Lint:** gruen (`tests/test_mart.py::test_read_modules_do_not_reference_core_or_stg_directly`).
- **VPS-Status:** `C:\newNFL` auf `17a529e`, Python 3.12 Venv aktiv. Alle 7 Primary-Slices end-to-end gruen (4 aus Step 1 + 3 aus T3.1S). Scheduled Tasks `NewNFL-Backup-Daily` (04:00) + `NewNFL-Fetch-Teams` (05:00) aktiv.
- **Letzter erfolgreicher Pflichtpfad:** Full-Suite gruen auf DEV-LAPTOP; Ruff Delta ≤ 0; AST-Lint gruen; alle 7 Primary-Slices `run_slice.ps1 -Slice <key> -Season 2024` gruen auf VPS.
- **Naechster konkreter Schritt:** **T3.1 Step 2 starten** — 6 weitere Scheduled Tasks `NewNFL-Fetch-{Games,Players,Rosters,TeamStats,PlayerStats,Schedule}` installieren, 2 Tage beobachten.

## Geaenderte / neue Dokumente in dieser Session

- Neu: [src/new_nfl/adapters/column_aliases.py](../../src/new_nfl/adapters/column_aliases.py) — Alias-Registry + Helper.
- Neu: [tests/test_column_aliases.py](../../tests/test_column_aliases.py) — 12 Unit-Tests.
- Neu: [tests/test_slices_network_smoke.py](../../tests/test_slices_network_smoke.py) — 8 Network-Smokes.
- Neu: dieses Handoff-Dokument.
- Geaendert (Code): [src/new_nfl/core/players.py](../../src/new_nfl/core/players.py), [src/new_nfl/core/rosters.py](../../src/new_nfl/core/rosters.py), [src/new_nfl/core/team_stats.py](../../src/new_nfl/core/team_stats.py) — Alias-Helper-Aufruf.
- Geaendert (Konfig): [pyproject.toml](../../pyproject.toml) — `network`-Marker, `addopts` mit `-m 'not network'`.
- Geaendert: [docs/PROJECT_STATE.md](../PROJECT_STATE.md) (Phase, Completed, Current cycle, Preferred next bolt).
- Geaendert: [docs/T2_3_PLAN.md](../T2_3_PLAN.md) §10 + §10.1 (T3.1S auf erledigt + VPS-Re-Smoke-Beleg).
- Geaendert: [docs/LESSONS_LEARNED.md](../LESSONS_LEARNED.md) (2026-04-24-Eintrag auf `accepted` geflippt + T3.1S-Folgeumsetzung-Block + VPS-Re-Smoke-Beleg).
- Geaendert: [docs/_ops/releases/v1.0.0-laptop.md](../_ops/releases/v1.0.0-laptop.md) §5 (Restrisiken #9 + #10 als adressiert / geschlossen).
- Memory-Update: [memory/feedback_delivery.md](../../../../Users/andre/.claude/projects/c--projekte-newnfl/memory/feedback_delivery.md) — Praezisierung „Ausfuehrungsort-Prefix steht ausserhalb des Code-Blocks" + „PowerShell 5.1 hat kein `&&`".

## Lessons-Learned-Eintrag

Kein eigener T3.1S-Eintrag — die 2026-04-24-Lesson („T3.1 VPS-Smoke entdeckt URL-Drift UND Schema-Drift bei nflverse") ist auf `accepted` geflippt mit T3.1S-Folgeumsetzung-Block und VPS-Re-Smoke-Beleg als Schliesslied. Die fuenf konkreten Methodaenderungen sind damit operational verankert (network-Marker code-seitig, Pin-Strategie, Restrisiko-Nachtrag, Plan-Doku-Konsistenz, Refactor-Zeit-Schaetzung).

Eine sekundaere Beobachtung wurde in [memory/feedback_delivery.md](../../../../Users/andre/.claude/projects/c--projekte-newnfl/memory/feedback_delivery.md) als Feedback-Memory persistiert: Ausfuehrungsort-Prefix gehoert ausserhalb des Code-Blocks (sonst kopiert der Operator `VPS-USER PS> ...` und PowerShell sucht ein Cmdlet `VPS-USER`). PowerShell 5.1 hat zudem kein `&&` als Statement-Separator — Befehle werden in einzelne Zeilen oder einzelne Code-Bloecke gesplittet. Beide Punkte sind fuer kuenftige Sessions wichtig, aber thematisch zu klein fuer einen eigenen Lesson-Learned-Eintrag.

## Starter-Prompt fuer die neue Session

```text
Du uebernimmst das Projekt **NEW NFL** — ein privates, single-operator-
betriebenes NFL-Daten- und Analysesystem. Arbeitssprache Deutsch. Der
Operator (Andreas) arbeitet allein, ohne Team, ohne externe Abnahme.

**Repo:**
- lokal: c:\projekte\newnfl (Haupt-Checkout, branch `main`)
- remote: https://github.com/andreaskeis77/new_nfl
- Git-Tag `v1.0.0-laptop` auf `main` (2026-04-24) markiert den v1.0-Cut.
- HEAD nach T3.1S: Commit `17a529e` (Column-Alias-Registry + Network-Marker).

**Zielkorridor:**
- v1.0 feature-complete: ✅ erreicht 2026-04-24.
- T3.1 VPS-Migration **vorgezogen vor T3.0** (siehe [ADR-0034](../adr/ADR-0034-vps-first-before-testphase.md)).
  - Step 1 ✅ erledigt 2026-04-24.
  - T3.1S Schema-Drift-Fix ✅ erledigt 2026-04-25 (alle 7 Primary-Slices gruen auf VPS).
  - **Step 2 (restliche 6 Fetch-Tasks)** offen → das ist dein naechster Bolt.
- T3.0 Testphase auf VPS: Juli 2026, nach T3.1-Abschluss.
- Produktiv (Tailscale-only, Port 8001): vor NFL-Preseason Anfang August 2026.

---

## Pflichtlektuere vor dem Step-2-Start (in dieser Reihenfolge)

1. **docs/PROJECT_STATE.md** — Current cycle zeigt T3.1 Step 2 als Preferred next bolt.
2. **docs/_handoff/chat_handoff_20260425-1700_t31s-schema-drift-done.md** — dieser Handoff.
3. **docs/T2_3_PLAN.md §10.2** — Step-2-Scope.
4. **docs/_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md** Phase 5 — bestehende Task-Installation als Referenz.
5. **deploy/windows-vps/vps_install_tasks.ps1** — Step-1-Vorlage; Step 2 erweitert oder ersetzt das Skript.
6. **deploy/windows-vps/run_slice.ps1** — Wrapper fuer `-Season`-Parameter; per-season-Slices brauchen den.
7. **docs/ENGINEERING_MANIFEST.md** oder **ENGINEERING_MANIFEST_v1_3.md** (Draft).
8. **docs/CHAT_HANDOFF_PROTOCOL.md** + **docs/LESSONS_LEARNED_PROTOCOL.md** — Protokoll-Pflichten am Session-Ende.

---

## Verbindliche Regeln (gelten fuer jede Antwort)

**Sprache + Stil:**
- Arbeitssprache Deutsch. Code-Identifier bleiben englisch.
- Kurze, praezise Antworten; kein Emoji-Spam.

**Engineering:**
- Manifest gilt vollstaendig. Vollstaendige Dateien liefern, keine Patch-Snippets (§7.5).
- Keine Scope-Ausweitung ohne explizite Freigabe.
- UI/API liest ausschliesslich aus `mart.*` (ADR-0029). AST-Lint-Test ist das Gate.
- Neue CLI-Subcommands ueber Plugin-Registry (ADR-0033).
- Neue Mart-Builder tragen `@register_mart_builder`-Decorator.
- Tests pro neues Feature hart: Full-Suite gruen. Aktueller Stand: **474 Tests gruen, 8 deselected (network) in ~9:57 auf DEV-LAPTOP**.
- Ruff-Delta <= 0 gegenueber Baseline 45 (aktuell 44, also Delta -1).
- PowerShell-Dateien (`*.ps1`): **ASCII-only** — keine Em-Dashes/Umlaute. Windows-PowerShell 5.1 liest UTF-8 ohne BOM als CP1252. Zudem: kein `&&` als Statement-Separator (PS 5.1 hat keine Pipeline-Chain-Operatoren).

**Ausfuehrungsort:**
- Befehle mit Prefix kennzeichnen: `DEV-LAPTOP $`, `VPS-ADMIN PS>`, `VPS-USER PS>`. Prefix steht **ausserhalb** des Code-Blocks (als Bold-Label oder Satzeinleitung), nie im Code-Block selbst.
- Mehrere Befehle pro Operator-Schritt nicht via `&&` chainen — eigene Zeilen oder eigene Code-Bloecke.

**Parallel-Entwicklung:**
- Worktree-Pflicht bei ≥2 parallelen Streams (siehe PARALLEL_DEVELOPMENT.md T2.7-Retro).

**Protokoll-Pflichten:**
- Am Bolt-Ende (also nach Step 2) Chat-Handoff proaktiv vorschlagen (§2.1).
- Lessons-Draft bei Ueberraschungen sofort anlegen.
- PROJECT_STATE, T2_3_PLAN, ADR-Index nach relevanten Entscheidungen aktualisieren.

---

## T3.1 Step 2 — konkreter Scope (gemaess T2_3_PLAN.md §10.2)

**Ziel:** die restlichen 6 Fetch-Tasks auf VPS installieren und 2 Tage beobachten. Nach grueneer Beobachtung ist T3.1 final.

**Tasks:**
- `NewNFL-Fetch-Schedule` (statisch, slice schedule_field_dictionary)
- `NewNFL-Fetch-Games` (statisch, slice games)
- `NewNFL-Fetch-Players` (statisch, slice players)
- `NewNFL-Fetch-Rosters` (per-season, slice rosters, `-Season`-Parameter)
- `NewNFL-Fetch-TeamStats` (per-season, slice team_stats_weekly, `-Season`-Parameter)
- `NewNFL-Fetch-PlayerStats` (per-season, slice player_stats_weekly, `-Season`-Parameter)

**Empfehlung:** ein neues `deploy/windows-vps/vps_install_tasks_step2.ps1` (statt das Step-1-Skript zu erweitern), damit der iterative Rollout-Charakter erhalten bleibt und Re-Runs idempotent sind. Tasks-Trigger gestaffelt 05:15 / 05:30 / 05:45 / 06:00 / 06:15 / 06:30 (analog zum Step-1-Muster `NewNFL-Fetch-Teams` 05:00). Zeitversatz vermeidet GitHub-Rate-Limit-Risiko.

**Per-season-Argument:** der Scheduled Task laesst `run_slice.ps1` ohne `-Season` laufen — `default_nfl_season()` (`src/new_nfl/adapters/slices.py`) liefert dann automatisch das richtige Jahr (Sep–Dec → current; Jan–Aug → previous). Pruefung: aktuell `2026-04-25` → `default_nfl_season() == 2025`; nflverse-Asset `roster_weekly_2025.csv` muss existieren — entweder via `pytest -m network` validieren oder manuell `curl -I https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_2025.csv` checken.

**DoD Step 2:**
- Alle 6 Tasks angelegt mit `LastTaskResult=0` nach manuellem Initial-Trigger.
- 2 Tage Beobachtung: alle 7 Fetches laufen 04:00–06:30 ohne Quarantaene-Eskalation, kein `meta.run_event` mit `severity in ('error','critical','fatal')` ausserhalb der dokumentierten Edge-Cases.
- Backup-Task selbst einmal manuell durchgespielt (oder durch 04:00-Trigger automatisch).
- 24-Stunden-Smoke-Lauf-DoD aus T2_3_PLAN.md §10 erfuellt.

**Pflicht vor erstem Code-Aenderungs-Schritt:** Pflichtlektuere lesen, Verstaendnis in 5 Bullets bestaetigen, Operator-Freigabe einholen (insbesondere fuer das neue `vps_install_tasks_step2.ps1` vs Erweiterung des Step-1-Skripts).

---

## Eskalations-Hinweise

- **Code-Regression vermutet** → Full-Suite `pytest -v` + Ruff gegen Stand `17a529e` vergleichen.
- **`default_nfl_season()` liefert ein Jahr ohne nflverse-Asset** → temporaer auf vorherige Saison fallen (Operator-Override per `-Season`-Argument im Task) und Lesson aufmachen.
- **Unklare Architektur-Entscheidung** → concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md + ADR-Index, dann Operator fragen.
- **Unerwarteter VPS-Zustand** → **nicht loeschen**, Operator fragen. T2.7-Lesson gilt weiter.

---

## Arbeitsauftrag fuer diese Session

1. Lies die Pflichtlektuere komplett (mindestens Dokumente 1–4 der Liste).
2. Bestaetige Verstaendnis in **5 Bullets**:
   - Wo stehen wir (T3.1 Step 1 + T3.1S done, alle 7 Slices gruen, Test-Count 474+8)?
   - Was ist Step 2 Scope (6 Tasks, gestaffelter Trigger)?
   - Welche Architektur-Entscheidung (neues Skript vs Erweiterung)?
   - Welche Pflichtpfade (Test-Gate, Ruff-Delta, AST-Lint, ASCII-only-PS1, kein `&&`)?
   - Welcher `default_nfl_season()`-Befund / Network-Smoke-Vorab-Check?
3. Operator-Freigabe einholen. Kein Blind-Code.
4. Nach Step-2-Abschluss: Handoff-Vorschlag proaktiv + Lessons-Draft, falls Ueberraschungen.
```
