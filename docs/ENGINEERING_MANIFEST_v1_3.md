# NEW NFL – Engineering Manifest v1.3

**Status:** Draft for adoption — supersedes v1.2
**Last Updated:** 2026-04-13
**Vorgänger:** `ENGINEERING_MANIFEST.md` (v1.2)

## 0. Was sich gegenüber v1.2 ändert

v1.3 ist additiv. Alle Regeln aus v1.2 bleiben in Kraft. Neu sind:

- Abschnitt 3.8 — *Redundanz vor Sparsamkeit beim Sammeln*
- Abschnitt 3.9 — *Replay-Fähigkeit ist Pflicht*
- Abschnitt 3.10 — *UI-Qualität ist Systemqualität*
- Abschnitt 3.11 — *Read-Modell-Disziplin*
- Abschnitt 3.12 — *Quarantäne ist ein Lebenszustand, kein Fehler*
- Abschnitt 3.13 — *Autonomie mit Sichtbarkeit*

Außerdem geschärft:

- Abschnitt 4.8 — *Erweiterbarkeit ohne Kernbruch*
- Abschnitt 6.4 — *Operator-Aktionen sind CLI-first*

## 1. Zweck

Dieses Manifest definiert die obersten Engineering-Regeln für NEW NFL. Es gilt für Architektur, Implementierung, Tests, Datenmodellierung, Ingestion, Deployment, Betrieb, Handoffs und Dokumentation.

## 2. Prioritätenreihenfolge

Bei Zielkonflikten gilt diese Reihenfolge (unverändert):

1. Korrektheit und Datenintegrität
2. Reproduzierbarkeit und Nachvollziehbarkeit
3. Robustheit und Betriebsfähigkeit
4. Verständlichkeit und Wartbarkeit
5. Testbarkeit und Observability
6. Geschwindigkeit der Umsetzung
7. Eleganz oder technische Raffinesse

## 3. Grundprinzipien

### 3.1 Small Batches
Kleine, klar abgrenzbare Tranches. Jede Tranche hat fachlichen Zweck und ist separat testbar.

### 3.2 Vertical Evidence
Eine Änderung ist erst belastbar, wenn Code, Tests, Logs, Doku und ggf. Artefakte sie stützen.

### 3.3 No Blind Trust in AI Output
KI-generierter Code ist untrusted, bis geprüft, getestet und dokumentiert.

### 3.4 Docs are Part of the System
Veraltete Doku ist Systemmangel.

### 3.5 Fail Loud on Data Integrity
Bei Risiken für Datenintegrität, Schema-Konsistenz, Deduplizierung oder Provenance wird laut gescheitert.

### 3.6 Designed Degradation
Bei Quellenausfall läuft das System bewusst degradiert weiter, dokumentiert und in der UI sichtbar.

### 3.7 Clear Ownership
Jede Tranche hat Ziele, Dateien, Tests, Gates und einen definierten nächsten Schritt.

### 3.8 Redundanz vor Sparsamkeit beim Sammeln *(neu)*
Es wird bewusst aus mehreren Quellen redundant gesammelt. Konsolidierung erfolgt erst im kanonischen Kern (1 Fakt = 1 Eintrag, mit Provenance-Mehrfachverweis). Diese Redundanz ist Feature, nicht Verschwendung. Lieber dreimal das gleiche Datum aus verschiedenen Quellen als eines vergessen.

### 3.9 Replay-Fähigkeit ist Pflicht *(neu)*
Kein Pipeline-Schritt darf Raw-Artefakte konsumieren, ohne Replay zu erhalten. Raw-Artefakte sind immutable. Jeder Run ist aus dem unveränderten Raw-Artefakt reproduzierbar. Replay erzeugt einen neuen Run mit Verweis auf die Ursprungs-Artefakte und die genutzten Code-/Ontologie-Versionen.

### 3.10 UI-Qualität ist Systemqualität *(neu)*
Eine schlechte UI ist kein kosmetischer Mangel, sondern ein Systemmangel. Sie verhindert Operator-Verständnis und damit Datenintegrität. UI-Arbeit folgt dem `UI_STYLE_GUIDE` mit gleicher Verbindlichkeit wie Schema-Migrationen.

### 3.11 Read-Modell-Disziplin *(neu)*
UI und API lesen niemals direkt aus `raw/`, `stg.*` oder `core.*`. Einziger Lese-Pfad ist `mart.*` (und `meta.*` für Operator-Sichten auf Runs/Quarantäne). Verstöße sind Architekturfehler.

### 3.12 Quarantäne ist ein Lebenszustand, kein Fehler *(neu)*
Quarantäne-Fälle werden nicht versteckt. Sie sind sichtbar, zählbar und bearbeitbar. Stilles Verwerfen unklarer Datensätze ist verboten. Jede Quarantäne hat `reason_code`, `severity`, `evidence_refs`, `status`, `owner`. Recovery erzeugt einen neuen Run mit Verweis auf den Quarantäne-Fall.

### 3.13 Autonomie mit Sichtbarkeit *(neu)*
Autonome Sammlung ist Ziel — aber jeder autonome Lauf muss im Freshness-Dashboard und in Run-Evidence nachvollziehbar sein. Kein „dunkler" Background-Job ohne Spur.

## 4. Regeln für Architektur und Implementierung

### 4.1 Keine vorschnelle Breite
Neue Quellen, Tabellen, Jobs oder UI-Module werden erst eingeführt, wenn Zielzweck, Verantwortlichkeiten und Teststrategie klar sind.

