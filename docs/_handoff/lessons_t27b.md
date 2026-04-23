# Lessons Learned — Stream B (Resilience), T2.7C + T2.7D

**Date:** 2026-04-23
**Branch:** `feature/t27-resilience`
**Commits:** `b234b59` (T2.7C) + `5be3aa7` (T2.7D)
**Test-Delta:** +37 resilience-specific tests (alle grün); keine bestehenden Tests modifiziert.

---

## 1. Was gebaut wurde

### T2.7C — Backup-Drill

* `new_nfl.resilience.backup.backup_snapshot(settings, target_zip)` → verifizierbares ZIP aus DuckDB (CHECKPOINT) und `data/raw/`-Baum, plus `manifest.json`.
* `new_nfl.resilience.restore.restore_snapshot(source_zip, target_dir)` → Extract + SHA-256-Verify; blockt Pfad-Traversal (`..`, absolut).
* `new_nfl.resilience.verify.verify_snapshot(source_zip)` → on-the-fly-Hash des Bytestreams, kein Extract.
* CLI: `new-nfl backup-snapshot|restore-snapshot|verify-snapshot` via ADR-0033-Plugin.

### T2.7D — Replay-Drill

* `new_nfl.resilience.diff.diff_tables(con_a, con_b, table, key_cols, exclude_cols=...)` → `TableDiff(only_in_a, only_in_b, changed)`.
* `new_nfl.resilience.replay.replay_domain(settings, domain, source_file_id=None, dry_run=False)` → snapshot+rerun+diff für sechs Kerndomains (team/game/player/roster_membership/team_stats_weekly/player_stats_weekly).
* CLI: `new-nfl replay-domain --domain <d> [--source-file-id ID] [--dry-run]`.

### Settings

Additive Property `Settings.backup_destination_dir` → `data_root/"backups"`. Kein Caller heute — reine Vorbereitung für Scheduler-Jobs.

---

## 2. Determinismus-Verträge (nicht verwässern!)

### Backup-Payload-Hash

`manifest.payload_hash` hasht **nur**:
* `schema_version`
* `db_filename`
* `file_hashes` (sorted)
* `row_counts` (sorted)

Explizit **ausgeschlossen**: `created_at`, `duckdb_version`. Diese sind Provenienz, nicht Payload. Der Test `test_backup_is_payload_deterministic_across_two_runs` erzwingt: zwei Backups identischer Eingaben → identischer `payload_hash`. ZIP-Metadaten (entry mtime, compressed size) dürfen abweichen — **die Payload nicht**.

### Replay-Diff auf unchanged raw

`test_replay_on_unchanged_raw_has_empty_diff` ist der Kern-Test: bei unchanged raw **muss** der Diff leer sein (exklusive `_canonicalized_at` / `_loaded_at`). Wenn dieser Test je failed — nicht den Test abschwächen! Es bedeutet einen Determinismus-Bug im core-load (nicht-idempotenter Promoter, Timestamp außerhalb der Default-Exclude-Liste, nicht-deterministischer Tie-Break). Das ist ein blockierender Defekt für den Resilience-Drill und muss eskaliert werden.

---

## 3. Stolperstein: TIMESTAMPTZ + pytz

Der initiale Replay-Test hat mit `_duckdb.InvalidInputException: Required module 'pytz' failed to import` failed. Wurzel: `core.team._canonicalized_at` ist als `TIMESTAMP WITH TIME ZONE` typisiert, und DuckDB benötigt `pytz` (optional dep!), um `TIMESTAMPTZ → Python datetime` zu konvertieren. `pytz` ist **nicht** in `pyproject.toml`.

### Zwei-Pronged Fix (ohne pytz-Dependency)

1. **`_copy_table_to_snapshot` in `replay.py`** → von Python-Fetch+Bulk-Insert auf **reines SQL** umgestellt:
   ```python
   snap_con.execute(f"ATTACH '{live_db_path}' AS live_src (READ_ONLY)")
   snap_con.execute(f"CREATE TABLE {qualified} AS SELECT * FROM live_src.{qualified}")
   snap_con.execute("DETACH live_src")
   ```
   Kein Python-Round-Trip, kein pytz. Voraussetzung: Live-Verbindung vorher schließen (ATTACH braucht freies Handle).

