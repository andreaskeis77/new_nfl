# Chat-Handoff 2026-04-24 23:00 — T3.1 Step 1 auf VPS abgeschlossen, Schema-Drift offen als T3.1S

## Trigger

§2.1 **Kontext-Druck + Major-Milestone + Lessons-würdige Überraschungen:** Die Session hat 9 Commits gepusht, einen großen Refactor (URL-Drift-Fix mit `remote_url_template` in 6 Files + 17 neuen Tests), eine Lesson geschrieben und mehrfach Scope-Gespräche geführt. T3.1 Step 1 auf VPS ist mechanisch durch; das Folgeproblem (Core-Loader-Schema-Drift) ist thematisch abgrenzbar und wird in einem eigenen Bolt T3.1S bearbeitet. Natürlicher Sitzungsschnitt.

## Was wurde in dieser Session erreicht

- **[ADR-0034](../adr/ADR-0034-vps-first-before-testphase.md) gesetzt:** T3.1 VPS-Migration zieht gegenüber dem Original-Plan **vor** T3.0 Testphase. Grund: DEV-LAPTOP läuft nicht always-on, 4-Wochen-Scheduler-Test ist dort nicht nachweisbar. Der bereits fürs `capsule`-Projekt eingerichtete Contabo-VPS übernimmt von Anfang an als Ziel-Umgebung. NEW NFL nutzt Tailscale-only (kein Cloudflare), Port 8001 (capsule belegt 8000), Task-Präfix `NewNFL-*` (getrennt von `Capsule-*`).
- **VPS-Dokumentation** unter `docs/_ops/vps/`:
  - [VPS_DOSSIER.md](../_ops/vps/VPS_DOSSIER.md) — Konventionen (Pfade, Ports, Task-Namen, Backup, Koexistenz zu capsule).
  - [VPS_DEPLOYMENT_RUNBOOK.md](../_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md) — Schritt-für-Schritt mit `DEV-LAPTOP $` und `VPS-ADMIN PS>`-Prefix, ausführlich für Inventarisierung (Phase 3) und Bootstrap (Phase 4).
- **Deployment-Skripte** unter `deploy/windows-vps/`:
  - `vps_bootstrap.ps1` — idempotent, Python 3.12 via `py -3.12`, Venv + editable-Install + `bootstrap` + `seed-sources` + `registry-list`-Smoke.
  - `run_backup.ps1` — Wrapper für `backup-snapshot` mit Zeitstempel-ZIP-Name und JSONL-Log.
  - `run_slice.ps1` — Wrapper für fetch → stage → core pro Slice, optionaler `-Season`-Parameter für per-season-Slices.
  - `vps_install_tasks.ps1` — iterativer Step 1: legt nur `NewNFL-Backup-Daily` (04:00) und `NewNFL-Fetch-Teams` (05:00) an.
