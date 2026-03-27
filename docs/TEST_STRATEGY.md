# NEW NFL – Test Strategy v1.0

## 1. Ziel

Diese Teststrategie stellt sicher, dass NEW NFL kontrolliert wächst und
Änderungen an Daten, Konsolidierung, Weboberfläche, Betrieb und späteren
Analytik-/Simulationsschichten nicht unbemerkt Schäden verursachen.

## 2. Grundsatz

Nicht jede Datei braucht denselben Testtyp.
Aber jede wichtige Änderung braucht eine nachvollziehbare Verifikation.

## 3. Testschichten

### 3.1 Unit Tests
Für:
- reine Python-Logik
- Mapper
- Parser
- Deduplizierung
- Normalisierung
- Schlüsselbildung
- Konflikterkennung
- Utility-Funktionen

Ziel:
- schnell
- deterministisch
- lokal ausführbar

### 3.2 Contract Tests
Für:
- Source Adapter
- Parser-Verträge
- erwartete Eingabe-/Ausgabeformen
- Kern-APIs
- DB-nahe Interfaces

Ziel:
- Änderungen an externen oder internen Schnittstellen früh sichtbar machen

### 3.3 Data Quality Tests
Für:
- Pflichtfelder
- Primärschlüssel
- Eindeutigkeit
- Referenzintegrität
- Freshness
- Wertebereiche
- logische Konsistenz

Ziel:
- fachlich verwertbare Daten sicherstellen

### 3.4 Integration Tests
Für:
- Ingestion-Flüsse
- DB-Schreibpfade
- Konsolidierung
- API + DB
- UI + API
- Job-Läufe mit Testdaten

Ziel:
- Zusammenspiel kritischer Komponenten absichern

### 3.5 Smoke Tests
Für:
- lokales Starten
- Health-Endpunkte
- minimale End-to-End-Pfade
- Scheduler-/Job-Start
- Deployment-Grundfunktion

Ziel:
- schnelle Aussage, ob das System grundsätzlich lebt

### 3.6 Ops / Runbook Checks
Für:
- Start-/Stop-Befehle
- Dienste
- Scheduled Tasks
- Logpfade
- Config-Loading
- Health-Checks
- Recovery-Pfade

Ziel:
- Betriebsfähigkeit absichern

### 3.7 Docs Checks
Für:
- Doku-Konsistenz
- referenzierte Befehle
- Dateipfade
- erwähnte Skripte / Endpunkte / Prozesse

Ziel:
- Doku-Drift begrenzen

## 4. Qualitätsgates

Welche Gates pro Tranche Pflicht sind, hängt vom Scope ab.
Mindestens wird pro Tranche ein expliziter Gatesatz festgelegt.

Beispielhafte Gates:
- `unit`
- `contract`
- `dq`
- `integration`
- `smoke`
- `ops`
- `docs`

## 5. Gate-Regeln

- Rot ist rot. Kein Schönreden.
- Bekannte, bewusst akzeptierte Ausnahmen müssen dokumentiert werden.
- Wenn ein Gate aus Zeitgründen ausgelassen wird, muss das explizit als Risiko notiert werden.
- Für produktionsnahe Änderungen sind Smoke- und Ops-Gates nicht optional.

## 6. Testdaten

- Testdaten müssen klein, reproduzierbar und rechtlich unkritisch sein.
- Für Ingestion- und DQ-Tests sind synthetische oder kontrollierte Fixtures zu bevorzugen.
- Externe Quellen sollen möglichst nicht direkt in Standardtests eingebunden werden.
  Dafür dienen Adapter-Mocks, Snapshots oder kontrollierte Fixtures.

## 7. Mindestanforderungen je Änderungstyp

### 7.1 Reine Dokuänderung
- docs-Check
- manuelle Konsistenzprüfung

### 7.2 Utility oder reine Kernlogik
- unit
- ggf. contract

### 7.3 Datenmodell / Keys / Konsolidierung
- unit
- contract
- dq
- integration

### 7.4 Source Adapter
- unit
- contract
- ggf. integration mit Fixture-Daten

### 7.5 API / Web
- unit
- integration
- smoke

### 7.6 Deployment / Scheduler / VPS
- smoke
- ops
- ggf. integration

## 8. Definition of Green

Ein Gate ist grün, wenn:
- der definierte Befehl erfolgreich läuft,
- das Ergebnis dokumentiert oder nachvollziehbar ist,
- keine unbewerteten kritischen Fehler offen sind.

## 9. Zielbild für spätere Automation

Mittel- bis langfristig sollen die wichtigsten Gates per Skript oder CI-artigem
lokalen/Server-seitigen Ablauf reproduzierbar sein.
Auch ohne formale Cloud-CI gilt: Qualität darf nicht von Erinnerung abhängen.
