# NEW NFL — Parallel Development Guide

**Zweck:** Drei parallele Claude-Code-Sessions arbeiten auf drei Feature-Branches (`feature/t27-observability`, `feature/t27-resilience`, `feature/t27-hardening`) je mit eigenem `git worktree`. Eine vierte Session integriert die Streams sequenziell zurück in `main`. Jeder Stream läuft autonom mit einem eigenen Master-Prompt; alle drei Streams bleiben strukturell entkoppelt, weil T2.7P vorher die drei Konflikt-Zonen (Mart-Registry, CLI-Plugin-Registry, Web-Route-Registry) aufgelöst hat (siehe ADR-0033).

**Status:** Entwurf, wartet auf Operator-Freigabe vor T2.7P-Start.

## 1. Voraussetzungen

Vor dem Split in parallele Streams:

1. **T2.7P — Parallelisierungs-Prep** ist abgeschlossen und nach `main` gepusht.
2. **ADR-0033** ist `Accepted`.
3. **Full-Suite 323+/323+** (T2.7P fügt kleine Smoke-Tests hinzu; die Zahl sollte leicht steigen, nicht sinken).
4. **Ruff sauber** auf allen T2.7P-scoped Files.

Ohne T2.7P führen parallele Streams garantiert zu Merge-Konflikten an `runner.py::_executor_mart_build`, `cli.py::build_parser` und `web/__init__.py` / `mart/__init__.py` Re-Export-Blöcken.

## 2. Branch- und Worktree-Strategie

```bash
# Einmalig in der Integrations-Session anlegen:
cd c:/projekte/newnfl
git checkout main
git pull
git branch feature/t27-observability
git branch feature/t27-resilience
git branch feature/t27-hardening

# Separate Worktrees pro Stream (parallele File-Systems):
git worktree add ../newnfl-obs     feature/t27-observability
git worktree add ../newnfl-res     feature/t27-resilience
git worktree add ../newnfl-hard    feature/t27-hardening
```

Jede Stream-Session startet in ihrem eigenen Worktree — die drei Worktrees teilen kein Arbeitsverzeichnis, aber alle gleiche Git-Historie. Python-Venv darf pro Worktree eigen sein (symlinking ist fragil auf Windows).

## 3. Stream-Definition

### Stream A — Observability (`feature/t27-observability`)

**Scope:** T2.7A Health-Endpunkte + T2.7B Strukturiertes Logging

**Owns (darf schreiben):**
- `src/new_nfl/observability/` (neuer Ordner)
  - `health.py` — JSON-Health-Response-Builder
  - `logging.py` — strukturierter Logger mit Pflichtfeldern (`event_id`, `adapter_id`, `source_file_id`, `job_run_id`, `ts`, `level`, `msg`, `details`)
  - `routes.py` — Registry-Registrierung der Health-Routen
- `src/new_nfl/cli/plugins/health.py` — CLI-Plugin `health-probe`
- `tests/test_health.py`, `tests/test_logging.py`
- neue Templates falls nötig (HTML-Fallback) unter `templates/health/`

**Touches readonly (darf nur additiv via Registry erweitern, nicht bestehende Logik ändern):**
- `src/new_nfl/settings.py` — neue Properties `log_level`, `log_destination` (via frozen-dataclass-Erweiterung, keine Struktur-Änderung)
- `src/new_nfl/web/_routes.py` — Route-Registrierung (Append-only)
- `src/new_nfl/jobs/runner.py` — nur Logging-Hook-Einbau an definierten Stellen (pro Executor-Entry/Exit), keine `_executor_*`-Logik ändern

**Darf NICHT anfassen:** `mart/*.py`, `core/*.py`, `adapters/*.py`, `dedupe/*.py`, `web/*_view.py` — Stream B und C haben dort Scope.

**Risiko:** niedrig. Health ist rein additiv. Logging ist cross-cutting, aber die Hook-Stellen in runner.py sind klar (Executor-Start, Executor-Ende, Executor-Exception).

