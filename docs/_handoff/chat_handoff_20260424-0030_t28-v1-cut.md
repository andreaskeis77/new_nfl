# Chat-Handoff 2026-04-24 00:30 — T2.8 v1.0 Cut auf DEV-LAPTOP abgeschlossen → Einstieg T3.0 Testphase

## Trigger

§2.1 "Ende einer Tranche / eines Bolt": **T2.8 v1.0 Cut auf DEV-LAPTOP ist abgeschlossen.** Damit schließt sich die T2.x-Entwicklungsphase (Foundation Hardening → Ontology Runtime → Domain Expansion → Web-UI v1.0 → Resilienz/Observability → v1.0-Cut). Nächster Zyklus ist **T3.0 Testphase**, fachlich eine qualitativ andere Arbeit — 4 Wochen Operator-Validation gegen echte Daten, nicht länger Feature-Entwicklung.

## Was wurde in dieser Session erreicht

- **T2.7F-Integrations-State verifiziert**: Commits `50d2652` (T2.7A-F Lessons-Konsolidierung + State-Update + Handoff) und `bcc5cc3` (PARALLEL_DEVELOPMENT — T2.7-Retro-Box) sauber gepusht, lokal clean.
- **Feature-Branches aufgeräumt**: `feature/t27-observability`, `feature/t27-resilience`, `feature/t27-hardening` lokal + origin gelöscht (alle gemerged).
- **Memory-Update**: `project_parallel_streams_shared_workdir.md` von Type `project` auf `feedback` geflippt mit Regel "Bei paralleler Multi-Stream-Entwicklung startet jeder Stream mit `git worktree add c:/projekte/newnfl.wt/<stream>`. Keine Branch-Flips im Haupt-Checkout." — begründet durch T2.7-Retro-Beobachtungen (mehrfach überschriebene `plugins/__init__.py`, zwei Commits auf falscher Branch durch externe Checkouts, Stream-C-Edits in Stream-A-Files).
- **PARALLEL_DEVELOPMENT.md Retro-Block**: Status von "Entwurf" auf "Referenz-Dokument — T2.7 abgeschlossen 2026-04-23" geflippt mit Notiz, dass Worktree-Strategie in T2.7 de facto NICHT implementiert war und ab nächster paralleler Tranche Pflicht ist.
- **Release-Evidence `docs/_ops/releases/v1.0.0-laptop.md`** gemäß RELEASE_PROCESS.md §5 geschrieben: Zweck, Definition-v1.0-Matrix (4/5 erfüllt, Backup/Restore-Validation nach T3.0 verschoben), betroffene Dateien, Gate-Ergebnisse, 8 bekannte Restrisiken, nächster Schritt T3.0, Referenzen, Artefakt-Manifest. Self-declared als die *einzige* kanonische Release-Evidence für `v1.0.0-laptop` — kein separates Release-Notes-Dokument im Repo-Root.
- **PROJECT_STATE.md** Phase-Header geflippt von "T2.7 vollständig integriert" auf "v1.0 feature-complete auf DEV-LAPTOP — T2.8 v1.0 Cut abgeschlossen"; T2.8-Eintrag als erster Punkt in Completed-Liste; "Current release posture" komplett neu geschrieben ("v1.0 feature-complete on DEV-LAPTOP"); "Current cycle" auf T2.8 abgeschlossen / T3.0 anstehend; "Preferred next bolt" auf T3.0 Testphase mit parallelen ADR-Flips.
- **T2_3_PLAN.md** T2.8-Sektion §7 von Planungs-Text auf "✅ abgeschlossen 2026-04-24" geflippt mit Definition-v1.0-Matrix, Gate-Summary und Restrisiken; Kalenderfenster-Tabelle in §1 flippt T2.7 + T2.8 beide auf ✅.
- **Git-Tag `v1.0.0-laptop`** auf dem finalen T2.8-Commit gesetzt und gepusht.

## Was ist offen / unklar / Risiko

