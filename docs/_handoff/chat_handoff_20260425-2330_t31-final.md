# Chat-Handoff 2026-04-25 23:30 — T3.1 VPS-Migration final, T3.0 Testphase als naechste Tranche

## Trigger

§2.1 **Major-Milestone — Tranche-Schluss + thematisch grundverschiedener Naechst-Bolt:** T3.1 ist mit drei Bolzen (Step 1, T3.1S, Step 2) durch und auf VPS verifiziert. Operator-Closer-Lauf 2026-04-25 23:30 hat alle 8 Scheduled Tasks (1 Backup + 7 Fetches) auf `LastTaskResult=0` gebracht. Der naechste Bolt T3.0 Testphase ist eine 4-wochige Beobachtungs- und Lasttest-Phase, thematisch deutlich anders als die T3.1-Migrations-Bolzen. Natuerlicher Sitzungsschnitt.

## Was wurde in dieser Session erreicht

### T3.1S — Core-Loader-Schema-Drift-Fix (vormittag, Commit `17a529e`)

- Neue zentrale Column-Alias-Registry [src/new_nfl/adapters/column_aliases.py](../../src/new_nfl/adapters/column_aliases.py) als Single-Point-of-Truth fuer nflverse-Schema-Drifts. Drei Eintraege: `players` (`gsis_id` → `player_id`), `rosters` (`gsis_id` + `team` → `player_id` + `team_id`), `team_stats_weekly` (`team` → `team_id`). Helper `apply_column_aliases` macht idempotenten `ALTER TABLE ... RENAME COLUMN` (case-insensitives Match, Original-Case fuer ALTER, no-op bei fehlender Tabelle / unbekanntem Slice / kanonischem Namen schon vorhanden).
- Drei Core-Loader (players, rosters, team_stats) rufen den Helper vor `_assert_required_columns` auf, fuer die Tier-A-Stage und in einer Schleife fuer jede Tier-B-Cross-Check-Stage.
- Lesson-Konsequenz aus 2026-04-24 umgesetzt: `@pytest.mark.network`-Marker registriert + 8 Smokes (7 Primary-Slices + Coverage-Test) gegen die echten nflverse-URLs in [tests/test_slices_network_smoke.py](../../tests/test_slices_network_smoke.py); `addopts = -q -m 'not network'` schliesst sie vom Default-Run aus.
- 12 Unit-Tests in [tests/test_column_aliases.py](../../tests/test_column_aliases.py).
- VPS-Re-Smoke 2026-04-25 mittags hat alle drei Slices auf gruen geflippt: `players` 24408 rows · `rosters` 10861 intervals (167 open, 234 trades) · `team_stats_weekly` 570 rows + 32 season aggregates. Lesson 2026-04-24 auf `accepted` geflippt.

### T3.1 Step 2 Code + Tests (Nachmittag, Commit `5a9e54c`)

- Neues Deployment-Skript [deploy/windows-vps/vps_install_tasks_step2.ps1](../../deploy/windows-vps/vps_install_tasks_step2.ps1) registriert sechs zusaetzliche Scheduled Tasks im 15-Minuten-Raster (`05:15 NewNFL-Fetch-Schedule`, `05:30 -Games`, `05:45 -Players`, `06:00 -Rosters`, `06:15 -TeamStats`, `06:30 -PlayerStats`), idempotenter Drop+Re-Register-Pfad, ASCII-only, ohne PS-5.1-Inkompatibilitaeten.
- Per-season-Tasks rufen `run_slice.ps1` ohne `-Season`-Argument auf — `default_nfl_season(today)` greift im Python-Pfad ueber `SliceSpec.remote_url_template` + `resolve_remote_url(spec, season=None)`. Vermeidet Doppel-Pflege des Saison-Jahres.
- 16 statische Validierungs-Tests in [tests/test_deploy_scripts.py](../../tests/test_deploy_scripts.py) ueber alle fuenf `.ps1`-Skripte: ASCII-only-Encoding (PowerShell-5.1-CP1252-Falle), kein `&&`/`||` (Pipeline-Chain-Inkompatibilitaet), exakte Task-Namen + Trigger-Zeiten + Slice-Keys, kein hartcodiertes `-Season`, idempotenter Re-Register-Pattern, `run_slice.ps1` reicht `--season` nur bei explizitem Argument durch.
- Full-Suite **490 gruen** (474 nach T3.1S + 16 Deployment-Tests), 8 deselected (network) in ~8:31 auf DEV-LAPTOP. Ruff Delta -1 vs Baseline 45.

### T3.1 Step 2 Operator-Closer (abend, 23:30 auf VPS)

