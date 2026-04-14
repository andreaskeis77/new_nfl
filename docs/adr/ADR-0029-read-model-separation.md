# ADR-0029: Read-Model Separation — `mart.*` is the Only Read Path for UI/API

## Status
Accepted (2026-04-14, umgesetzt in T2.3D)

## Kontext
Aktuell liest die lokale Web-Preview teilweise direkt aus `core.*`. Mit wachsender UI-Surface (Phase-1-Domänen, Vergleichs-Views in v1.1) entsteht ein Architektur-Risiko: UI-Performance-Bedürfnisse drücken auf den kanonischen Kern (Denormalisierung, View-spezifische Spalten), was Konsolidierung und Konfliktauflösung schwerer macht.

## Entscheidung
**UI und HTTP-API lesen ausschließlich aus `mart.*` (und `meta.*` für Operator-Sichten auf Runs/Quarantäne).** Direktzugriff auf `raw/`, `stg.*` oder `core.*` aus UI/API ist verboten.

- `mart.*` ist vollständig aus `core.*` rebuildbar.
- `mart.*`-Tabellen sind **versioniert** (`mart.player_overview_v1`, später `_v2`).
- UI-Performance-Optimierungen (Denormalisierung, vorberechnete Aggregate) erfolgen ausschließlich in `mart.*`.
- `mart.*`-Build ist ein eigener Job-Typ im Runner.

Verstöße sind Architekturfehler und Blocker im Code-Review.

## Begründung
- saubere Entkopplung von Modellierungs- und Performance-Concerns.
- Versionierung erlaubt UI-Iteration ohne Schema-Bruch im Kern.
- klare Verantwortlichkeit: Core → Wahrheit, Mart → Lesbarkeit.

## Konsequenzen
**Positiv:** Refactors am Core brechen UI nicht (mart.* puffert); UI-Iteration ist schnell.
**Negativ:** initial mehr Schema-Pflege, Doppelhaltung gleicher Daten.

## Alternativen
1. UI liest direkt aus Core — kurzfristig schneller, mittel-/langfristig erodiert es den Kern.
2. Views statt Tabellen in `mart.*` — kein Performance-Puffer, sonst akzeptabel; bleibt erlaubt für einfache Read-Modelle.

## Rollout
- T2.3D: Schema `mart` anlegen, erstes Read-Modell migrieren, Refactor `core_browse.py` etc.
- Lint-Regel oder Test, der Direktzugriffe aus `web*`/`api*` auf `core.*`/`stg.*`/`raw/` als Fehler markiert.

## Offene Punkte
- Konkrete Versionierungs-Konvention (`_v<N>` vs Schema `mart_v<N>`) — Default `_v<N>` (in T2.3D umgesetzt).

## Implementierungs-Notizen (T2.3D, 2026-04-14)

- Erste Projektion: `mart.schedule_field_dictionary_v1`, voll rebuildbar aus `core.schedule_field_dictionary`. Spaltenform: kanonische Felder (`field`, `data_type`, `description`) plus pre-normalisierte Filter-Spalten (`field_lower`, `data_type_lower`) plus Build-Provenance (`source_file_id`, `source_adapter_id`, `source_canonicalized_at`, `built_at`).
- Builder ist **Spalten-tolerant**: optionale Provenance-Spalten werden über `DESCRIBE` erkannt und durch `NULL` ersetzt, wenn das Quell-Schema sie (noch) nicht trägt. Erlaubt parallelen Roll-out neuer `core.*`-Tabellen ohne Bruch.
- Runner-Executor `mart_build` (registriert als Default, neben `fetch_remote`/`stage_load`/`custom`) macht jeden Mart-Build über `meta.job_run` evidenz-belegt. Operator-Pfad: `cli mart-rebuild --mart-key <key>`.
- `core-load --execute` ruft den Builder synchron am Ende — der UI-Lesepfad wird nach jeder Core-Promotion automatisch konsistent. Manueller `mart-rebuild` bleibt für isolierte Mart-Schema-Bumps (`_v<N>` → `_v<N+1>`) der primäre Pfad.
- Lint-Wand: `tests/test_mart.py::test_read_modules_do_not_reference_core_or_stg_directly` parst Read-Module per AST und schlägt Alarm, sobald ein String-Literal `core.`/`stg.`/`raw/` enthält. Docstrings sind exempt.
- Aktuelle Read-Module unter Lint-Schutz: `core_browse.py`, `core_lookup.py`, `core_summary.py`, `web_preview.py`, `web_server.py`. Modul-Namen behalten das `core_*`-Präfix für Phase-1-Stabilität — semantisch sind es Mart-Reader.

Offene Punkte → Folge-Tranchen:
- Modul-Umbenennung `core_browse.py` → `mart_browse.py` etc. wird gebündelt nach T2.5 (Domain Expansion), wenn ohnehin neue Read-Module entstehen.
- Provenance-Verkettung Mart-Build ↔ auslösender Ingest-Run ist heute über `meta.job_run` verfolgbar, aber nicht über die Mart-Tabelle selbst. Bei `_v2` ergänzen.
- `mart.*`-Build-Job gehört in den Scheduler (T2.7), heute nur On-Demand.