### 4.2 Kanonische Layer
Schichtweise denken: Raw → Staging → Canonical Core → Read-Modelle → Forecast. Vermischung verboten.

### 4.3 Provenance Pflicht
Jeder relevante persistierte Datensatz braucht nachvollziehbare Herkunft (Quelle, Abrufzeit, Run-ID, Hash, Konfliktstatus).

### 4.4 Idempotenz vor Bequemlichkeit
Ingestion und Konsolidierung müssen wiederholbar sein, ohne Datenmüll zu erzeugen.

### 4.5 Explizite Entscheidungen
Wichtige Architekturentscheidungen per ADR. Stillschweigende Richtungswechsel sind unzulässig.

### 4.6 Vertragsflächen sind echte Systemgrenzen
Stabil, bis bewusst geändert: Paket-`__init__`-Exporte, zentrale Datamodelle, CLI-Kommandos und Kernargumente, Mindestspalten zentraler `meta.*`-Tabellen, Registry-/Adapter-Rückgaben.

### 4.7 Upgrade-Zustände sind First-Class-Fälle
Bestehende lokale Datenbanken und ältere Metadatenflächen sind explizite Zielzustände.

### 4.8 Erweiterbarkeit ohne Kernbruch *(geschärft)*
Neue Datendomänen und Stat-Familien müssen ohne Schema-Bruch im kanonischen Kern aufnehmbar sein:
- neue Adapter ohne Touch am bestehenden Core,
- neue Stat-Familien als zusätzliche `core.*`-Tabellen, nicht als breite Spaltenerweiterung,
- `mart.*`-Read-Modelle versioniert.

## 5. Regeln für Tests und Qualität

(unverändert gegenüber v1.2 — Abschnitte 5.1 bis 5.6)

### 5.1 Kein ungetesteter Kern
### 5.2 Green Gate vor Fortschritt
### 5.3 Reproduzierbare Befehle
### 5.4 Defekte ehrlich behandeln
### 5.5 Kein „teilgrün" bei roten operativen Pfaden
### 5.6 Replay vor Neuheit

## 6. Regeln für Betrieb und Deployment

### 6.1 Betriebsrealität ist dokumentiert
Dienste, Scheduler, Ports, Secrets-Handling, Logs, Recovery-Schritte, Health-Checks dokumentiert.

### 6.2 Observability ist Pflicht
Ein produktionsnahes System ohne verwertbare Logs, Health-Checks und Run-Evidence ist unfertig.

### 6.3 Security und Secrets
Keine Secrets im Repo. Keine Vermischung von Test- und Produktivwerten.

### 6.4 Operator-Aktionen sind CLI-first *(geschärft)*
Refresh, Replay, Backfill, Quarantäne-Override sind in v1.0 ausschließlich über die CLI verfügbar. UI-Buttons folgen in v1.1. Diese Reihenfolge ist verbindlich, weil Operator-Aktionen mit hoher Wirkung erst auditiert und protokolliert sein müssen, bevor sie über ein Web-Frontend exponiert werden.

### 6.5 Deployment-Phasen *(neu)*
Bis v1.0 läuft alles auf DEV-LAPTOP. Migration auf Windows-VPS erfolgt erst nach v1.0. OS-Neutralität der Anwendungslogik bleibt erhalten.

## 7. Regeln für Zusammenarbeit Andreas ↔ ChatGPT / KI-Assistenz

### 7.1 In der Konzeptphase
Alternativen erlaubt, aber mit klarer Empfehlung.

### 7.2 In der Umsetzungsphase
Keine unverbindlichen Mehrfachoptionen. Eindeutige Befehle und klare Reihenfolgen.

### 7.3 Ausführungsort immer benennen
Jeder Befehl mit `DEV-LAPTOP`, `VPS-USER` oder `VPS-ADMIN`.

### 7.4 Dateilieferung in Paketen
Code und Dokumente als vollständige Dateipakete (ZIP mit passender Struktur).

### 7.5 Vollständige Dateien statt Patch-Anweisungen
Standard ist die vollständige Datei. Such-/Ersetz-Anweisungen, Snippets, Patch-Fragmente sind nicht der Standard. Ausnahmen explizit benennen.

### 7.6 Kein Fortschritt ohne Ist-Bild
Debugging und nächste Schritte basieren auf realen Outputs.

### 7.7 Vorab-Validierung ist Pflichtdisziplin
Vor Auslieferung mindestens prüfen: Import/Collection, letzten grünen Pflichtpfad, neuen Pflichtpfad, Fresh State, Upgrade State, Lint und Pytest. Lücken explizit als Risiko benennen.

## 8. Ausnahmen

Ausnahmen sind nur zulässig, wenn explizit benannt, begründet, mit Risiko beschrieben und als ADR oder Handoff festgehalten.

## 9. Definition of Done für Tranches

Eine Tranche ist done, wenn:

- Ziel und Scope klar
- Dateien konsistent
- Tests/Gates ausgeführt
- Ergebnis fachlich verständlich
- Doku aktualisiert
- Handoff aktualisiert
- nächster Schritt eindeutig benannt
- kein verpflichtender operativer Pfad rot

## 10. Verweise

- `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md`
- `USE_CASE_VALIDATION_v0_1.md`
- `UI_STYLE_GUIDE_v0_1.md`
- `T2_3_PLAN.md`
- vorheriger Stand: `ENGINEERING_MANIFEST.md` (v1.2)
