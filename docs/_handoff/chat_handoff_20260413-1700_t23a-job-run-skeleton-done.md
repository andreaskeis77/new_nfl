# Chat-Handoff 2026-04-13 17:00 — T2.3A Job-/Run-Modell-Skeleton abgeschlossen

## Trigger
§2.1 „Tranche-Abschluss + größerer Themenwechsel": T2.3A ist done (Schema + Modelle + CLI + Tests), der nächste Schritt T2.3B ist thematisch deutlich anders (Worker-Loop, Laufzeit-Verhalten, atomares Claim auf DuckDB — nicht mehr reines Modellieren). Zusätzlich §2.1 „Kontext-Druck": die Session hat v0.3-Architektur-Baseline, Handoff-/Lessons-Infrastruktur und T2.3A in einem Lauf produziert; vor Beginn der Runner-Arbeit ist ein sauberer Cut sinnvoll.

## Was wurde in dieser Session erreicht

- **T2.3A — Job-/Run-Modell-Skeleton** vollständig geliefert:
  - 7 neue `meta.*`-Tabellen über `TABLE_SPECS` / `ensure_metadata_surface` in `src/new_nfl/metadata.py`:
    `retry_policy`, `job_definition`, `job_schedule`, `job_queue`, `job_run`, `run_event`, `run_artifact`.
  - Modul `src/new_nfl/jobs/` mit `__init__.py` und `model.py` (Pydantic-Modelle + Service-Funktionen
    `register_retry_policy`, `register_job`, `upsert_schedule`, `enqueue_job`, `list_jobs`, `describe_job`).
  - CLI-Surface in `src/new_nfl/cli.py`: `list-jobs`, `describe-job`, `register-job`, `register-retry-policy`.
  - Tests `tests/test_jobs_model.py` (7 Cases) + `tests/test_jobs_cli.py` (5 Cases), **Suite 73/73 grün** (~78 s).
  - Ruff auf neuen Dateien clean (11 verbleibende Ruff-Befunde sind pre-existing, nicht aus T2.3A).
- Dokumentation aktualisiert: `PROJECT_STATE.md`, `T2_3_PLAN.md` (T2.3A abgehakt, T2.3B als nächster Bolt), `ADR-0025` (Status-Update + Implementierungs-Notizen).
- Lessons-Learned-Draft zu T2.3A in `docs/LESSONS_LEARNED.md` (Status `draft`, wartet auf Operator-Freigabe).

## Was ist offen / unklar / Risiko

- **Lessons-Learned-Draft T2.3A** ist `draft`, Operator-Freigabe ausstehend (`docs/LESSONS_LEARNED.md`, oberster Eintrag).
- **Lessons-Learned-Draft Use-Case-Baseline (2026-04-13 früher)** ist ebenfalls noch `draft` — beide sollten zusammen freigegeben werden.
- **Helper-Duplikation** zwischen `src/new_nfl/jobs/model.py` (`_connect`, `_row_to_dict`, `_new_id`) und `src/new_nfl/metadata.py`. Bewusst in T2.3A nicht refaktoriert, aber in T2.3B zusammenführen (z. B. in `src/new_nfl/_db.py`) bevor Runner, Quarantine, Ontology weitere Duplikate erzeugen. Siehe LL-Draft §4.
- **Concurrency-Key-Strategie pro Quelle** und **Backoff-Defaults pro Jobtyp** — offen laut ADR-0025 „Offene Punkte". Für T2.3B notwendig.
- **`ADR-0025` steht weiterhin auf „Proposed"**, Final-Accept erst nach T2.3B.
- Uncommitted Changes im Repo (Status-Dump am Session-Start zeigte viele `??` und `M` Dateien) — Git-Commit-Hygiene am Ende dieser Session einzuplanen.

## Aktueller Arbeitsstand

