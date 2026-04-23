# Chat-Handoff 2026-04-23 23:59 — T2.7A-E Parallel-Streams + T2.7F Integration abgeschlossen

## Trigger

§2.1 „Tranche-Abschluss": **T2.7A-F vollständig integriert** in `main`. Drei parallel entwickelte Feature-Streams (A Observability, B Resilience, C Hardening) sind in der Reihenfolge A → B → C nach aufsteigendem Risiko gemerged, Full-Suite **445 Tests grün in 551.69s (9:11)**, Integration gepusht zu `origin/main`. Lessons-Drafts aus allen drei Streams sind in einen kanonischen LESSONS_LEARNED-Eintrag konsolidiert.

§2.1 „thematischer Wechsel": Nach T2.7 ist der nächste Bolt eine Operator-Entscheidung zwischen **T2.5D-Validation** (bitemporale Rosters mit echten Daten → ADR-0032 auf `Accepted`) und **T2.8 v1.0 Cut auf DEV-LAPTOP** (Release-Tag + Release-Notes). Beide sind thematisch disjunkt von T2.7 — Handoff-Bruch ist sinnvoll.

## Was wurde in dieser Session erreicht

### T2.7F — Integrations-Session (sequenziell)

**Cleanup vor dem Merge:**
- 5 Stashes aus parallelen Streams gedropped, 2 Tags (`__t27a_commit`, `__t27b_commit`) gelöscht; Orphan-Commit `b908550` wird natürlich GC-en da alle Refs fort sind.
- Ruff-Baseline auf `main` dokumentiert: **45 pre-existing Errors** (UP035/UP037/E501/I001/B905/UP012/E741) aus Ruff-0.15.10-Rule-Drift — keine neue Regression, sondern strengere Rule-Evaluierung seit dem letzten „clean"-Commit. Gate-Kriterium für die Integration auf „Delta 0 gegenüber Baseline-45" umgestellt; Tests bleiben das harte Gate.

**Merge-Reihenfolge A → B → C** (Risiko aufsteigend):

| Schritt | Merge-Commit | Tests nach Merge | Ruff |
|---|---|---|---|
| Baseline `main` (T2.7P + Lesson-Commits) | `86bf8a2` | 332 | 45 |
| Stream A (observability) | `1eee163` | 360 (+28) | 45 |
| Stream B (resilience) | `a7575dc` | 397 (+37) | 45 |
| Stream C (hardening) | `1cada42` | 445 (+48) | 45 |

Pro Merge exakt zwei triviale Union-Konflikte:
- [src/new_nfl/plugins/__init__.py](../../src/new_nfl/plugins/__init__.py) — Registry-Import-Liste, alphabetisch resolved.
- [src/new_nfl/settings.py](../../src/new_nfl/settings.py) — additive `@property`-Block, jede Stream fügt eine Property (`log_level`/`log_destination` von A, `backup_destination_dir` von B, `schema_cache_ttl_seconds` von C) an die frozen dataclass an.

Keine weiteren Konflikte — die Scope-Trennung (Stream-lokale Namespaces `observability/` / `resilience/` / `meta/`) hat unter echter Parallelität gehalten.

**Finale Suite:** `================= 445 passed, 7 warnings in 551.69s (0:09:11) =================` — exakt Baseline 332 + Stream A 28 + Stream B 37 + Stream C 48.

### Was die drei Streams lieferten

**Stream A — Observability (Merge `1eee163`, 28 neue Tests):**
- CLI `new-nfl health-probe --kind <live|ready|freshness|deps>` mit JSON-Envelope `{schema_version:"1.0", checked_at, status, details}` und Shell-Exit-Codes `0=ok / 1=warn / 2=fail`.
- Strukturierter JSON-Logger `new_nfl.observability.logging.get_logger(settings)` mit Pflicht-Envelope + optionalen Kontext-Feldern `adapter_id`/`source_file_id`/`job_run_id`; Runner-Hook in allen vier `_executor_*` mit `executor_start`/`executor_complete`-Events.
- Settings-Properties `log_level` (Env `NEW_NFL_LOG_LEVEL`, default `INFO`) und `log_destination` (`stdout`|`file:<dir>` mit täglicher `events_YYYYMMDD.jsonl`-Rotation).

**Stream B — Resilience (Merge `a7575dc`, 37 neue Tests):**
- CLI `backup-snapshot|restore-snapshot|verify-snapshot` für verifizierbare ZIP-Snapshots; `manifest.payload_hash` deterministisch (nur payload, explizit ohne Zeitstempel).
- CLI `replay-domain --domain <d> [--source-file-id ID] [--dry-run]` für alle sechs Kerndomains; pytz-frei via pure-SQL ATTACH/CTAS + VARCHAR-Cast auf TIMESTAMPTZ.
- `diff_tables(con_a, con_b, table, key_cols, exclude_cols=...)` liefert `TableDiff(only_in_a, only_in_b, changed)`.
- Settings-Property `backup_destination_dir = data_root/"backups"`.