---

### Stream B — Resilience (`feature/t27-resilience`)

**Scope:** T2.7C Backup-Drill + T2.7D Replay-Drill

**Owns:**
- `src/new_nfl/resilience/` (neuer Ordner)
  - `backup.py` — DuckDB-Snapshot + `data/raw/` → ZIP
  - `restore.py` — ZIP-Restore in neues DB-File + Raw-Verzeichnis
  - `replay.py` — Full-Run-Replay auf Raw-Artefakt, Pre/Post-Vergleich
  - `diff.py` — Tabellarischer Vergleich für Pre/Post-Erwartungen
- `src/new_nfl/cli/plugins/resilience.py` — `backup-snapshot`, `restore-snapshot`, `verify-snapshot`, `replay-domain`
- `tests/test_backup.py`, `tests/test_replay.py`, `tests/test_restore.py`
- dedicated Fixtures unter `tests/fixtures/backup/` (small-sized seed)

**Touches readonly:**
- `src/new_nfl/settings.py` — neue Property `backup_destination` (Pfad für ZIP-Target)
- `src/new_nfl/cli/_plugins.py` — nur Registry-Hook
- `src/new_nfl/jobs/runner.py` — neuer Executor `backup_snapshot` via `register_job_executor`-Registry (gehört zu T2.7P, falls ich da vorgreife — sonst Neu-Scope)

**Darf NICHT anfassen:** `mart/*.py`, `core/*.py`, `web/*.py`, `adapters/*.py` — außer für Read-Only-Queries in Replay-Diff.

**Risiko:** mittel. Backup/Restore ist Filesystem-heavy, braucht Windows-Pfad-Disziplin und Tempdir-Hygiene. Replay-Vergleich kann subtile Determinism-Fragen aufwerfen (z.B. `_canonicalized_at`-Timestamp variiert).

---

### Stream C — Hardening (`feature/t27-hardening`)

**Scope:** T2.7E Backlog-Abarbeitung — sammelt die offenen Punkte aus T2.5/T2.6 Lessons Learned

**Owns:**
- `src/new_nfl/meta/` (neuer Ordner — bisher kein eigener Namespace)
  - `schema_cache.py` — Settings-Level-Cache für DESCRIBE auf `core.team` / `core.player`
  - `adapter_slice_registry.py` — Projektion von `SLICE_REGISTRY` nach `meta.adapter_slice`
  - `retention.py` — CLI-Backend für `trim-run-events --older-than 30d`
- `src/new_nfl/cli/plugins/hardening.py` — `trim-run-events`, `dedupe-review-resolve`, `adapter-slice-sync`
- Änderungen an `src/new_nfl/bootstrap.py` — Ontology-Auto-Aktivierung (dritte T2.5C-Backlog-Lesson)
- Änderungen an `src/new_nfl/dedupe/review.py` — `resolve(review_id, action)`-Funktion plus CLI-Plugin
- `tests/test_schema_cache.py`, `tests/test_retention.py`, `tests/test_adapter_slice_registry.py`, `tests/test_dedupe_review_resolve.py`

**Touches readonly:**
- `src/new_nfl/settings.py` — neue Property `schema_cache_ttl_seconds`
- `src/new_nfl/mart/player_overview.py` — Integration Schema-Cache (koordinationsfrei, weil Stream B dort nichts schreibt)
- `src/new_nfl/mart/*_*.py` mit DESCRIBE-Fallback — Integration Schema-Cache (Bulk-Edit durch Stream C, weil thematisch zusammengehörig)

**Darf NICHT anfassen:** `web/*.py`, `observability/*.py` (Stream A), `resilience/*.py` (Stream B).

**Risiko:** mittel. Stream C berührt mehrere bestehende Files (Mart-Module mit DESCRIBE-Fallback), aber jeweils additiv (Cache-Wrapper um bestehende DESCRIBE-Calls). Ontology-Bootstrap-Änderung ist heikel — muss idempotent bleiben.

---