- VPS-Pull auf `5a9e54c` und Skript-Lauf `vps_install_tasks_step2.ps1` liefen ohne Fehler durch. Sechs Tasks idempotent angelegt.
- Manueller Initial-Trigger pro Task innerhalb von ~3 Minuten ausgefuehrt; jeder Task lief fetch+stage+core durch.
- `Get-ScheduledTask -TaskName NewNFL-* | Get-ScheduledTaskInfo` zeigt fuer **alle 8 Tasks** `LastTaskResult=0`:
  - `04:00 NewNFL-Backup-Daily` — Cron-Tick desselben Tages, zusaetzlich manuell getriggert
  - `05:00 NewNFL-Fetch-Teams` — Step-1-Task, weiter gruen
  - `05:15 NewNFL-Fetch-Schedule` — Step-2-Task, manuell getriggert 23:23:32
  - `05:30 NewNFL-Fetch-Games` — Step-2-Task, manuell getriggert 23:24:03
  - `05:45 NewNFL-Fetch-Players` — Step-2-Task, manuell getriggert 23:24:33
  - `06:00 NewNFL-Fetch-Rosters` — Step-2-Task, manuell getriggert 23:25:15
  - `06:15 NewNFL-Fetch-TeamStats` — Step-2-Task, manuell getriggert 23:26:21
  - `06:30 NewNFL-Fetch-PlayerStats` — Step-2-Task, manuell getriggert 23:26:52