**Stream C — Hardening (Merge `1cada42`, 48 neue Tests):**
- CLI `trim-run-events --older-than 30d [--dry-run]` + `meta.retention` Backend.
- [src/new_nfl/meta/schema_cache.py](../../src/new_nfl/meta/schema_cache.py) TTL-Cache als drop-in-Ersatz für `con.execute("DESCRIBE …")`; 9 Mart-Module migriert; Settings-Property `schema_cache_ttl_seconds` (Env `NEW_NFL_SCHEMA_CACHE_TTL_SECONDS`, default 300s, `0` deaktiviert).
- Bootstrap aktiviert automatisch `ontology/v0_1` wenn keine aktive Version existiert (Opt-out `NEW_NFL_SKIP_ONTOLOGY_AUTOLOAD=1`); behebt `position_is_known`-Bug auf Fresh-DB.
- `meta.adapter_slice`-Runtime-Projektion + CLI `adapter-slice-sync`.
- CLI `dedupe-review-resolve --review-id … --action {merge,reject,defer}`.

### Lessons-Konsolidierung

Drei Stream-Drafts (`docs/_handoff/lessons_t27a.md`, `lessons_t27b.md`, `lessons_t27c.md`) zu einem kanonischen Eintrag in [docs/LESSONS_LEARNED.md](../LESSONS_LEARNED.md) verschmolzen. Kern-Lessons:

1. **Registry-Pattern (ADR-0033) hat unter echter Parallelität gehalten.** Drei neue `plugins/*.py`-Module, kein Touch an `cli.py`, pro Stream-Merge nur zwei triviale Union-Konflikte. Bestätigt den Investment in T2.7P.
2. **Shared-Workdir ist die eigentliche Kostenstelle.** Branch-Flips unter den Füßen, überschriebene Edits, SHA-Refspec-Push als Notbehelf — die Memory `project_parallel_streams_shared_workdir.md` hatte das Risiko beschrieben, aber die Git-Ebene-Schutzmechanismen reichen nicht. **Methodänderung: ab der nächsten parallelen Tranche `git worktree add c:/projekte/newnfl.wt/<stream>` statt Branch-Flips im Haupt-Checkout.**
3. **TIMESTAMPTZ + Python-fetchall ohne pytz-Dependency = Problem.** Lösung bewahren: pure-SQL ATTACH/CTAS oder VARCHAR-Cast.
4. **`manifest.payload_hash` trennt Determinismus von Provenienz.** Pattern wiederverwendbar für jedes künftige Snapshot-Format.
5. **`stale`-Kollaps zu `warn` in Severity-Ladder verhindert Cold-Start-"alles grün".** Pattern wiederverwendbar für jeden künftigen Health-Endpoint.
6. **Ruff-Baseline vor Integrations-Session dokumentieren.** Gate-Kriterium ist "Delta 0", nicht "absolut 0" — trennt Rule-Drift von echten Regressions.
7. **Monitor-Tool vertrauen, nicht manuell pollen.** Tail-Loops belasten Context-Window unnötig; Monitor feuert zuverlässig auf `PYTEST_EXITED`.
8. **Pytest auf Windows mit File-Redirect: immer `-u -v`, nie `-q`.** Stdout-Buffer im Background-Task flusht nur auf Newline.

### Doku-Updates in dieser Session

- [docs/LESSONS_LEARNED.md](../LESSONS_LEARNED.md): konsolidierter T2.7A-E-Eintrag prepended (neueste oben).
- [docs/T2_3_PLAN.md](../T2_3_PLAN.md): T2.7A bis T2.7F jeweils auf `✅ (2026-04-23)` geflippt; T2.7E als fünf abgeschlossene Sub-Bolts expandiert.
- [docs/PROJECT_STATE.md](../PROJECT_STATE.md): Phase-Header auf „T2.7 vollständig integriert"; T2.7A-F als neuer oberster Eintrag in Completed; 10 neue Einträge in „Current runtime posture"; „Preferred next bolt" auf Operator-Entscheidung T2.5D-Validation vs. T2.8 umgestellt; Deep-Review-Kennzahlen auf 445 Tests aktualisiert.
- Chat-Handoff-Referenz in PROJECT_STATE auf diesen Datei-Namen aktualisiert.

## Branch-/Git-Status nach Session-Ende

- `main` hat **alle drei Stream-Merges + Doku-Commit** und ist zu `origin/main` gepusht.
- Feature-Branches bleiben vorerst erhalten (lokal + remote):
  - `feature/t27-observability` (Stream A, vollständig in main gemerged)
  - `feature/t27-resilience` (Stream B, vollständig in main gemerged)
  - `feature/t27-hardening` (Stream C, vollständig in main gemerged)
  - Löschung bleibt Operator-Entscheidung — sie dienen als Audit-/Backup-Referenz.