### Integration-Session (`main`)

**Scope:** Sequenzielles Merge von A → B → C nach Risiko aufsteigend.

**Protokoll pro Merge:**
1. `git fetch`; `git checkout main`; `git pull` (falls zwischenzeitlich Commits direkt auf main)
2. `git merge --no-ff feature/t27-observability` (resp. B, C) mit sprechender Merge-Message
3. **Bei Konflikt:** an Registry-Files (`_registry.py`, `_plugins.py`, `_routes.py`) ist der Konflikt append-only und löst sich meist trivial. An anderen Files: Operator konsultieren.
4. `pytest` full suite grün
5. `ruff check` auf allen geänderten Files grün
6. AST-Lint-Test (`test_mart.py::test_read_modules_do_not_reference_core_or_stg_directly`) grün
7. Push nach `origin/main`
8. Worktree des gemergten Streams löschen: `git worktree remove ../newnfl-obs`; Branch löschen: `git branch -d feature/t27-observability`

**Nach allen drei Merges:**
- ADR-0030 (UI Tech Stack) → `Accepted` (war seit T2.6A implementiert, Statuswechsel überfällig)
- ADR-0032 (Bitemporale Rosters) → Validation-Check, ob Operator mit echten Daten zufrieden ist
- ADR-0033 (Registry-Pattern) → `Accepted`
- Neue ADRs aus den Streams (falls welche entstanden sind) → Status aktualisieren
- Lessons-Learned-Einträge aus allen drei Streams konsolidieren
- Chat-Handoff T2.7 → T2.8

## 4. Master-Prompts

Jeder Stream startet seine Claude-Code-Session mit genau einem Master-Prompt. Der Prompt ist self-contained: er nennt Scope, Boundaries, Pflichtlektüre, Quality-Gates, Commit-Disziplin, Handoff-Format.

**Vorbereitung vor jedem Prompt:**
- Der Operator startet Claude Code im jeweiligen Worktree-Verzeichnis
- Der Master-Prompt wird **unverändert** (inkl. der Abschnitts-Überschriften) in den ersten User-Turn eingefügt
- Der Operator greift nicht weiter ein, außer bei expliziten Blocker-Signalen

---

### Master-Prompt A — Observability-Stream

