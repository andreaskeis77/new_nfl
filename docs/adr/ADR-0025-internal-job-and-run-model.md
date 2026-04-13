# ADR-0025: Internal Job and Run Model in DuckDB Metadata

## Status
Proposed — Schema in T2.3A (2026-04-13) implementiert, Final-Accept am Ende von T2.3B nach Runner-Verifikation.

## Kontext
NEW NFL braucht in v1.0 einen autonomen Scheduler, der Quellen periodisch abruft, Stage-Loads ausführt, Promotionen in den Kanon triggert und Fehler nicht still verschluckt. v0.2 hat dies offengelassen. Externe Orchestratoren (Airflow, Dagster, Temporal, Celery) sind für einen single-operator Windows-VPS überdimensioniert und teilweise OS-inkompatibel (Celery ≥ 4.x kein Windows).

## Entscheidung
Wir bauen einen **internen, datenbankgestützten Job-Runner** auf der DuckDB-Metadatenfläche. Tabellenfamilie in `meta.*`:

- `meta.job_definition`
- `meta.job_schedule`
- `meta.job_queue`
- `meta.job_run`
- `meta.run_event`
- `meta.run_artifact`
- `meta.retry_policy`

Claims erfolgen über atomare DuckDB-Updates mit Idempotency-Keys. Worker-Prozess wird über CLI gestartet (`cli run-worker --serve`). Auf dem VPS später als Windows-Service. OS-Scheduler nur als Watchdog/Trigger.

**Nicht Teil dieser Entscheidung:** verteilte Worker, externe Queue-Backends (Redis, RabbitMQ).

## Begründung
- Single-Operator-Setup, kein Multi-Tenancy.
- DuckDB ist bereits zentral; zusätzlicher Store wäre Komplexität ohne Nutzen.
- Volle Kontrolle über Run-Evidence und Provenance.
- OS-neutral, Windows-tauglich.
- Spätere Migration auf Postgres möglich, falls Multi-Writer-Druck entsteht.

## Konsequenzen
**Positiv:** keine externen Abhängigkeiten, einheitliches Backup, Run-Evidence direkt in DuckDB queryable, Replay deterministisch.
**Negativ:** Worker-Skalierung auf einen Prozess beschränkt (Phase-1 ausreichend); kein UI „out of the box" wie bei Airflow.
**Risiken:** DuckDB-Concurrency-Limits bei stark parallelen Writes — in v1.0 nicht relevant (sequenzieller Worker).

## Alternativen
1. Airflow — zu schwergewichtig für Single-Operator-VPS.
2. Dagster — gute Konzepte, aber Setup-Overhead.
3. Celery + Redis — Windows-Inkompatibilität, externer Broker.
4. APScheduler in-Process ohne Persistenz — keine Run-Evidence, kein Replay.

## Rollout
- T2.3A: Schema-Migration. **Erledigt 2026-04-13.** Tabellen in `src/new_nfl/metadata.py::TABLE_SPECS`. Pydantic-Modelle in `src/new_nfl/jobs/model.py`. CLI-Surface: `list-jobs`, `describe-job`, `register-job`, `register-retry-policy`.
- T2.3B: Worker-Loop, Migration bestehender CLI-Aufrufe (`fetch-remote`, `stage-load`) auf Job-Submission.
- Backout: alte CLI-Direktaufrufe bleiben für eine Übergangsphase parallel verfügbar.

## Implementierungs-Notizen (T2.3A)
- Schema-Entscheidungen:
  - `meta.retry_policy.policy_key` ist logischer Schlüssel, `retry_policy_id` UUID-PK. Jobs referenzieren `retry_policy_id`.
  - `meta.job_queue.claim_status` ∈ {`pending`, `claimed`, `done`, `abandoned`}.
  - `meta.job_queue.idempotency_key` erlaubt `enqueue_job`-Deduplizierung innerhalb `pending`/`claimed`.
  - `meta.job_run.run_status` ∈ {`pending`, `running`, `success`, `failed`, `retrying`, `quarantined`}.
  - `meta.run_artifact.artifact_kind` ist bewusst frei gehalten (z. B. `ingest_run`, `source_file`, `receipt`) um Kopplung an bestehende Domänen weich zu halten.
- `ensure_metadata_surface` erzeugt die Tabellen idempotent über `TABLE_SPECS`; bestehende Backfill-Hooks sind neutral (keine Legacy-Vorgänger).

## Offene Punkte
- Concurrency-Key-Strategie pro Quelle.
- Backoff-Defaults pro Jobtyp.