- Keine Stashes, keine Tags, keine offenen Working-Tree-Änderungen.
- Lessons-Drafts `docs/_handoff/lessons_t27{a,b,c}.md` bleiben als historische Artefakte erhalten (der kanonische Eintrag in LESSONS_LEARNED.md referenziert sie).

## Gate-Stand nach Session-Ende

| Gate | Wert | Kommentar |
|---|---|---|
| pytest Full-Suite | 445 passed, 7 warnings, 551.69s | vollständiger Run nach Stream-C-Merge |
| ruff check | 45 errors (Baseline) | Delta 0 gegenüber pre-Integration, keine neue Regression |
| AST-Lint `mart.*`-only | grün | Read-Modul-Invariante (ADR-0029) unverändert |
| Git-Status | clean | keine offenen Änderungen, `main` synchron mit `origin/main` |
| ADR-Status | 33 ADRs, 2 `Proposed` (0030, 0032), Rest `Accepted` | ADR-0033 Accepted seit T2.7P |

## Was für die nächste Session relevant ist

### Operator-Entscheidung: nächster Bolt

**Option 1 — T2.5D-Validation (empfohlen):**
Bitemporale Rosters mit echten Daten (nflverse-Bulk + `(official_context_web, rosters)`) durchspielen. ADR-0032 von `Proposed` auf `Accepted` kippen, wenn die Trade-/Release-Heuristik stabil trägt. Fachlicher Vorteil: ein v1.0-Cut mit `Proposed`-ADR-0032 wäre architektonisch halbwegs. Umfang: ein Claude-Code-Session.

**Option 2 — T2.8 v1.0 Cut auf DEV-LAPTOP:**
Tag `v1.0.0-laptop` auf `main`, Release-Notes mit Domänen-Coverage + bekannten Grenzen + Quarantäne-Stand, `PROJECT_STATE.md` auf „v1.0 feature-complete on DEV-LAPTOP" aktualisieren, Handoff-Dokument für Testphase. **Kein VPS-Deploy in T2.8**. Umfang: eine halbe Claude-Code-Session, reine Doku-Arbeit.

### Open Loops für spätere Tranchen

- **Feature-Branch-Löschung** (`feature/t27-observability|resilience|hardening`) — ausstehend, Operator-Entscheidung; kann mit T2.8-Release-Notes gebündelt werden.
- **HTTP-Mirror für Health-Probes** — bewusst deferred bis ein echter Web-Router landet (frühestens T2.6I oder T2.9).
- **Log-Rotation / Retention für `file:`-Destination** — `events_YYYYMMDD.jsonl` läuft aktuell unbegrenzt; Cleanup per Analogie zu `trim-run-events` denkbar, aber nicht gebraucht bis Testphase.
- **`job_run_id`-Kontext in Runner-Executor-Hooks** — aktuell nicht gesetzt, weil `job_run_id` im Executor-Body nicht direkt verfügbar ist; Executor-Signatur um `job_run_id: str | None = None` erweitern wäre ein einfacher Folge-Bolt.
- **Backup als Runner-Job** — `register_job_executor` existiert noch nicht; sobald ein Executor-Registry-Pfad steht, Cron-Job für tägliches Backup einrichten.
- **`replay-domain --all`-Modus** — derzeit genau eine Domain pro Call; `--all` über alle sechs Specs wäre trivial nachzurüsten bei Operator-Bedarf.

### Methodisch festgelegt für die nächste parallele Tranche

- **`git worktree add c:/projekte/newnfl.wt/<stream>`** statt Branch-Flips im Haupt-Checkout — Memory `project_parallel_streams_shared_workdir.md` entsprechend aktualisieren.
- **Ruff-Baseline-Zahl** vor Tranche-Start dokumentieren; Gate ist „Delta 0".
- **Monitor-Tool** für "warte auf Exit", nicht Bash-Polls.
- **Pytest auf Windows mit File-Redirect**: `-u -v`, nicht `-q`.
- **Full-Suite pro Tranche, nicht pro Commit**: 1 Run statt 5.
- **Lessons-Doc parallel zur letzten Testrun-Wartezeit schreiben**, nicht danach.

## Referenzen

- Konsolidierte Lesson: [docs/LESSONS_LEARNED.md](../LESSONS_LEARNED.md) § „2026-04-23 — T2.7A-E Parallel-Streams + T2.7F Integration"
- Stream-Drafts (historisch): [lessons_t27a.md](lessons_t27a.md), [lessons_t27b.md](lessons_t27b.md), [lessons_t27c.md](lessons_t27c.md)
- Vorheriger Handoff: [chat_handoff_20260423-2350_t27p-registry-complete.md](chat_handoff_20260423-2350_t27p-registry-complete.md)
- Merge-Commits: `1eee163` (A), `a7575dc` (B), `1cada42` (C)
- ADR-0033 (Registry-Pattern) Accepted seit T2.7P — die Architektur-Vorbereitung, die diese Parallelität möglich gemacht hat.