- **ADR-0030 (UI Tech Stack: Jinja + Tailwind + htmx + Plot)** bleibt `Proposed`. Implementierung seit T2.6A live und stabil; Status-Flip auf T3.0 verschoben, damit reales Lasttest-Feedback einfließt statt premature Acceptance.
- **ADR-0032 (Bitemporale Roster-Modellierung)** bleibt `Proposed`. Trade-/Release-Heuristik in T2.5D implementiert und unit-test-validiert, aber nicht gegen echte NFL-Trades produktions-validiert — T3.0 soll das Gate liefern.
- **Backup/Restore/Replay-Drill** mechanisch ausgeliefert (37 Tests), Operator-Validation gegen gewachsene DB bewusst nach T3.0 verschoben. Das ist das einzige nicht-✅-Kriterium in der Definition-v1.0-Matrix.
- **Ruff-Baseline 45 Errors** auf `main` (UP035/UP037/E501/I001/B905/UP012/E741) aus Ruff-0.15.10-Rule-Drift, Delta 0 gegenüber Baseline. T3.0-Aufräum-Bolzen optional.
- **HTTP-Mirror für Health-Probes deferred** bis echter Web-Router landet (frühestens T2.6I oder T2.9). Monitoring-Scripte sind in v1.0 auf CLI-Shell-Exit-Code beschränkt.
- **Backup fehlt als Runner-Job** — CLI-only, Cron-Style-Scheduling in v1.0 nur über Windows Task Scheduler + CLI-Call.
- **`events_YYYYMMDD.jsonl` (T2.7B File-Destination) wächst unbegrenzt** — keine automatische Rotation/Retention.
- **`replay-domain --all`-Modus fehlt** — aktuell manueller Shell-Loop über sechs Domains.

## Aktueller Arbeitsstand

- **Phase:** v1.0 feature-complete auf DEV-LAPTOP. T2.8 abgeschlossen 2026-04-24. **Nächster Zyklus:** T3.0 Testphase (Juli 2026 laut Plan, kann aber früher anlaufen wenn Operator bereit ist).
- **Letzter erfolgreicher Pflichtpfad:** `pytest -v` → 445 passed, 7 warnings in 551.69s (verifiziert nach T2.7F-Integration, Stand bestätigt durch T2.8-Cut da keine Code-Änderungen).
- **Nächster konkreter Schritt:** T3.0 Testphase starten. Konkret erster Schritt: Operator entscheidet, ob T3.0 sofort oder erst im Juli 2026 beginnt (laut T2_3_PLAN.md §9 Fenster "Juli 2026"). Bei Sofort-Start: Scheduler-Tick-Loop auf DEV-LAPTOP aufsetzen (Windows Task Scheduler + `new-nfl run-worker --serve` oder Cron-äquivalent), tägliche `fetch-remote` + `stage-load` + `core-load` + `mart-rebuild` über alle sieben Primary-Slices planen, `backup-snapshot` als tägliche Task ergänzen.

## Geänderte / neue Dokumente in dieser Session

- Neu: `docs/_ops/releases/v1.0.0-laptop.md` (Release-Evidence gemäß RELEASE_PROCESS.md §5).
- Neu: `docs/_handoff/chat_handoff_20260424-0030_t28-v1-cut.md` (dieser Handoff).
- Geändert: `docs/PROJECT_STATE.md` (Phase-Header, Completed-Liste, Release posture, Current cycle, Preferred next bolt — komplett auf v1.0 feature-complete geflippt).
- Geändert: `docs/T2_3_PLAN.md` (Kalenderfenster-Tabelle T2.7 + T2.8 auf ✅, §7 T2.8-Sektion auf abgeschlossen mit Definition-v1.0-Matrix geflippt).
- Geändert: `docs/PARALLEL_DEVELOPMENT.md` (Retro-Block mit Worktree-Pflicht, Status-Flip auf Referenz-Dokument) — bereits in Commit `bcc5cc3` gelandet.
- Geändert: `C:\Users\andre\.claude\projects\c--projekte-newnfl\memory\project_parallel_streams_shared_workdir.md` (Type `project` → `feedback`, Worktree-Regel als `feedback`-Memory).
- Geändert: `C:\Users\andre\.claude\projects\c--projekte-newnfl\memory\MEMORY.md` (Index-Eintrag aktualisiert).

## Lessons-Learned-Eintrag

Keine neue Lesson. Der T2.8-Cut ist rein dokumentarisch und berührt keinen Code — Lessons entstehen nur aus gebrochenen Erwartungen oder überraschenden Befunden. Die relevanten Lessons dieser Tranche wurden bereits vor T2.8 konsolidiert (T2.7 A-E final in `docs/LESSONS_LEARNED.md`; T2.6E/F/G/H und T2.7P bleiben `draft` bis Operator-Freigabe).

