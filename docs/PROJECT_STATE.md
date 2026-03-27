# NEW NFL – Project State

## 1. Projektmission

Aufbau eines privaten, robusten NFL-Daten- und Analysezentrums mit
historischer Tiefe, regelmäßiger Aktualisierung, mehrstufiger Datenhaltung,
komfortabler Weboberfläche und späterer Analyse-/Simulationsfähigkeit.

## 2. Aktuelle Phase

**Phase:** Methodikdefinition und Methodik-Härtung vor Architektur und vor Runtime-Implementierung

## 3. Aktuell gültige Leitdokumente

- `docs/ENGINEERING_MANIFEST.md`
- `docs/WORKING_AGREEMENT.md`
- `docs/HANDOFF_MANIFEST.md`
- `docs/HANDOFF_GUIDE.md`
- `docs/TEST_STRATEGY.md`
- `docs/RELEASE_PROCESS.md`

## 4. Operative Struktur für Wiederaufnahme

- Handoffs liegen unter `docs/_handoff/`
- Release-Evidence liegt unter `docs/_ops/releases/`
- Quality-Gate-Evidence liegt unter `docs/_ops/quality_gates/`

## 5. Was bereits feststeht

- Das Projekt wird als neues Repo / neuer Neuaufbau gedacht.
- Das bisherige NFL-Repo dient als fachliche Referenz, nicht als operative Basis.
- Die methodische Grundlage wird aus dem reiferen Capsule-Engineering-Ansatz abgeleitet.
- Vorrang haben Methodik, Handoffs, Architektur und Governance vor frühem Coding.
- Deployment-Ziel ist ein Windows-VPS.
- Andreas arbeitet primär in VS Code und PowerShell.
- Operative Schritte müssen den Ausführungsort klar benennen.

## 6. Was noch offen ist

- endgültige Repo-Grundstruktur
- Datenbank- / Speicherstrategie
- Layer-Modell im Detail
- Source-Tiering
- Canonical Schema
- Web-Architektur
- Scheduler-/Dienstemodell
- Observability-Konzept im technischen Detail
- Release-/Versionierungstakt im späteren Runtime-Betrieb

## 7. Aktuell bevorzugter nächster Schritt

Nach Abschluss der Methodik-Härtung folgt die Architekturphase von NEW NFL:
- Ziel-Repo-Struktur
- Systemlayer
- Datenspeicher und Rollen
- Source-Tiering und Provenance-Modell
- Betriebsmodell auf dem Windows-VPS

## 8. Aktueller Handoff-Status

Noch kein operativer Handoff nötig, da bisher nur methodische Grundstruktur ohne offenen Zwischenzustand vorliegt.

## 9. Pflegehinweis

Dieses Dokument ist nach jeder relevanten Tranche zu prüfen und bei Bedarf zu aktualisieren.
