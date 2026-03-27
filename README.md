# NEW NFL

NEW NFL ist der methodisch neu aufgesetzte Nachfolger des bisherigen NFL-Projekts.
Das Ziel ist ein privat betriebenes, robustes NFL-Daten- und Analysezentrum mit
historischer Tiefe, regelmäßiger Aktualisierung, konsolidierten Datenmodellen,
komfortabler Weboberfläche und späteren Analyse-/Simulationsfähigkeiten.

Diese Tranche liefert bewusst weiterhin **keine Runtime-Komponenten**.
Sie härtet die Arbeitsmethode, Repo-Hygiene, Handoff-Regeln und
betriebsnahen Dokumentations-Einstiegspunkte, bevor Architektur und Code starten.

## Ziel dieser Tranche

- Engineering-Methode weiter in Richtung Endfassung schärfen
- Repo-Hygiene und plattformübergreifende Dateiregeln festlegen
- Handoffs operativ verankern
- Quickstart, Runbook und Observability-Struktur vorbereiten
- den Weg für die Architekturphase freimachen

## Aktueller Status

- Methodik: in Härtung, belastbare Basis vorhanden
- Architektur: noch offen
- Runtime-Code: noch nicht gestartet
- Deployment: noch nicht gestartet

## Nächster logischer Schritt

1. Diese Tranche ins Repo übernehmen.
2. Die Methode gegen den echten Arbeitsmodus prüfen.
3. Danach Architektur in klaren ADR- und Konzept-Tranchen definieren:
   - Layer-Modell
   - Datenbanken / Speicher
   - Source-Tiering
   - Schemata / Keys / Provenance
   - VPS-Betriebsmodell

## Dokumentationsstart

- `docs/INDEX.md`
- `docs/PROJECT_STATE.md`
- `docs/ENGINEERING_MANIFEST.md`
- `docs/WORKING_AGREEMENT.md`