2. **`_fetch_rows` in `diff.py`** → TIMESTAMPTZ-Spalten werden on-the-fly zu VARCHAR gecastet, bevor der Fetch passiert. Da `_canonicalized_at`/`_loaded_at` in `DEFAULT_EXCLUDE_COLS` stehen, ändert der Cast keine Diff-Semantik.

**Lesson für künftige Streams:** Wenn ein Operator-Command gegen `core.*`-Tabellen mit Timestamps arbeitet und kein pytz will — **nie** `fetchall()` auf einer TIMESTAMPTZ-Spalte. Entweder pure-SQL (ATTACH/CTAS) oder VARCHAR-Cast.

---

## 4. ADR-0033-Disziplin gehalten

* **Keine** Änderungen an `cli.py`, `build_parser()`, `runner.py`, `mart/`, `core/`, `web/`, `adapters/`.
* Ein einziges neues Plugin-Modul: `src/new_nfl/plugins/resilience.py` registriert vier `CliPlugin`-Instanzen.
* Ein einziger additiver Import in `plugins/__init__.py` (neben dem bestehenden `registry_inspect`).
* Keine Job-Executor-Registrierung (existiert im T2.7P-Registry-Skelett noch nicht — kein Workaround gebaut, stattdessen CLI-Plugin-only bestätigt im Realitäts-Check).

---

## 5. Test-Inventar

| Datei              | Tests | Schwerpunkt                                                                  |
|--------------------|-------|------------------------------------------------------------------------------|
| `test_diff.py`     | 9     | identisch, only_in_a/b, changed, default-/custom-exclude, composite key, frozen |
| `test_backup.py`   | 14    | Layout, Forward-Slashes, SHA-256, Determinismus, leeres raw, Verify-Flows   |
| `test_restore.py`  | 8     | Reconstruct, Smoke-Query, non-zip/tampered/unsafe-path/missing-manifest     |
| `test_replay.py`   | 6     | Domain-Registry, dry_run ohne Mutation, empty diff, missing core table      |

**Summe Stream B: 37 Tests, alle grün.**

---

## 6. Offen / Nächste Schritte

* **Backup-Command im Runner.** T2.7P hat `register_job_executor` noch nicht, daher kein `backup-snapshot`-Job. Sobald Stream A/P einen Executor-Registry-Pfad anbietet, sollte ein Cron-Job `backup-snapshot` täglich auf `settings.backup_destination_dir` feuern.
* **Multi-Domain-Replay.** Derzeit replay't `replay-domain` genau **eine** Domain. Ein `--all`-Modus über alle sechs Specs ist trivial nachzurüsten; wurde bewusst nicht gebaut bis ein Operator-Bedarf sichtbar wird.
* **Restore-Smoke ohne Extract.** `verify-snapshot` prüft Hashes, aber nicht "kann DuckDB die enthaltene DB öffnen?". Ein Extended-Mode mit In-Memory-Attach wäre ein Follow-up.

---

## 7. Meta: Parallel-Worktree-Fallen

**Stolperstein während der Session:** der Worktree wurde von parallelen Agenten zwischen Branches umgeschaltet (`t27-resilience` ↔ `t27-observability` ↔ `t27-hardening`), was Edits in `plugins/__init__.py` und `settings.py` zwischenzeitlich wegriss, weil diese Dateien auf jedem Branch andere Basis-Inhalte haben. Fix: Edits so früh wie möglich auf dem Ziel-Branch **committen** statt im Arbeitsbaum liegen zu lassen. Untracked-Files überleben Checkouts; modifizierte Tracked-Files dagegen können in einem Switch "verschwinden", wenn der Ziel-Branch andere Inhalte hat.

**Lesson:** Bei Stream-parallelen Agenten jedes Feature-Artefakt unmittelbar nach Test-Grün committen. Nicht "später alles zusammen".
