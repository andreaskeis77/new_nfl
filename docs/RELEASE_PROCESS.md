# NEW NFL – Release Process v1.1

## 1. Zweck

Dieser Release-Prozess definiert, wann eine Tranche oder ein Stand als
belastbarer Entwicklungsfortschritt gilt und wie dieser Fortschritt dokumentiert wird.

## 2. Begriffe

### Tranche
Ein klar abgegrenztes Änderungspaket mit definiertem Scope, Testumfang und Doku-Update.

### Release Candidate (RC)
Ein Stand, der technisch und dokumentarisch so weit geprüft ist, dass ein Deployment
oder eine stabile Zwischenmarke sinnvoll ist.

### Release
Ein bewusst markierter, dokumentierter und wiederaufnahmefähiger Stand.

## 3. Release-Level

### 3.1 Methodik-Release
Änderungen an Manifest, Agreement, Test- oder Release-Regeln.
Noch kein Runtime-Wert, aber hoher Steuerungswert.

### 3.2 Architektur-Release
Entscheidungen zu Layern, DB-Strategie, Source-Tiering, Schemata oder Betriebsmodell.

### 3.3 Runtime-Release
Änderungen an lauffähigem Code, Jobs, APIs, Web oder Deployment.

### 3.4 Betriebs-Release
Änderungen mit Auswirkung auf VPS, Dienste, Scheduler, Secrets-Handling oder Recovery.

## 4. Voraussetzungen für einen Release Candidate

Vor einem RC muss mindestens vorliegen:

- Scope der Tranche klar
- Dateien konsistent
- relevante Gates definiert
- relevante Gates ausgeführt
- Doku abgeglichen
- Handoff aktualisiert
- Risiken benannt

## 5. Mindestartefakte je Release

Jeder Release oder RC soll nachvollziehbar hinterlassen:

- kurzer Zweck / Ziel
- betroffene Dateien oder Bereiche
- Test-/Gate-Ergebnisse
- bekannte Rest-Risiken
- nächster sinnvoller Schritt
- Referenz auf Handoff / PROJECT_STATE / ADRs

## 6. Keine stillen Releases

Ein Stand gilt nicht als Release, nur weil Dateien geändert wurden.
Ohne dokumentierte Einordnung ist es nur ein Zwischenzustand.

## 7. Verbindliche Ablage für Evidence

- `docs/_handoff/`
- `docs/_ops/releases/`
- `docs/_ops/quality_gates/`

## 8. Minimaler Release-Ablauf

1. Tranche abschließen
2. relevante Tests/Gates ausführen
3. Ergebnis bewerten
4. Doku aktualisieren
5. Handoff aktualisieren
6. RC oder Release markieren
7. nächsten Schritt festlegen

## 9. Besondere Regel für NEW NFL

Für NEW NFL sind diese Bereiche release-kritisch:
- Datenintegrität
- Konsolidierung
- Provenance
- Scheduler / Ingestion
- API-Verfügbarkeit
- Web-Browsebarkeit
- VPS-Betrieb

Änderungen in diesen Bereichen benötigen erhöhte Sorgfalt und dokumentierte Evidenz.

## 10. Definition eines guten Releases

Ein guter Release ist:
- nachvollziehbar,
- reproduzierbar,
- fachlich verständlich,
- testseitig begründet,
- dokumentarisch anschlussfähig,
- und für die nächste Session ohne Ratespiel wieder aufnehmbar.