## Starter-Prompt für die neue Session

```text
Du übernimmst das Projekt **NEW NFL** — ein privates, single-operator-
betriebenes NFL-Daten- und Analysesystem. Arbeitssprache Deutsch. Der
Operator (Andreas) arbeitet allein, ohne Team, ohne externe Abnahme.

**Repo:**
- lokal: c:\projekte\newnfl (Haupt-Checkout, branch `main`)
- remote: https://github.com/andreaskeis77/new_nfl
- Git-Tag `v1.0.0-laptop` auf `main` markiert den v1.0-Cut (2026-04-24).

**Zielkorridor:**
- v1.0 feature-complete: ✅ erreicht 2026-04-24 (Tag `v1.0.0-laptop`)
- T3.0 Testphase: Juli 2026 (~4 Wochen, kann auch früher starten)
- T3.1 VPS-Migration: Ende Juli / Anfang August 2026
- Produktiv (Windows-VPS, Contabo): vor NFL-Preseason Anfang August 2026

---

## Pflichtlektüre vor jedem größeren Schritt (in dieser Reihenfolge)

1. **docs/PROJECT_STATE.md** — aktueller Gesamt-Stand, Completed-Liste,
   Preferred-Next-Bolt. Immer zuerst.
2. **docs/_handoff/chat_handoff_20260424-0030_t28-v1-cut.md** — dieser
   Handoff, Session-Brücke T2.8 → T3.0.
3. **docs/_ops/releases/v1.0.0-laptop.md** — kanonische Release-Evidence
   für v1.0 mit Definition-Matrix (4/5 Kriterien ✅, Backup/Restore nach
   T3.0 verschoben) und 8 benannten Restrisiken.
4. **docs/T2_3_PLAN.md** — Tranche-Plan; §9 beschreibt T3.0 mit Sub-Bolts
   T3.0A–H (Scheduler-Automation, ADR-0032-Validation, ADR-0030-Review,
   Designed Degradation, Backfill-Lasttest, Backup/Restore-Drill,
   Ruff-Cleanup optional, Bugfix-Bolts ad hoc).
5. **docs/ENGINEERING_MANIFEST_v1_3.md** — verbindliche Engineering-
   Regeln (v1.3 ist der aktuelle Draft; v1.2 in `ENGINEERING_MANIFEST.md`
   bleibt referenz-bindend bis v1.3 explizit angenommen ist).
6. **docs/concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md** — Architektur-Anker,
   Phasen (bis v1.0: DEV-LAPTOP; nach v1.0: VPS), Definition v1.0
   (§2.4), UI-Surface (§9), Operator-Workflow (§10).
7. **docs/USE_CASE_VALIDATION_v0_1.md** — abgenommene Use Cases, §2.3
   Definition v1.0, §5.4 Pflicht-Views.
8. **docs/UI_STYLE_GUIDE_v0_1.md** — Pflicht für jede UI-Arbeit
   (Tailwind-Subset, Komponenten, Theme-Tokens).
9. **docs/RELEASE_PROCESS.md** — §3.3 Runtime-Release, §4 Voraussetzungen,
   §5 Mindestartefakte.
10. **docs/CHAT_HANDOFF_PROTOCOL.md** — wann Handoff Pflicht, Template
    für neue Handoff-Dokumente.
11. **docs/LESSONS_LEARNED_PROTOCOL.md** + **docs/LESSONS_LEARNED.md** —
    Method-Updates, inkl. konsolidierter T2.7-Lesson.
12. **docs/PARALLEL_DEVELOPMENT.md** — mit T2.7-Retro-Block; ab sofort
    Pflicht bei jeder parallelen Tranche: `git worktree add` statt
    Branch-Flips im Haupt-Checkout.
13. **docs/adr/README.md** — ADR-Index (33 Stück, davon 2 `Proposed`:
    ADR-0030 UI-Stack, ADR-0032 Bitemporale Rosters — beide warten auf
    T3.0-Feedback).

---

## Verbindliche Regeln (gelten für jede Antwort)

**Sprache + Stil:**
- Arbeitssprache Deutsch. Code-Identifier bleiben englisch (Konsistenz
  mit bestehendem Codebase).
- Kein Emoji-Spam.
- Kurze, präzise Antworten. Lange Erklärungen nur wenn gefragt.

**Engineering:**
- Manifest gilt vollständig (Prio-Reihenfolge §2, Prinzipien §3).
- **Vollständige Dateien liefern, keine Patch-Snippets** (Manifest §7.5).
- Keine Scope-Ausweitung ohne explizite Freigabe. Bug-Fixes nicht mit
  Refactoring bündeln.
- UI/API liest ausschließlich aus `mart.*` (ADR-0029). AST-Lint-Test
  `tests/test_mart.py::test_read_modules_do_not_reference_core_or_stg_directly`
  ist das Gate.
- Operator-Aktionen sind in v1.0 CLI-only. Keine UI-Buttons für
  Refresh/Replay/Quarantäne — das ist v1.1.
- Read-Modelle sind versionsiert (`mart.<name>_v1`), Rebuild ist
  idempotent, `CREATE OR REPLACE TABLE` garantiert bit-identischen
  Output bei unveränderten Inputs.
- Neue CLI-Subcommands gehen über die Plugin-Registry
  (`src/new_nfl/cli_plugins.py` + `src/new_nfl/plugins/*.py`), nicht in
  den `cli.py`-Monolith (ADR-0033).
- Neue Mart-Builder tragen `@register_mart_builder("<mart_key>")`-
  Decorator aus `src/new_nfl/mart/_registry.py`.
- Tests pro neues Feature hart: Full-Suite muss grün bleiben. Aktueller
  Stand: 445/445 in ~9:11.
- Ruff-Delta bleibt 0 gegenüber Baseline (45 pre-existing Rule-Drift-
  Errors sind toleriert). Neue Regressionen sind blockierend.

**Ausführungsort:**
- Befehle immer mit Prefix kennzeichnen:
  - `DEV-LAPTOP $` — lokaler Entwicklungs-Laptop (Windows 11 Pro)
  - `VPS-USER $` — Benutzer-Session auf Windows-VPS (nach T3.1)
  - `VPS-ADMIN $` — Admin-Session auf Windows-VPS (nach T3.1)

**Parallel-Entwicklung:**
- Bei **jeder** Tranche mit ≥2 parallelen Streams: `git worktree add
  c:/projekte/newnfl.wt/<stream> feature/<branch>` **vor Stream-Start**,
  **keine Branch-Flips** im Haupt-Checkout `c:/projekte/newnfl`. Der
  Haupt-Checkout bleibt für Sync + Integration reserviert.
- Python-Venv pro Worktree eigen (Symlinks sind auf Windows fragil).
- Bei Session-Start: wenn Worktree-Setup nicht eindeutig aus dem
  vorherigen Handoff hervorgeht, **explizit nachfragen**.

**Protokoll-Pflichten:**
- Bei Ende einer Tranche/eines Bolts: Chat-Handoff gemäß
  CHAT_HANDOFF_PROTOCOL §2.1 **proaktiv** vorschlagen.
- Bei Lesson-würdigen Beobachtungen (Überraschungen, gebrochene
  Erwartungen, bestätigte Nicht-Offensichtliches): Lesson-Draft gemäß
  LESSONS_LEARNED_PROTOCOL anlegen, nicht warten bis gefragt.
- Pläne und Doku automatisch bei jeder relevanten Entscheidung
  aktualisieren — `PROJECT_STATE.md`, `T2_3_PLAN.md`, `adr/*.md`.
- Memory-System unter `C:\Users\andre\.claude\projects\c--projekte-newnfl\memory\`
  aktiv nutzen: `MEMORY.md` als Index, Memory-Files einzeln pro Thema.

---

## Aktueller Stand (Stand 2026-04-24, nach T2.8-Cut)

**Code-Basis:** ~19.200 LoC Quellcode + ~12.400 LoC Tests = ~31.600
aktive Zeilen. 6 Core-Domänen (Teams, Games, Players, Rosters-bitemporal,
Team-Stats-Weekly, Player-Stats-Weekly). 16 Marts unter 15 Builder-
Modulen. 14 Slices (7 primary + 7 cross-check). 10 UI-Views (alle
Pflicht-Views aus §5.4). 33 ADRs (2 `Proposed`).

**Gates:** 445 Tests grün in 551.69s. Ruff-Baseline 45 Rule-Drift-
Errors, Delta 0 gegenüber vor-T2.7-Stand.

**Was läuft:**
- Fetch → Stage → Core → Mart-Pipeline über alle Primary-Slices
- Internal Runner mit Retry/Quarantäne/deterministischem Replay
- 10 Web-Views lokal unter Jinja2 + Tailwind-Subset
- CLI mit ~60 Subcommands (50 im Monolith + 13 via Plugin-Registry)
- Health-Probes (CLI-only, HTTP-Mirror deferred)
- Strukturiertes JSON-Logging mit täglicher File-Rotation
- Backup/Restore/Replay-Mechanik mit Determinismus-Gate

**Was offen ist:**
- ADR-0030 (UI Tech Stack): `Proposed`, Flip nach T3.0-Feedback
- ADR-0032 (Bitemporale Rosters): `Proposed`, Flip nach T3.0B
- 5. v1.0-Kriterium (Backup/Restore-Operator-Validation): ⚠️, Aufwertung
  nach T3.0F
- Ruff-Baseline 45 Errors: optional T3.0G

**Aktueller Cycle:** T2.8 abgeschlossen. **Nächster Cycle ist T3.0
Testphase auf DEV-LAPTOP.**

---

## Konkreter nächster Schritt

**Operator-Entscheidung an Session-Start:** Wann startet T3.0?

Option A: **T3.0 sofort** — dann erster Bolt ist **T3.0A Scheduler-
Automation**:
- `schtasks.exe /create`-Definition für `new-nfl run-worker --serve`
  mit Auto-Restart-Policy
- Daily-Trigger für alle sieben Primary-Slices
  (nflverse_bulk × teams/games/players/rosters/team_stats_weekly/
  player_stats_weekly + schedule_field_dictionary)
- `backup-snapshot` als eigene Daily-Task
- Log-Destination auf `file:<data_root>/logs/` (T2.7B)
- DoD: drei Tage stabiler Tick-Stream + sichtbare Freshness-Ticks im
  Home-Dashboard

Option B: **T3.0 im Juli 2026** — dann ist Zwischen-Arbeit z. B.:
- Ruff-Baseline-Cleanup (T3.0G vorgezogen)
- Backup als Runner-Job nachziehen (Restrisiko 6 aus v1.0.0-laptop.md)
- `replay-domain --all`-Modus nachziehen (Restrisiko 8)
- Oder Phase-1.5-Domänen (Injuries, Inactives, Depth-Charts,
  Play-by-Play, PFR-Advanced, Next-Gen-Stats, Wetter) vorbereiten

**Pflicht vor erstem Code-Änderungs-Schritt:** Pflichtlektüre lesen,
Verständnis in 5 Bullets bestätigen, Operator-Freigabe für Option A
oder B einholen.

---

## Eskalations-Hinweise

- **Verdacht auf Code-Regression** → Full-Suite `pytest -v` + Ruff
  vergleichen gegen Stand `v1.0.0-laptop`.
- **Unklare Architektur-Entscheidung** → zuerst `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md`
  + ADR-Index konsultieren, dann Operator fragen, erst danach Neuentscheidung.
- **Unklare Priorität** → T2_3_PLAN.md §9 (T3.0 Sub-Bolts) ist die
  aktuell verbindliche Sequenz; bei Widerspruch zu anderen Quellen
  dort die Wahrheit suchen.
- **Unerwarteter Zustand im Repo** (unbekannte Dateien, Branches,
  Worktrees) → **nicht löschen**, erst Operator fragen. T2.7-Lesson:
  Shared-Workdir kann Stream-C-Edits in Stream-A-Files hinterlassen.

---

## Arbeitsauftrag für diese Session

1. Lies die Pflichtlektüre komplett (mindestens Dokumente 1–4 der Liste).
2. Bestätige Verständnis in **5 Bullets**:
   - Wo stehen wir (Tranche, Test-Count, offene ADRs)?
   - Was ist T3.0 und welche Sub-Bolts umfasst es?
   - Welche der 8 Restrisiken aus `v1.0.0-laptop.md §5` sind für den
     T3.0-Scope relevant?
   - Welche Pflichtpfade (Test-Gate, Ruff-Delta, AST-Lint) gelten?
   - Was ist die Worktree-Pflicht und warum?
3. Stelle dem Operator die Frage: **Option A (T3.0 sofort mit T3.0A
   Scheduler-Automation) oder Option B (T3.0 im Juli, Zwischen-Arbeit
   jetzt)?**
4. Erst nach Antwort: konkreten nächsten Schritt vorschlagen und
   Freigabe einholen.
```