- **VPS-Provisionierung abgeschlossen:** Inventarisierung erfolgreich (Python 3.12 + 3.14 verfügbar, Git 2.53, ~178 GB frei, Tailscale-IP `100.71.205.5`, Hostname `vmd193069`, Admin-User `srv-ops-admin`). Bootstrap-Skript in einem Durchlauf grün (nach ASCII-Fix im Em-Dash-Bug und Dev-Extras-Ergänzung). Full-Suite **445 Tests grün auf VPS in 13:05** (DEV-LAPTOP: 9:11) — Parität beim Code-Stand bewiesen.
- **URL-Drift-Fix (ADR-0034-Folge-Refactor):** `SliceSpec.remote_url_template: str = ""` als additives Feld, `resolve_remote_url(spec, season=None, today=None)`-Helper, `default_nfl_season(today)`-Helper (Sep–Dez → current year; Jan–Feb → year-1; Mar–Aug → year-1). 3 Slice-URLs umgezogen auf `nflverse-data/releases/...`, 3 Slices auf Per-Season-Templates. `--season` als neuer optionaler CLI-Parameter an `fetch-remote`. `run_slice.ps1 -Season` durchgereicht. 17 neue Unit-Tests (`test_slices_url_resolution.py`) decken beide Helper und Registry-Integration ab. Full-Suite **462 Tests grün**. Ruff-Delta **-1** gegenüber Baseline 45.
- **Scheduled-Tasks Step 1 aktiv:** `NewNFL-Backup-Daily` (04:00) und `NewNFL-Fetch-Teams` (05:00) via `vps_install_tasks.ps1` angelegt. `Fetch-Teams` einmal manuell getriggert → `LastTaskResult=0` ✓.
- **Slice-Smoke 7/7 getestet:** 4 grün (`teams`, `games`, `schedule_field_dictionary`, `player_stats_weekly`), 3 mit Schema-Drift (`players`, `rosters`, `team_stats_weekly`).
- **Lesson angelegt** (Status `draft`): 2026-04-24-Eintrag in [LESSONS_LEARNED.md](../LESSONS_LEARNED.md) dokumentiert URL-Drift und Schema-Drift, Root-Cause „v1.0 hatte keinen E2E-HTTP-Smoke", fünf konkrete Methodänderungen (neues Definition-v1.0-Kriterium #6, Pin-Strategie, nachträgliches Restrisiko, Plan-Konsistenz-Check, Refactor-Schätzung).
- **Restrisiko-Nachtrag:** [v1.0.0-laptop.md §5](../_ops/releases/v1.0.0-laptop.md) um Punkt **#9 URL-Drift** und **#10 Schema-Drift** ergänzt.
- **9 Commits auf `main` gepusht** (2a4adab…f0e8d13).

## Was ist offen / unklar / Risiko

- **T3.1S — Core-Loader-Schema-Drift-Fix.** Siehe [T2_3_PLAN.md §10.1](../T2_3_PLAN.md). `player_id` → `gsis_id` in `core/players.py` und `core/rosters.py`; `team_id` → `team` in `core/rosters.py` und `core/team_stats.py`. `core/player_stats.py` ist nicht betroffen (akzeptiert bereits die neuen Namen). Empfehlung beim Session-Start: zentrale Column-Alias-Registry (Option B in §10.1) statt pro-Loader-Parameter.
- **Neue Test-Kategorie `@pytest.mark.network`:** als Lesson-Konsequenz soll T3.1S einen E2E-HTTP-Smoke pro Primary-Slice gegen die echten `nflverse-data/releases/…`-URLs einführen, via Pytest-Marker selektierbar. Default ohne den Marker für CI-Disziplin, separat ausführbar `pytest -m network`.
- **Backup-Task selbst noch nie ausgeführt** (`LastTaskResult=267011` = `SCHED_S_TASK_HAS_NOT_RUN`, kein Fehler). Morgen 04:00 triggert automatisch; alternativ manuell: `Start-ScheduledTask -TaskName NewNFL-Backup-Daily`.
- **Step 2 iterativer Rollout:** nach T3.1S die restlichen 6 Fetch-Tasks installieren. Siehe [T2_3_PLAN.md §10.2](../T2_3_PLAN.md).
- **Lesson-Freigabe:** Eintrag vom 2026-04-24 in LESSONS_LEARNED.md steht auf `draft`. Nach T3.1S auf `accepted` flippen (oder Abschnitt im gleichen Atemzug erweitern).
- **Dokumentations-Restarbeit aus Lesson-Methodänderungen:** neues Kriterium #6 in [USE_CASE_VALIDATION_v0_1.md §2.3](../USE_CASE_VALIDATION_v0_1.md) und [RELEASE_PROCESS.md §5](../RELEASE_PROCESS.md) ergänzen. Ebenfalls: Pin-Strategie-Regel ins [ENGINEERING_MANIFEST.md](../ENGINEERING_MANIFEST.md) (Draft v1.3 oder neuer ADR). Nicht T3.1S-blockierend, aber vor T3.0 fällig.
- **Wert von `remote_url` in `meta.adapter_slice`:** für Template-Slices projiziert die Sync-Funktion jetzt den Template-String mit `{season}`-Platzhalter. `list-slices`-CLI zeigt den Platzhalter. Ist informativ OK, könnte aber später um eine eigene Spalte verbessert werden (nicht v1.0-Scope).

## Aktueller Arbeitsstand