Damit ist der DoD-Hauptpunkt aus T2_3_PLAN.md §10.2 („alle Tasks angelegt mit `LastTaskResult=0` nach manuellem Initial-Trigger") erfuellt.

## Was ist offen / unklar / Risiko

- **2-Tage-Beobachtungsfenster laeuft 2026-04-25 → 2026-04-27.** DoD verlangt: keine `meta.run_event` mit `severity in ('error','critical','fatal')` ausserhalb dokumentierter Edge-Cases (insbesondere die 7 invalid roster rows aus 2024). Operator beobachtet Tag 1 (26.04) und Tag 2 (27.04) Cron-Tick-Ergebnisse. Ueberwachung am einfachsten via `Get-ScheduledTask -TaskName NewNFL-* | Get-ScheduledTaskInfo` plus stichprobenartige `meta.run_event`-Inspektion ueber `new-nfl run-evidence-list` oder Web-UI.
- **Backup-End-to-End-Drill** (Snapshot → `verify-snapshot` → Test-`restore-snapshot` in einem temporaeren Verzeichnis) ist als DoD-Punkt fuer T3.0 vorbehalten; mechanisch ausgeliefert und unit-test-validiert (T2.7C/D), aber Operator-Validation gegen echte Produktions-DB steht aus.
- **Nflverse `roster_weekly_2025.csv` und Co.:** Per-season-Tasks rufen ohne `-Season` auf, also `default_nfl_season()` liefert auf `today=2026-04-25` das Jahr **2025**. Die Initial-Trigger-Smokes haben jeweils erfolgreich durchgelaufen (`LastTaskResult=0`), also sind die 2025er-Assets verfuegbar. Trotzdem hilfreich vor T3.0-Start: einmal `pytest -m network` mit `PINNED_SMOKE_SEASON=2025` (oder als zusaetzlicher Test-Lauf) als Live-Confirmation.
- **234 trade events in Saison 2024** aus dem T3.1S-VPS-Re-Smoke sind hoeher als die ~50 echten NFL-Trades pro Saison — ADR-0032-Heuristik klassifiziert konservativ practice-squad-Wechsel als `trade`. Nicht T3.1-blockierend; ADR-0032-Validierung gegen echte 2025er-Trade-Liste ist explizit als T3.0-DoD-Item gefuehrt.
- **ADR-0030/0032 sind weiterhin `Proposed`.** Flip auf `Accepted` ist Teil des T3.0-Closers.

## Aktueller Arbeitsstand

- **Phase:** T3.1 final (alle drei Bolzen durch, alle 8 Scheduled Tasks `LastTaskResult=0`). Beobachtungs-Fenster bis 2026-04-27. Naechste Tranche: T3.0 Testphase auf VPS, Juli 2026.
- **Git-Stand:** `main` bei einem T3.1-Closer-Commit (folgt). Origin sync. VPS bei `5a9e54c`. Working-Tree nach Closer-Commit sauber.
- **Tests:** **490 gruen** (445 v1.0 + 17 URL-Drift + 12 T3.1S + 16 Deployment), 8 deselected (`@pytest.mark.network`-Smokes). Laufzeit ~8:31 auf DEV-LAPTOP.
- **Ruff:** 44 Errors, Delta -1 gegenueber Baseline 45 (alle pre-existing UP035/UP037/E501/I001/B905/UP012/E741, keine neue Regression).
- **AST-Lint:** gruen.
- **VPS-Status:** `C:\newNFL` auf `5a9e54c`, Python 3.12 Venv aktiv. 8 Scheduled Tasks aktiv mit `LastTaskResult=0`. `data/raw/landed/...`-Tree wuchst durch heutige Initial-Trigger-Smokes (3 fetch-receipt-Triplets pro Slice). DuckDB-Tabellen (`core.team`, `core.game`, `core.player`, `core.roster_membership`, `core.team_stats_weekly`, `core.player_stats_weekly` plus Marts) gefuellt.
- **Letzter erfolgreicher Pflichtpfad:** Full-Suite gruen auf DEV-LAPTOP; Ruff Delta ≤ 0; AST-Lint gruen; alle 8 Scheduled Tasks auf VPS `LastTaskResult=0`.
- **Naechster konkreter Schritt:** **T3.0 Testphase planen + starten.** Vorbereitend: 2-Tage-Beobachtung abwarten, Backup-End-to-End-Drill durchspielen, dann T3.0-Plan-Update + erste T3.0-Bolzen.

## Geaenderte / neue Dokumente in dieser Session

- Neu (Code): [src/new_nfl/adapters/column_aliases.py](../../src/new_nfl/adapters/column_aliases.py).
- Neu (Code): [deploy/windows-vps/vps_install_tasks_step2.ps1](../../deploy/windows-vps/vps_install_tasks_step2.ps1).
- Neu (Tests): [tests/test_column_aliases.py](../../tests/test_column_aliases.py), [tests/test_slices_network_smoke.py](../../tests/test_slices_network_smoke.py), [tests/test_deploy_scripts.py](../../tests/test_deploy_scripts.py).
- Neu (Handoffs): [docs/_handoff/chat_handoff_20260425-1700_t31s-schema-drift-done.md](chat_handoff_20260425-1700_t31s-schema-drift-done.md), dieses Handoff-Dokument.
- Geaendert (Code): [src/new_nfl/core/players.py](../../src/new_nfl/core/players.py), [src/new_nfl/core/rosters.py](../../src/new_nfl/core/rosters.py), [src/new_nfl/core/team_stats.py](../../src/new_nfl/core/team_stats.py) — Alias-Helper-Aufruf.
- Geaendert (Konfig): [pyproject.toml](../../pyproject.toml) — `network`-Marker registriert.
- Geaendert: [docs/PROJECT_STATE.md](../PROJECT_STATE.md) (Phase, Completed, Current cycle, Preferred next bolt).
- Geaendert: [docs/T2_3_PLAN.md](../T2_3_PLAN.md) §10 (Header), §10.1 (T3.1S erledigt), §10.2 (Step 2 erledigt + Operator-Closer-Beleg).
- Geaendert: [docs/LESSONS_LEARNED.md](../LESSONS_LEARNED.md) (2026-04-24-Eintrag auf `accepted`).
- Geaendert: [docs/_ops/releases/v1.0.0-laptop.md](../_ops/releases/v1.0.0-laptop.md) §5 (Restrisiken #9 + #10 als adressiert / geschlossen).
- Memory-Update: [memory/feedback_delivery.md](../../../../Users/andre/.claude/projects/c--projekte-newnfl/memory/feedback_delivery.md) — Praezisierung Ausfuehrungsort-Prefix + PS 5.1 ohne `&&`.

## Lessons-Learned-Eintrag

Kein eigener T3.1-final-Eintrag. Die 2026-04-24-Lesson („T3.1 VPS-Smoke entdeckt URL-Drift UND Schema-Drift bei nflverse") deckt die T3.1-Befunde + Methodaenderungen ab und ist mit T3.1S-Folgeumsetzung-Block + VPS-Re-Smoke-Beleg auf `accepted` geflippt.

Eine sekundaere Methodbeobachtung wurde in [memory/feedback_delivery.md](../../../../Users/andre/.claude/projects/c--projekte-newnfl/memory/feedback_delivery.md) als feedback-memory persistiert: Ausfuehrungsort-Prefix gehoert ausserhalb des Code-Blocks; PowerShell 5.1 hat kein `&&` als Statement-Separator. Beide Punkte fanden in T3.1 statt; sind operationell relevant fuer kuenftige Sessions, aber zu klein fuer einen eigenen Lesson-Eintrag.

Beobachtung fuer T3.0: der iterative Rollout hat sich als Tranche-Strategie bestaetigt — Step 1 (1 Slice) als Smoke, T3.1S als Drift-Fix, Step 2 (6 Slices) als Voll-Rollout. Big-Bang waere nach den 2026-04-24-Befunden riskant gewesen. Diese Beobachtung wandert in den T3.0-Plan, wenn sie fuer die 4-Wochen-Phase Konsequenzen hat.

## Starter-Prompt fuer die neue Session

```text
Du uebernimmst das Projekt **NEW NFL** — ein privates, single-operator-
betriebenes NFL-Daten- und Analysesystem. Arbeitssprache Deutsch. Der
Operator (Andreas) arbeitet allein, ohne Team, ohne externe Abnahme.

**Repo:**
- lokal: c:\projekte\newnfl (Haupt-Checkout, branch `main`)
- remote: https://github.com/andreaskeis77/new_nfl
- Git-Tag `v1.0.0-laptop` auf `main` (2026-04-24).
- HEAD nach T3.1 final: T3.1-Closer-Commit (folgt im naechsten Handoff-Push).

**Zielkorridor:**
- v1.0 feature-complete: ✅ erreicht 2026-04-24.
- T3.1 VPS-Migration: ✅ final 2026-04-25.
  - Step 1 (Bootstrap + URL-Drift-Fix): ✅
  - T3.1S (Schema-Drift-Fix + Network-Marker): ✅
  - Step 2 (sechs zusaetzliche Fetch-Tasks + Operator-Closer): ✅
  - 2-Tage-Beobachtungsfenster: laeuft bis 2026-04-27.
- **T3.0 Testphase auf VPS** = naechste Tranche, Juli 2026 oder frueher.
- Produktiv (Tailscale-only, Port 8001): vor NFL-Preseason Anfang August 2026.

---

## Pflichtlektuere vor T3.0-Start (in dieser Reihenfolge)

1. **docs/PROJECT_STATE.md** — Current phase + Current cycle = T3.1 final.
2. **docs/_handoff/chat_handoff_20260425-2330_t31-final.md** — dieser Handoff.
3. **docs/T2_3_PLAN.md §9** — T3.0-Scope (4 Wochen Scheduler-Lauf, Designed Degradation, Backfill-Lasttest, ADR-0030/0032-Flips).
4. **docs/USE_CASE_VALIDATION_v0_1.md §2.3** — Definition v1.0 (T3.0 erfuellt das fuenfte Kriterium "Backup/Restore + Replay real getestet" abschliessend).
5. **docs/LESSONS_LEARNED.md** Eintrag 2026-04-24 (`accepted`) — Methodaenderungen, die in T3.0 weiterhin gelten.
6. **docs/adr/README.md** — ADR-0030 + ADR-0032 sind weiterhin `Proposed`; T3.0 ist die Flip-Phase.
7. **docs/ENGINEERING_MANIFEST.md** oder **ENGINEERING_MANIFEST_v1_3.md** (Draft).
8. **docs/CHAT_HANDOFF_PROTOCOL.md** + **docs/LESSONS_LEARNED_PROTOCOL.md**.

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
- Tests pro neues Feature hart: Full-Suite gruen. Aktueller Stand: **490 Tests gruen, 8 deselected (network) in ~8:31 auf DEV-LAPTOP**.
- Ruff-Delta <= 0 gegenueber Baseline 45 (aktuell 44, also Delta -1).
- PowerShell-Dateien (`*.ps1`): **ASCII-only**, kein `&&`/`||` als Statement-Separator. tests/test_deploy_scripts.py ist das Gate.

**Ausfuehrungsort:**
- Befehle mit Prefix kennzeichnen: `DEV-LAPTOP $`, `VPS-ADMIN PS>`, `VPS-USER PS>`. Prefix steht **ausserhalb** des Code-Blocks (als Bold-Label oder Satzeinleitung), nie im Code-Block selbst.
- Mehrere Befehle pro Operator-Schritt nicht via `&&` chainen — eigene Zeilen oder eigene Code-Bloecke.

**Parallel-Entwicklung:**
- Worktree-Pflicht bei ≥2 parallelen Streams.

**Protokoll-Pflichten:**
- Am Bolt-Ende Chat-Handoff proaktiv vorschlagen (§2.1).
- Lessons-Draft bei Ueberraschungen sofort anlegen.
- PROJECT_STATE, T2_3_PLAN, ADR-Index nach relevanten Entscheidungen aktualisieren.

---

## T3.0 — konkreter Scope-Vorschlag (zu schaerfen vor Start)

**Phase 1 (Tag 1–7): passive Beobachtung.** Cron-Belegung laeuft taeglich 04:00–06:30 ohne weitere Code-Aenderungen. Tag 7 Status-Inspektion:
- `Get-ScheduledTask -TaskName NewNFL-* | Get-ScheduledTaskInfo` — alle `LastTaskResult=0` ueber 7 Tage?
- `meta.run_event severity in ('error','critical','fatal')` ueber CLI / Web-UI durchgehen.
- Optionaler T3.0A-Bolt fuer Bugfixes, falls etwas auffaellt.

**Phase 2 (Tag 8–14): Designed Degradation.** Operator faehrt bewusste Quell-Ausfaelle:
- Eine `remote_url` per Override auf 404 setzen → Quarantaene-Hook muss `meta.quarantine_case` oeffnen, Task `LastTaskResult != 0`, kein Crash der Cron-Belegung.
- DuckDB-Lock-Konflikt simulieren (parallel `new-nfl ...`-Aufruf waehrend Backup) → erwarteter sauberer Retry-Pfad.

**Phase 3 (Tag 15–21): Backfill-Lasttest.** Per-season-Slices ueber ~15 Saisons (z. B. 2010–2024) mit Operator-Override-Loop:
- Skript-Wrapper: fuer jedes `season in 2010..2024`: `run_slice.ps1 -Slice rosters -Season <season>`, `team_stats_weekly`, `player_stats_weekly`.
- Beobachten: DuckDB-Groesse, Mart-Rebuild-Latenz, `meta.run_event`-Anzahl. T3.0E-Risiko-Eintrag aus T2_3_PLAN.md §11 ist hier der Auslese-Trigger.

**Phase 4 (Tag 22–28): ADR-Flips + DoD-Closer.**
- ADR-0032 (Bitemporale Roster-Modellierung): Operator vergleicht Trade-Events aus `meta.roster_event` gegen oeffentliche NFL-Trade-Liste 2024/2025. Bei akzeptabler Trefferrate Flip auf `Accepted`.
- ADR-0030 (UI-Stack Jinja+Tailwind+htmx+Plot): Lasttest-Feedback aus den Phase-1-3-Beobachtungen → Flip auf `Accepted` oder gezielte Nachbesserung.
- Backup-End-to-End-Drill: einmal `backup-snapshot` → `verify-snapshot` → Test-`restore-snapshot` in temporaerem Verzeichnis.
- Definition-v1.0-Matrix Kriterium 5 final auf `✅`.

**T3.0-DoD:** 4 Wochen ununterbrochener Scheduler-Lauf ohne ungeloeste Quarantaene-Eskalation; ADR-0030 + ADR-0032 auf `Accepted`; Backup-Drill durchgespielt.

---

## Eskalations-Hinweise

- **Tag-1-Beobachtung 2026-04-26 zeigt rote Tasks** → sofort `Get-ScheduledTaskInfo -TaskName <x>` + `data/logs/events_<heute>.jsonl`-Auszug; T3.0-Start verschiebt sich um T3.0-Hotfix-Tranche.
- **T3.0-Backfill sprengt DuckDB > 5 GB oder Mart-Rebuild > 60s** → T2_3_PLAN.md §11-Risiko-Eintrag aktivieren (Schema-Cache hilft, Mart-Partitionierung als Folge-Arbeit).
- **Unklare Architektur-Entscheidung** → concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md + ADR-Index, dann Operator fragen.
- **Unerwarteter VPS-Zustand** → **nicht loeschen**, Operator fragen.

---

## Arbeitsauftrag fuer diese Session

1. Lies die Pflichtlektuere komplett (mindestens Dokumente 1–4 der Liste).
2. Bestaetige Verstaendnis in **5 Bullets**:
   - Wo stehen wir (T3.1 final, alle 8 Tasks `LastTaskResult=0`, 2-Tage-Fenster laeuft)?
   - Was ist T3.0 Phase 1–4 grob?
   - Welche zwei ADRs sind die T3.0-Flip-Kandidaten?
   - Welche Pflichtpfade (Test-Gate, Ruff-Delta, AST-Lint, ASCII-PS1, kein `&&`)?
   - Welche Phase-1-Beobachtung steht heute / in den naechsten 24 h an?
3. Operator-Freigabe einholen fuer den ersten T3.0-Schritt (z. B. T3.0-Plan-Schaerfung als Edit, oder erst Beobachtungs-Fenster komplett abwarten).
4. Bei Ueberraschungen Lesson-Draft anlegen.
```
