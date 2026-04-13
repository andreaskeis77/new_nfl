# ADR-0028: Quarantine as First-Class Domain

## Status
Proposed (target: Accepted at end of T2.3C)

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