- **Phase:** T2.3 Foundation Hardening, T2.3A done, Übergang zu T2.3B.
- **Letzter erfolgreicher Pflichtpfad:** `pytest` 73/73 grün (u. a. `tests/test_jobs_model.py`, `tests/test_jobs_cli.py`). Manuelle CLI-Checks auf `list-jobs` / `describe-job` per Tests abgedeckt.
- **Nächster konkreter Schritt:** **T2.3B — Internal Runner** gemäß `T2_3_PLAN.md` §2 und `ADR-0025`. Ziel: Worker-Loop, der `meta.job_queue` atomar claimt (Idempotency-Key, atomarer Update-Claim), Job ausführt, `meta.job_run` + `meta.run_event` + `meta.run_artifact` schreibt, Retries gemäß `meta.retry_policy` fährt. Artefakte: `src/new_nfl/jobs/runner.py`, `cli run-worker --once`, `cli run-worker --serve`. Pflichtpfade: `fetch-remote` und `stage-load` über den Runner ausführbar. DoD: Replay eines fehlgeschlagenen Runs reproduziert deterministisch.

## Geänderte / neue Dokumente in dieser Session

- **Neu:** `src/new_nfl/jobs/__init__.py`, `src/new_nfl/jobs/model.py`
- **Neu:** `tests/test_jobs_model.py`, `tests/test_jobs_cli.py`
- **Neu:** `docs/_handoff/chat_handoff_20260413-1700_t23a-job-run-skeleton-done.md` (dieses Dokument)
- **Geändert:** `src/new_nfl/metadata.py` (7 neue `TABLE_SPECS`-Einträge)
- **Geändert:** `src/new_nfl/cli.py` (Job-Kommandos + Dispatch)
- **Geändert:** `docs/PROJECT_STATE.md` (Phase, Completed, Runtime-Posture, Next-Bolt)
- **Geändert:** `docs/T2_3_PLAN.md` (T2.3A als abgeschlossen markiert)
- **Geändert:** `docs/adr/ADR-0025-internal-job-and-run-model.md` (Status, Rollout, Implementierungs-Notizen)
- **Geändert:** `docs/LESSONS_LEARNED.md` (neuer Top-Eintrag T2.3A, Status `draft`)

## Lessons-Learned-Eintrag

Siehe `docs/LESSONS_LEARNED.md` Eintrag „2026-04-13 — T2.3A Job-/Run-Modell-Skeleton" (Status `draft`, Operator-Freigabe offen).

## Vor dem Wechsel noch zu tun (in dieser Session)

1. Operator-Freigabe für die zwei offenen Lessons-Learned-Drafts (heute Use-Case-Baseline + heute T2.3A).
2. Optional: Git-Commit aller neuen/geänderten Dateien mit Präfix `Handoff:` bzw. `T2.3A:`.

## Starter-Prompt für die neue Session