- **Phase:** T3.1 Step 1 abgeschlossen, T3.1S offen. T3.0 Testphase folgt nach T3.1-Abschluss (also nach T3.1S + Step 2) im Juli 2026.
- **Git-Stand:** `main` bei `f0e8d13`, sauber gepusht. Working-Tree nach Handoff-Commit sauber.
- **Tests:** **462 grün** (445 aus v1.0-Cut + 17 neu aus URL-Drift-Fix). Laufzeit ~9:21 auf DEV-LAPTOP, ~13:05 auf VPS.
- **Ruff:** 44 Errors, Delta **-1** gegenüber Baseline 45.
- **AST-Lint:** grün (unverändert).
- **VPS-Status:** läuft, Python 3.12 Venv unter `C:\newNFL\.venv`, `meta.source_registry` gesät (4 Sources), `core.team` (32) und `core.game` (7276) und `core.schedule_field_dictionary` (45) und `core.player_stats_weekly` (19399) + 3 Marts gefüllt. Scheduled Tasks `NewNFL-Backup-Daily` + `NewNFL-Fetch-Teams` aktiv.
- **Letzter erfolgreicher Pflichtpfad:** Full-Suite grün auf DEV-LAPTOP und VPS; Ruff Delta ≤ 0; AST-Lint grün; `run_slice.ps1 -Slice teams` auf VPS grün; `NewNFL-Fetch-Teams`-Task `LastTaskResult=0`.
- **Nächster konkreter Schritt:** **T3.1S starten** — Column-Alias-Registry entwerfen, 3 Core-Loader anpassen, Tests + E2E-Network-Smokes hinzu, alle 7 Slices auf VPS re-smoken.

## Geänderte / neue Dokumente in dieser Session

