# ADR-0028: Quarantine as First-Class Domain

## Status
Accepted (2026-04-14, umgesetzt in T2.3C)

## Kontext
Bisher werden Fehler beim Fetch / Parse / Stage-Load über Logs sichtbar, aber nicht als persistente Domäne geführt. Das widerspricht dem Manifest-Prinzip „Fail loud on data integrity" und macht Recovery zu einer Ad-hoc-Aktivität.

## Entscheidung
Quarantäne ist eine **First-Class-Domäne** mit eigenen Tabellen in `meta.*`:

- `meta.quarantine_case` — `id`, `scope_type`, `scope_ref`, `reason_code`, `severity`, `evidence_refs[]`, `first_seen_at`, `status`, `owner`, `notes`.
- `meta.recovery_action` — `id`, `quarantine_case_id`, `action_kind` (replay / override / suppress), `triggered_at`, `triggered_by`, `resulting_run_id`, `note`.

Pflichtregeln:
- Kein Pipeline-Schritt darf einen unklaren Datensatz still verwerfen.
- Jede Recovery erzeugt einen **neuen** Run mit Verweis auf die Quarantäne.
- CLI-Surface: `cli quarantine-list --open`, `cli quarantine-show <id>`, `cli quarantine-resolve <id> --action … --note …`.
- UI-Surface in v1.1.

## Begründung
- macht Datenintegritäts-Risiken sichtbar und zählbar.
- Recovery wird auditierbar.
- klare Grenze zwischen technischen Retries (intern in `retry_policy`) und fachlichen Quarantäne-Entscheidungen (Operator).

## Konsequenzen
**Positiv:** Operator hat jederzeit Überblick über offene Datenprobleme; Recovery ist reproduzierbar.
**Negativ:** zusätzlicher Pflege-Aufwand für Operator (gewollt).

## Alternativen
1. Nur Logging — verstößt gegen Manifest §3.5 / §3.12.
2. Tickets in externem System (GitHub Issues) — Bruch des Single-Store-Prinzips.

## Rollout
- T2.3C: Schema, CLI, ein synthetischer Quarantäne-Test im Pytest-Suite.

## Implementierungs-Notizen (T2.3C, 2026-04-14)

- Tabellen sind in `metadata.TABLE_SPECS` versioniert; `ensure_metadata_surface` legt sie beim Bootstrap an.
- Dedupe-Schlüssel: `(scope_type, scope_ref, reason_code)` solange Status `open` oder `in_progress`. Re-Occurrence aktualisiert `last_seen_at`, merged `evidence_refs` dedupliziert und eskaliert `severity` monoton (`info < warning < error < critical`).
- Runner-Hook: `jobs/runner._auto_quarantine_failed_run` öffnet bei jedem `runner_exhausted`-Abschluss einen Case mit `scope_type='job_run'`, `reason_code='runner_exhausted'` und dem `job_run_id` als `scope_ref`. Evidence-Ref enthält `job_key` + letzte Fehlernachricht.
- Operator-Aktionen (`meta.recovery_action.action_kind`):
  - `override` → Case `resolved`, kein neuer Run.
  - `suppress` → Case `suppressed`.
  - `replay` → verlangt `scope_type='job_run'`; ruft `jobs/runner.replay_failed_run` auf, verlinkt den neuen `job_run_id`. Bei Erfolg wird der Case `resolved`; bei erneutem Fehlschlag bleibt er `in_progress` — der Runner öffnet autom. einen neuen Case für den neuen Failed Run.
- Import-Zyklen (`runner ↔ quarantine`) werden über Lazy-Imports in den beiden Hook-Funktionen aufgelöst.
- CLI-Output folgt dem `KEY=VALUE`-Stil der anderen Job-Kommandos (grep-bar).

Offene Punkte → Folge-Tranchen:
- UI-Surface (v1.1 / T2.6).
- Schema-validierte `evidence_refs` (heute frei-form JSON) sobald die ersten Adapter stabilisiert sind.
- `owner`-Workflow (Zuweisung) kommt mit Multi-Operator-Modus (post-v1.0).
