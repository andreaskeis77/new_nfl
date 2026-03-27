# NEW NFL – Handoff Guide v1.0

## 1. Zweck

Dieses Dokument operationalisiert das Handoff-Manifest.
Es beschreibt, wie Handoffs in NEW NFL konkret angelegt, gepflegt und genutzt werden.

## 2. Ablageort

Verbindlicher Ablageort:
- `docs/_handoff/`

## 3. Dateinamensschema

Standard:
- `handoff_YYYYMMDD-HHMM_<kurztitel>.md`

Beispiele:
- `handoff_20260327-2015_method-hardening.md`
- `handoff_20260402-2240_architektur-layering.md`

## 4. Erzeugungsregeln

Ein Handoff wird erstellt oder aktualisiert, wenn:
- eine Tranche abgeschlossen wurde,
- ein RC vorliegt,
- ein roter Zustand sauber dokumentiert werden muss,
- ein Chat-/Session-Wechsel realistisch ist,
- oder ein Arbeitsstand sonst schwer wiederaufnehmbar wäre.

## 5. Inhaltliche Mindestdisziplin

Ein Handoff soll nicht nur erzählen, was gedacht wurde, sondern belastbar festhalten:
- was real geändert wurde,
- welche Artefakte existieren,
- welche Checks gelaufen sind,
- was grün / rot / offen ist,
- und welcher eine nächste Schritt empfohlen wird.

## 6. Bezug auf andere Dokumente

Ein gutes Handoff referenziert bei Bedarf:
- `docs/PROJECT_STATE.md`
- `docs/RELEASE_PROCESS.md`
- relevante ADRs
- relevante Ops- oder Quality-Gate-Artefakte

## 7. Betriebsregel

Ohne Handoff darf kein komplexer Zwischenzustand stillschweigend als „bekannt“ vorausgesetzt werden.
Wenn ein Zustand wiederaufnahmebedürftig ist, wird er dokumentiert.

## 8. Minimal-Workflow

1. Tranche oder Zwischenzustand identifizieren
2. reale Lage zusammentragen
3. Checks und Risiken benennen
4. genau einen bevorzugten nächsten Schritt formulieren
5. Handoff unter `docs/_handoff/` ablegen
6. `PROJECT_STATE.md` bei Bedarf aktualisieren
