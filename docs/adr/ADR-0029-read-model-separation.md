# ADR-0029: Read-Model Separation — `mart.*` is the Only Read Path for UI/API

## Status
Proposed (target: Accepted at end of T2.3D)

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
- Konkrete Versionierungs-Konvention (`_v<N>` vs Schema `mart_v<N>`) — Default `_v<N>`.