```text
Du übernimmst das Projekt **NEW NFL** (privates NFL-Daten-/Analysesystem,
Single-Operator, Python 3.12, DuckDB-Zentrum, Windows-VPS-Ziel ab v1.0).
Repo lokal: c:\projekte\newnfl
Repo remote: https://github.com/andreaskeis77/new_nfl

**Pflichtlektüre vor jedem größeren Schritt — in dieser Reihenfolge:**
1. docs/PROJECT_STATE.md
2. docs/_handoff/chat_handoff_20260413-1700_t23a-job-run-skeleton-done.md
3. docs/ENGINEERING_MANIFEST_v1_3.md
4. docs/concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md
5. docs/T2_3_PLAN.md
6. docs/UI_STYLE_GUIDE_v0_1.md (für UI-Tranches ab T2.6)
7. docs/CHAT_HANDOFF_PROTOCOL.md
8. docs/LESSONS_LEARNED_PROTOCOL.md
9. docs/LESSONS_LEARNED.md
10. docs/adr/README.md (insb. ADR-0025 bis ADR-0030)
11. docs/adr/ADR-0025-internal-job-and-run-model.md (Stand nach T2.3A,
    inklusive „Implementierungs-Notizen (T2.3A)")

**Verbindliche Regeln:**
- Engineering Manifest v1.3 gilt vollständig (Prio-Reihenfolge §2, Prinzipien §3.1–3.13).
- Befehle immer mit Ausführungsort kennzeichnen: DEV-LAPTOP / VPS-USER / VPS-ADMIN.
  In dieser Phase ist alles DEV-LAPTOP.
- Vollständige Dateien liefern, keine Patch-Snippets (Manifest §7.5).
- Operator-Aktionen sind in v1.0 CLI-only, UI-Buttons erst v1.1.
- UI/API liest ausschließlich aus mart.* (ADR-0029).
- Quarantäne ist First-Class (ADR-0028), Replay aus immutable Raw ist Pflicht.
- Personen-/Teamnamen immer in offizieller Vollform (UI Style Guide §1).
- Schlage proaktiv einen Chat-Handoff vor, sobald ein Trigger aus
  CHAT_HANDOFF_PROTOCOL.md §2.1 zutrifft.
- Aktualisiere PROJECT_STATE und den aktiven Plan (T2_3_PLAN.md) automatisch
  nach jedem Tranche-Abschluss.
- Erstelle nach jeder Tranche einen Lessons-Learned-Eintrag (draft) gemäß
  LESSONS_LEARNED_PROTOCOL.md.
- Termine werden gegen reale Tranche-Last validiert, bevor sie übernommen werden.

**Aktueller Stand:**
- T2.3A (Job-/Run-Modell-Skeleton) abgeschlossen 2026-04-13:
  7 meta.*-Tabellen (retry_policy, job_definition, job_schedule, job_queue,
  job_run, run_event, run_artifact), Pydantic-Modelle in
  src/new_nfl/jobs/model.py, CLI list-jobs / describe-job / register-job /
  register-retry-policy, Tests grün (73/73).
- ADR-0025 Status: Proposed, Schema in T2.3A implementiert, Final-Accept
  erst nach T2.3B.
- 2 Lessons-Learned-Drafts offen (Use-Case-Baseline, T2.3A) — Freigabe
  durch Operator abfragen, bevor du T2.3B startest.
- Zielkorridor: v1.0 feature-complete bis Ende Juni 2026, Testphase Juli,
  produktiv vor Preseason-Start Anfang August 2026.

**Konkreter nächster Schritt:**
**T2.3B — Internal Runner** gemäß T2_3_PLAN.md §2 und ADR-0025.
Konkret:
- Modul src/new_nfl/jobs/runner.py mit Claim-Loop (atomarer UPDATE auf
  meta.job_queue mit Idempotency-/Concurrency-Key-Schutz), Execution,
  Schreiben von meta.job_run / meta.run_event / meta.run_artifact,
  Retry-Logik über meta.retry_policy.
- CLI-Kommandos `cli run-worker --once` und `cli run-worker --serve`.
- Migration der bestehenden Pflichtpfade `fetch-remote` und `stage-load`
  auf Job-Submission + Runner-Ausführung.
- Gemeinsames DB-Helper-Modul (z. B. src/new_nfl/_db.py) einziehen, um
  Helper-Duplikation zwischen metadata.py und jobs/model.py zu beenden
  (siehe Lessons Learned 2026-04-13 T2.3A §4).
- Tests: Claim-Atomarität (zwei gleichzeitige Claims → einer gewinnt),
  Retry-Pfad, Replay eines fehlgeschlagenen Runs reproduziert
  deterministisch.
- DoD: Replay eines fehlgeschlagenen Runs reproduziert deterministisch;
  Suite grün; ADR-0025 bleibt „Proposed" bis Final-Accept am T2.3B-Ende.

Lies erst die Pflichtlektüre, dann bestätige Verständnis in 5 Bullets,
dann frage nach Freigabe für T2.3B.
```

## Verweise

- `docs/CHAT_HANDOFF_PROTOCOL.md`
- `docs/LESSONS_LEARNED_PROTOCOL.md`
- `docs/T2_3_PLAN.md`
- `docs/adr/ADR-0025-internal-job-and-run-model.md`
- `docs/_handoff/chat_handoff_20260413-1530_use-cases-and-architecture-baseline.md` (Vor-Handoff derselben Arbeitsperiode)