- Neu: [docs/adr/ADR-0034-vps-first-before-testphase.md](../adr/ADR-0034-vps-first-before-testphase.md).
- Neu: [docs/_ops/vps/VPS_DOSSIER.md](../_ops/vps/VPS_DOSSIER.md), [docs/_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md](../_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md).
- Neu: `deploy/windows-vps/vps_bootstrap.ps1`, `run_slice.ps1`, `run_backup.ps1`, `vps_install_tasks.ps1`.
- Neu: [tests/test_slices_url_resolution.py](../../tests/test_slices_url_resolution.py) — 17 Unit-Tests.
- Neu: dieses Handoff-Dokument.
- Geändert: [docs/adr/README.md](../adr/README.md) (ADR-0034 am Kopf der Tabelle).
- Geändert: [docs/T2_3_PLAN.md](../T2_3_PLAN.md) §1, §9 (T3.0A auf VPS), §10 (T3.1 Scope + Fortschritt + neue §10.1 T3.1S + §10.2 Step 2).
- Geändert: [docs/PROJECT_STATE.md](../PROJECT_STATE.md) (Current cycle, Current release posture, Preferred next bolt — alle auf T3.1S-Scope geflippt).
- Geändert: [docs/_ops/releases/v1.0.0-laptop.md](../_ops/releases/v1.0.0-laptop.md) §5 (neue Restrisiken #9 URL-Drift, #10 Schema-Drift).
- Geändert: [docs/LESSONS_LEARNED.md](../LESSONS_LEARNED.md) (neuer Eintrag 2026-04-24, `draft`).
- Geändert (Code): `src/new_nfl/adapters/slices.py` (vollständig umgeschrieben — neues Feld, Helpers, URL-Daten), `src/new_nfl/adapters/remote_fetch.py`, `src/new_nfl/cli.py`, `src/new_nfl/jobs/runner.py`, `src/new_nfl/meta/adapter_slice_registry.py`.

## Lessons-Learned-Eintrag

Siehe [LESSONS_LEARNED.md](../LESSONS_LEARNED.md), Eintrag „2026-04-24 — T3.1 VPS-Smoke entdeckt URL-Drift UND Schema-Drift bei nflverse; v1.0-Cut hat E2E-Fetch-Smoke vermisst". Status `draft`, wartet auf Operator-Freigabe. Nach T3.1S-Abschluss geeignete Erweiterung oder Flip auf `accepted`.

## Starter-Prompt für die neue Session

```text
Du uebernimmst das Projekt **NEW NFL** — ein privates, single-operator-
betriebenes NFL-Daten- und Analysesystem. Arbeitssprache Deutsch. Der
Operator (Andreas) arbeitet allein, ohne Team, ohne externe Abnahme.

**Repo:**
- lokal: c:\projekte\newnfl (Haupt-Checkout, branch `main`)
- remote: https://github.com/andreaskeis77/new_nfl
- Git-Tag `v1.0.0-laptop` auf `main` (2026-04-24) markiert den v1.0-Cut.
- HEAD nach T3.1 Step 1: Commit `f0e8d13` (URL-Drift-Fix).

**Zielkorridor:**
- v1.0 feature-complete: ✅ erreicht 2026-04-24 (Tag `v1.0.0-laptop`).
- T3.1 VPS-Migration **vorgezogen vor T3.0** (siehe [ADR-0034](../adr/ADR-0034-vps-first-before-testphase.md)). Zielfenster Juni-Ende / Anfang Juli 2026.
  - Step 1 ✅ erledigt.
  - **T3.1S Core-Loader-Schema-Drift-Fix** offen → das ist dein naechster Bolt.
  - Step 2 (restliche 6 Fetch-Tasks) nach T3.1S.
- T3.0 Testphase auf VPS: Juli 2026, nach T3.1-Abschluss.
- Produktiv (Windows-VPS, Contabo, Tailscale-only): vor NFL-Preseason Anfang August 2026.

---

## Pflichtlektuere vor dem T3.1S-Start (in dieser Reihenfolge)

1. **docs/PROJECT_STATE.md** — Current cycle zeigt T3.1S als Preferred next bolt.
2. **docs/_handoff/chat_handoff_20260424-2300_t31-step1-schema-drift.md** — dieser Handoff, vollstaendige Session-Uebersicht.
3. **docs/T2_3_PLAN.md §10.1** — T3.1S-Scope-Definition mit Option A vs. B (Alias-Registry empfohlen) und DoD.
4. **docs/LESSONS_LEARNED.md** oberster Eintrag 2026-04-24 — status `draft`, inkl. Methodaenderung „E2E-HTTP-Smoke fehlt" die T3.1S umsetzen muss.
5. **docs/_ops/releases/v1.0.0-laptop.md §5** — Restrisiken #9 (URL-Drift) und #10 (Schema-Drift) als Zielzustand.
6. **docs/adr/ADR-0034-vps-first-before-testphase.md** — warum T3.1 vor T3.0.
7. **docs/_ops/vps/VPS_DOSSIER.md** + **docs/_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md** — Konventionen + Runbook (falls Operator etwas auf VPS pruefen will).
8. **docs/ENGINEERING_MANIFEST.md** oder **ENGINEERING_MANIFEST_v1_3.md** (Draft) — verbindliche Engineering-Regeln.
9. **docs/concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md** — Architektur-Anker bei Bedarf.
10. **docs/CHAT_HANDOFF_PROTOCOL.md** + **docs/LESSONS_LEARNED_PROTOCOL.md** — Protokoll-Pflichten am Session-Ende.

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
- Neue Mart-Builder tragen `@register_mart_builder`-Decorator (`src/new_nfl/mart/_registry.py`).
- Tests pro neues Feature hart: Full-Suite gruen. Aktueller Stand: **462 Tests gruen in ~9:21 auf DEV-LAPTOP**.
- Ruff-Delta <= 0 gegenueber Baseline 45 (aktuell 44, also Delta -1).
- PowerShell-Dateien (`*.ps1`): **ASCII-only** — keine Em-Dashes/Umlaute. Windows-PowerShell 5.1 liest UTF-8 ohne BOM als CP1252 und scheitert am Parser. Siehe Commit `3c15751` fuer die Erfahrung.

**Ausfuehrungsort:**
- Befehle mit Prefix kennzeichnen: `DEV-LAPTOP $`, `VPS-ADMIN PS>` (Admin-PowerShell auf VPS), `VPS-USER PS>`.

**Parallel-Entwicklung:**
- Worktree-Pflicht bei ≥2 parallelen Streams (siehe PARALLEL_DEVELOPMENT.md T2.7-Retro).

**Protokoll-Pflichten:**
- Am Bolt-Ende (also nach T3.1S) Chat-Handoff proaktiv vorschlagen (§2.1).
- Lessons-Draft bei Ueberraschungen sofort anlegen.
- PROJECT_STATE, T2_3_PLAN, ADR-Index nach relevanten Entscheidungen aktualisieren.
- Memory-System unter `C:\Users\andre\.claude\projects\c--projekte-newnfl\memory\` nutzen.

---

## T3.1S — konkreter Scope (gemaess T2_3_PLAN.md §10.1)

**Problem:** drei per-season-Slices scheitern am Core-Load-Gate:
- `players`: Spalte `player_id` fehlt (nflverse liefert `gsis_id`).
- `rosters`: Spalten `player_id` (`gsis_id`) und `team_id` (`team`) fehlen.
- `team_stats_weekly`: Spalte `team_id` fehlt (nflverse liefert `team`).

`core/player_stats.py` ist nicht betroffen (akzeptiert bereits `team`; `player_id` ist im aktuellen File vorhanden).

**Design-Empfehlung (Option B aus §10.1):** zentrale Column-Alias-Registry unter `src/new_nfl/adapters/column_aliases.py`. Ein dict `{(slice_key) -> {nflverse_name: canonical_name}}`. Jeder Core-Loader liest die Registry ueber einen Helper `apply_column_aliases(df, slice_key)` oder setzt vor `_assert_required_columns` einen `RENAME`-Schritt. Vorteil: Single-Point-of-Truth, zukuenftige Drifts = 1-Zeilen-Registry-Eintrag.

**Neu als Lesson-Konsequenz:** `@pytest.mark.network`-Marker fuer E2E-HTTP-Smokes einfuehren:
```python
@pytest.mark.network
def test_nflverse_teams_live_url():
    ...
```
Default-Pytest-Run ignoriert den Marker; separat `pytest -m network` fuer Operator-validieren vor Release. Ziel: alle 7 Primary-Slices in einem Sweep gegen echte URLs pruefen.

**DoD T3.1S:**
- Alle 7 Primary-Slices laufen `run_slice.ps1 -Slice <key>` auf VPS gruen bis `=== DONE ===`.
- Full-Suite weiterhin gruen (462 + neue Tests).
- Ruff-Delta <= 0.
- Lesson 2026-04-24 entweder um T3.1S-Befund erweitert oder auf `accepted` geflippt.

**Pflicht vor erstem Code-Aenderungs-Schritt:** Pflichtlektuere lesen, Verstaendnis in 5 Bullets bestaetigen, Operator-Freigabe fuer Option A oder Option B einholen.

---

## Eskalations-Hinweise

- **Code-Regression vermutet** → Full-Suite `pytest -v` + Ruff gegen Stand `f0e8d13` vergleichen.
- **Unklare Architektur-Entscheidung** → concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md + ADR-Index, dann Operator fragen.
- **Unklare Prioritaet** → T2_3_PLAN.md §10.1 (T3.1S) ist die verbindliche Sequenz.
- **Unerwarteter VPS-Zustand** → **nicht loeschen**, Operator fragen. T2.7-Lesson gilt weiter.

---

## Arbeitsauftrag fuer diese Session

1. Lies die Pflichtlektuere komplett (mindestens Dokumente 1–5 der Liste).
2. Bestaetige Verstaendnis in **5 Bullets**:
   - Wo stehen wir (T3.1 Step 1 done, T3.1S offen, Test-Count, Slice-Gruen-Status)?
   - Was ist T3.1S (betroffene Loader + Column-Aliases)?
   - Welche Design-Option fuer Alias-Strategie (A vs. B) und warum?
   - Welche Pflichtpfade (Test-Gate, Ruff-Delta, AST-Lint, ASCII-only-PS1)?
   - Welche neue Lesson-Konsequenz muss als Test eingebaut werden?
3. Operator-Freigabe fuer konkreten T3.1S-Start einholen. Kein Blind-Code.
4. Nach T3.1S-Abschluss: Handoff-Vorschlag proaktiv + Lesson-Update-Vorschlag.
```