```
NEW NFL — Stream A (Observability) — autonome Session

Dein Arbeitsverzeichnis ist ein git-worktree auf dem Branch `feature/t27-observability`. Basis ist `main` nach Abschluss von T2.7P (Registry-Pattern, ADR-0033). Zwei Schwester-Streams (Resilience, Hardening) laufen parallel in anderen Worktrees — du siehst deren Arbeit nicht, und du darfst keine Dateien außerhalb deines Scopes ändern.

## Dein Scope
- T2.7A — Health-Endpunkte: `/livez`, `/readyz`, `/health/deps`, `/health/freshness` als JSON-Responses (`Content-Type: application/json`, stabile Schema-Version in jedem Response).
- T2.7B — Strukturiertes Logging: Pflichtfelder `event_id`, `adapter_id`, `source_file_id`, `job_run_id`, `ts`, `level`, `msg`, `details` gemäß `docs/OBSERVABILITY.md`. Logger-Instanz via Settings, Destination konfigurierbar (stdout default, File-Ziel `data/logs/` optional).

## Erlaubte Verzeichnisse (du darfst schreiben)
- `src/new_nfl/observability/` (neuer Ordner) — `health.py`, `logging.py`, `routes.py`
- `src/new_nfl/cli/plugins/health.py` — Plugin-Modul für CLI-Health-Commands
- `tests/test_health.py`, `tests/test_logging.py`
- optional: `src/new_nfl/web/templates/health/` für HTML-Fallback-Seiten

## Verboten (Read-Only)
- `mart/*.py`, `core/*.py`, `adapters/*.py`, `dedupe/*.py`, `web/*_view.py` — gehört Stream B/C oder ist stabil
- `cli.py` selbst (nur via Plugin-Registry erweitern)
- `settings.py` — nur additive Properties via Diff-Patch erlaubt (keine Struktur-Änderung)

## Pflichtlektüre vor erstem Edit
1. `docs/PROJECT_STATE.md` — aktueller Stand
2. `docs/T2_3_PLAN.md` §6 — T2.7-Scope
3. `docs/PARALLEL_DEVELOPMENT.md` — dieser Guide (Stream-A-Abschnitt)
4. `docs/OBSERVABILITY.md` — Pflichtfelder für Logging
5. `docs/adr/ADR-0033-registry-pattern-for-parallel-development.md` — Registry-API
6. `docs/adr/ADR-0029-read-model-separation.md` — `/health/freshness` liest ausschließlich `mart.*`

## Quality-Gates (vor jedem Commit)
- `pytest tests/test_health.py tests/test_logging.py -v` grün
- `ruff check src/new_nfl/observability/ tests/test_health.py tests/test_logging.py` clean
- Full-Suite `pytest` grün (keine Regression in den 323+ bestehenden Tests)
- Jeder Health-Endpunkt liefert JSON mit `schema_version`, `checked_at`, `status` (`ok`/`warn`/`fail`)
- Logging nutzt strukturierte Records, nicht `print()`

## Commit-Disziplin
- Ein Feature = ein Commit. Keine "fix ruff"-Nachzügler — Ruff läuft vor dem ersten Test-Run.
- Commit-Messages: `T2.7A: ...` für Health-Commits, `T2.7B: ...` für Logging-Commits
- Nach jedem Commit: `git push origin feature/t27-observability`
- Am Ende der Session: Stream-Lessons-Learned als Draft in `docs/LESSONS_LEARNED.md` prepend (nicht committen ohne Operator-Review — stattdessen in eigenem `.md`-File unter `docs/_handoff/lessons_t27a.md` ablegen und verlinken)

## Arbeitsrhythmus
1. **Setup-Check:** Liste alle Dateien unter `src/new_nfl/observability/` auf. Wenn der Ordner nicht existiert, lege ihn an. Prüfe, dass `src/new_nfl/web/_routes.py` existiert (T2.7P-Artefakt) — ohne das darfst du nicht starten.
2. **Health-Endpunkte zuerst (`/livez` + `/readyz`):** trivialer Prozess-Check, dann DB-Connect-Check + Mart-Presence-Check für `mart.freshness_overview_v1`.
3. **Health-Endpunkte zweite Welle (`/health/freshness` + `/health/deps`):** JSON-Spiegel von `render_home` bzw. Adapter-Registry mit `meta.load_events`-Timestamp pro Adapter.
4. **Strukturiertes Logging:** Logger-Factory in `observability/logging.py`. Jeder `_executor_*` in runner.py bekommt einen `log_event(kind, details)`-Hook am Entry/Exit/Exception. Der Hook ist ein 2-Zeilen-Injection — wenn du feststellst, dass du mehr als 2 Zeilen pro Executor änderst, stopp und frag nach.
5. **Cleanup-Tests:** Empty-State (DB komplett leer), Null-Nachbar (Mart existiert, aber 0 Rows), Happy-Path, Error-Path.
6. **Abschluss:** `docs/_handoff/lessons_t27a.md` mit Draft-Lessons schreiben. Handoff-Commit mit Link-Hinweis für die Integrations-Session.

## Eskalations-Regeln
- Wenn ein Test scheitert und du den Grund nicht in <3 Iterations-Schritten findest → stop, beschreibe den Blocker, warte auf Operator-Input.
- Wenn du feststellst, dass du eine Datei außerhalb des erlaubten Scopes ändern musst → stop, beschreibe die Notwendigkeit, warte auf Operator.
- Wenn Full-Suite nach deinem Commit scheitert (Regression in einem der 323 bestehenden Tests) → Commit zurückrollen, Ursache isolieren, eskalieren.

Los geht's. Erste Aktion: Setup-Check.
```

---

### Master-Prompt B — Resilience-Stream

```
NEW NFL — Stream B (Resilience) — autonome Session

Dein Arbeitsverzeichnis ist ein git-worktree auf dem Branch `feature/t27-resilience`. Basis ist `main` nach Abschluss von T2.7P (Registry-Pattern, ADR-0033). Zwei Schwester-Streams (Observability, Hardening) laufen parallel — du siehst deren Arbeit nicht.

## Dein Scope
- T2.7C — Backup-Drill: DuckDB-File + `data/raw/` in ein ZIP exportieren, Restore in neues Temp-Verzeichnis, Smoke nach Restore.
- T2.7D — Replay-Drill: bestehenden Run aus `core.*` löschen, von Raw-Artefakt replayen, Pre/Post-Vergleich mit Equality-Assert.

## Erlaubte Verzeichnisse (du darfst schreiben)
- `src/new_nfl/resilience/` (neuer Ordner) — `backup.py`, `restore.py`, `replay.py`, `diff.py`
- `src/new_nfl/cli/plugins/resilience.py` — CLI-Plugin-Modul
- `tests/test_backup.py`, `tests/test_replay.py`, `tests/test_restore.py`
- `tests/fixtures/backup/` — falls deterministische Seed-Fixtures nötig

## Verboten (Read-Only)
- `mart/*.py`, `core/*.py`, `web/*.py`, `adapters/*.py` — nur Read-Only-Queries für Replay-Vergleich
- `cli.py`, `jobs/runner.py` (die Job-Executor-Registry kommt aus T2.7P — du registrierst dort, änderst sie nicht)
- `settings.py` — nur additive Property `backup_destination` (eine Zeile)

## Pflichtlektüre vor erstem Edit
1. `docs/PROJECT_STATE.md`
2. `docs/T2_3_PLAN.md` §6 — T2.7-Scope, insbesondere T2.7C/D
3. `docs/PARALLEL_DEVELOPMENT.md` — Stream-B-Abschnitt
4. `docs/RUNBOOK.md` — welche Artefakte sind Pflicht bei einem Restore-Smoke
5. `docs/adr/ADR-0033-registry-pattern-for-parallel-development.md`
6. `docs/adr/ADR-0025-internal-job-and-run-model.md` — Replay-Semantik erbt von hier

## Quality-Gates (vor jedem Commit)
- `pytest tests/test_backup.py tests/test_replay.py tests/test_restore.py -v` grün
- `ruff check src/new_nfl/resilience/ tests/test_backup.py tests/test_replay.py tests/test_restore.py` clean
- Full-Suite `pytest` grün
- Backup-ZIPs sind deterministisch (gleiche Input-Daten → gleicher SHA-256 nach Extraktion — zumindest für Daten-Payload, nicht für Archive-Metadaten)
- Replay-Pre/Post-Diff ist leer bei identischem Raw-Artefakt (Timestamps `_canonicalized_at` dürfen variieren — baue das explizit in den Vergleich ein)

## Commit-Disziplin
- `T2.7C: ...` für Backup-Commits, `T2.7D: ...` für Replay-Commits
- Nach jedem Commit: `git push origin feature/t27-resilience`
- Am Ende: `docs/_handoff/lessons_t27b.md` mit Draft-Lessons

## Arbeitsrhythmus
1. **Setup-Check:** `resilience/`-Ordner anlegen. Prüfe, dass `jobs/runner.py` eine `register_job_executor`-Registry-API hat (T2.7P). Ohne diese keine Backup-Jobs.
2. **Backup-Snapshot (T2.7C):** `backup_snapshot(settings, target_zip)` — schließt DB-Connections, kopiert `.duckdb`-File in Temp, ZIPt DB + `data/raw/`. Tests mit winziger DB + 2 Raw-Files.
3. **Restore-Snapshot:** `restore_snapshot(zip_path, target_dir)` — Inverse. Smoke: Full-Suite gegen Restore-Dir funktioniert (Subset, nicht Full-Suite — such einen geeigneten Smoke-Test).
4. **Verify-Snapshot:** `verify_snapshot(zip_path)` — prüft ZIP-Integrität ohne Restore (Manifest-Check).
5. **Replay-Drill (T2.7D):** `replay_domain(settings, domain, source_file_id)` — löscht domain-spezifische `core.*`-Rows, ruft Core-Load neu auf, vergleicht mit Pre-State-Snapshot.
6. **Diff-Tool:** `diff_tables(db_a, db_b, table, key_cols, exclude_cols)` — für Replay-Vergleich. `exclude_cols=['_canonicalized_at', '_loaded_at']` standardmäßig.
7. **CLI-Plugins:** `backup-snapshot --target PATH`, `restore-snapshot --source PATH --target DIR`, `verify-snapshot --source PATH`, `replay-domain --domain DOMAIN --source-file-id ID`.
8. **Abschluss:** Lessons-Draft.

## Eskalations-Regeln
- Wenn DuckDB einen Lock auf der DB-Datei hält und dein Backup scheitert → stop, eskaliere. Nicht mit `--force`-Flags oder Kill-Prozess-Hacks umgehen.
- Wenn Replay-Diff bei identischem Input nicht-leere Ergebnisse liefert und du den Grund nicht findest → stop, eskaliere (das ist ein Determinism-Bug im Core-Load und braucht eine separate Session).
- Gleiche Scope-Regeln wie Stream A: bei Scope-Überschreitung stop.

Los geht's.
```

---

### Master-Prompt C — Hardening-Stream

```
NEW NFL — Stream C (Hardening) — autonome Session

Dein Arbeitsverzeichnis ist ein git-worktree auf dem Branch `feature/t27-hardening`. Basis ist `main` nach Abschluss von T2.7P (Registry-Pattern, ADR-0033). Zwei Schwester-Streams (Observability, Resilience) laufen parallel — du siehst deren Arbeit nicht.

## Dein Scope (Backlog-Abarbeitung, in dieser Priorität)
- T2.7E-1 — **Event-Retention**: `meta.run_event` wächst linear mit Runs. CLI `trim-run-events --older-than 30d [--dry-run]` löscht alte Events + zugehörige Artefakt-Referenzen (falls der Run vollständig abgeschlossen ist).
- T2.7E-2 — **Schema-DESCRIBE-Cache**: Settings-Level-Cache mit TTL. Aktuell rufen ~10 Marts pro Rebuild DESCRIBE auf `core.team` / `core.player`. Skaliert nicht für UI-Requests.
- T2.7E-3 — **Ontology-Auto-Aktivierung**: `bootstrap_local_environment` erkennt, wenn keine `meta.ontology_version` als `is_active=true` markiert ist, und aktiviert automatisch die neueste geladene Version (wenn überhaupt eine existiert). Motivation: `position_is_known` in `mart.player_overview_v1` ist auf Fresh-DB dreiwertig NULL.
- T2.7E-4 — **`meta.adapter_slice` Runtime-Projektion**: `SLICE_REGISTRY` aus `adapters/slices.py` wird beim Bootstrap in eine DB-Tabelle projiziert, damit UI/CLI ohne Python-Import Slice-Metadaten lesen können.
- T2.7E-5 — **`dedupe-review-resolve`**: CLI zum Auflösen eines offenen Review-Items in `meta.review_item` mit Aktionen `merge`, `reject`, `defer`.

## Erlaubte Verzeichnisse
- `src/new_nfl/meta/` (neuer Namespace) — `schema_cache.py`, `adapter_slice_registry.py`, `retention.py`
- `src/new_nfl/cli/plugins/hardening.py` — Plugin für alle Hardening-Commands
- Änderung an `src/new_nfl/bootstrap.py` — Ontology-Auto-Activate (zusätzliche Zeilen, keine Struktur-Änderung)
- Änderung an `src/new_nfl/dedupe/review.py` — `resolve(review_id, action)` hinzufügen
- `tests/test_schema_cache.py`, `tests/test_retention.py`, `tests/test_adapter_slice_registry.py`, `tests/test_dedupe_review_resolve.py`, `tests/test_bootstrap_ontology.py`

## Erlaubt mit Vorsicht (Integration bestehender Marts in Schema-Cache)
- `src/new_nfl/mart/player_overview.py`, `mart/team_overview.py`, alle `mart/*stats*.py` — Integration Schema-Cache via Wrapper um bestehende DESCRIBE-Calls. **Regel:** additiver Wrapper, bestehende Logik bleibt bit-identisch, du entfernst nur die Direkt-DESCRIBE-Calls und ersetzt sie durch `schema_cache.describe(settings, 'core.team')`.

## Verboten (Read-Only)
- `web/*.py`, `observability/*.py`, `resilience/*.py` — andere Streams
- `cli.py`, `jobs/runner.py` (nur via Registry)
- `settings.py` — nur additive Property `schema_cache_ttl_seconds` (eine Zeile)

## Pflichtlektüre vor erstem Edit
1. `docs/PROJECT_STATE.md`
2. `docs/T2_3_PLAN.md` §6
3. `docs/PARALLEL_DEVELOPMENT.md` — Stream-C-Abschnitt
4. `docs/LESSONS_LEARNED.md` — Suche nach Erwähnungen der fünf Backlog-Punkte (T2.5C, T2.5F, T2.6H) für den Why-Kontext
5. `docs/adr/ADR-0026-ontology-as-code-with-runtime-projection.md` — Auto-Aktivierungs-Semantik
6. `docs/adr/ADR-0027-dedupe-pipeline-as-explicit-stage.md` — Review-Resolve-Erwartung
7. `docs/adr/ADR-0031-adapter-slice-strategy.md` — Registry → `meta.adapter_slice`-Projektion

## Quality-Gates
- Alle neuen Tests grün
- Full-Suite grün (besonders kritisch wegen Schema-Cache-Integration in bestehende Marts — Regression hier wäre fatal)
- `ruff check` clean auf allen geänderten Files
- AST-Lint `test_mart.py::test_read_modules_do_not_reference_core_or_stg_directly` grün (du berührst mart-Module, achte drauf)
- Idempotenz: jeder Command darf zweimal hintereinander laufen ohne Fehler

## Commit-Disziplin
- Eine Backlog-Lesson = ein Commit, nicht alle fünf in einen. Titel `T2.7E-1: event retention`, `T2.7E-2: schema cache`, etc.
- Schema-Cache-Integration in Marts ist ein zusätzlicher Commit `T2.7E-2b: integrate schema cache in marts`
- Nach jedem Commit Push
- Am Ende: `docs/_handoff/lessons_t27c.md`

## Arbeitsrhythmus
1. **Setup + kleinstes Risiko zuerst**: Event-Retention (T2.7E-1). Isoliert, keine Integration in bestehende Marts.
2. **Schema-Cache (T2.7E-2) in zwei Schritten:** (a) Cache-Infrastruktur + Tests, (b) Integration in bestehende Marts (Bulk-Edit mit Regressions-Check).
3. **Ontology-Auto-Activate (T2.7E-3):** Änderung in `bootstrap.py` mit neuem Test, der explicit nachprüft: Fresh-DB → `ontology-load` → `is_active` wird automatisch gesetzt → `mart.player_overview_v1` baut mit `position_is_known` nicht NULL.
4. **Adapter-Slice-Projektion (T2.7E-4):** Projektion in `meta.adapter_slice` beim Bootstrap. CLI `list-slices` bleibt kompatibel (liest jetzt aus `meta.adapter_slice` statt direkt aus `SLICE_REGISTRY` — oder beide Wege, Registry als Source-of-Truth, DB als Projektion).
5. **Dedupe-Review-Resolve (T2.7E-5):** `resolve(review_id, action)`-Funktion in `dedupe/review.py` + CLI-Plugin. Actions: `merge` (upsert in Ziel-Table), `reject` (status='rejected'), `defer` (status='deferred', `resolved_at` bleibt NULL).
6. **Abschluss:** Lessons-Draft.

## Eskalations-Regeln
- Wenn Schema-Cache-Integration in einem Mart zu Test-Failures führt → Commit rückwärts, isoliere das spezifische Mart, eskaliere.
- Wenn Ontology-Auto-Activate idempotenz-brechend wirkt (zweiter Bootstrap-Lauf ändert den Zustand unerwartet) → stop, eskaliere.
- Wenn du beim `dedupe-review-resolve` auf unklare Merge-Semantik stößt (welches Feld überschreibt welches?) → stop, dokumentiere die Frage im Commit-Draft, warte auf Operator.

Los geht's.
```

## 5. Integrations-Session — kein Master-Prompt nötig

Die Integrations-Session ist **nicht autonom**, sondern vom Operator initiiert nach Abschluss aller drei Streams. Sie folgt dem Protokoll aus §3. Ein Master-Prompt wäre kontra-produktiv, weil die Session aktiv Konflikte bewerten und ggf. manuell entscheiden muss.

**Empfohlenes Vorgehen in der Integrations-Session:**
1. Operator bestätigt, dass alle drei Feature-Branches grün sind (CI/local Full-Suite je grün)
2. Operator öffnet eine Claude-Code-Session im Haupt-Worktree (`c:/projekte/newnfl` auf `main`)
3. Operator schreibt: "Merge-Protokoll T2.7 Integration. A → B → C. Nach jedem Merge Full-Suite, bei Konflikten stoppen und mich konsultieren."
4. Claude arbeitet das Protokoll ab, pausiert an jeder Merge-Grenze.

## 6. Risiken und Gegenmaßnahmen

| Risiko | Wahrscheinlichkeit | Auswirkung | Gegenmaßnahme |
|---|---|---|---|
| Stream überschreitet Scope, ändert Datei in einem anderen Stream | mittel | Merge-Konflikt | Eskalations-Regel im Master-Prompt; Stream pausiert vor Scope-Überschreitung |
| T2.7P-Registry wird nicht komplett umgestellt, manche Marts bleiben hardcoded | niedrig | Teilweise Konflikte bei Mart-Additionen | T2.7P-DoD listet "alle 16 Marts migriert" als Pflicht |
| Stream-interne Regression bricht Full-Suite vor Integrations-Merge | mittel | Stream-Rollback | Jede Stream-Session hat Full-Suite als Quality-Gate pro Commit |
| Settings-Properties werden in Streams widersprüchlich ergänzt | niedrig | Merge-Konflikt in `settings.py` | Nur je eine additive Property pro Stream (siehe Scope), keine Struktur-Änderungen |
| Lessons-Learned-Drafts der drei Streams widersprechen sich | niedrig | Integrations-Session muss sie harmonisieren | Jeder Stream schreibt seinen Draft in separate Datei unter `docs/_handoff/lessons_t27{a,b,c}.md`, nicht direkt in `LESSONS_LEARNED.md` |

## 7. Erfolgskriterium

Nach Abschluss der Integrations-Session:
- Alle T2.7-Bolzen (A–E) sind in `main` gemergt und getaggt
- Full-Suite ist grün (~380–400 Tests erwartet, je nach Stream-Gewicht)
- ADR-0030, ADR-0032, ADR-0033 haben ihren finalen Status
- Ein konsolidiertes Lessons-Learned-Kapitel T2.7 ist in `docs/LESSONS_LEARNED.md`
- `docs/PROJECT_STATE.md` zeigt T2.7 abgeschlossen, T2.8 als nächsten Bolzen
- Chat-Handoff T2.7 → T2.8 ist geschrieben

Wenn diese sechs Punkte erfüllt sind, ist das Parallel-Experiment erfolgreich und das Pattern ist für T3.0 (Testphase mit mehreren parallelen Bug-Fix-Streams) wiederverwendbar.
