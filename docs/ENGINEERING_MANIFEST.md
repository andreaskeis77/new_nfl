# NEW NFL – Engineering Manifest v1.1

## 1. Zweck

Dieses Manifest definiert die obersten Engineering-Regeln für NEW NFL.
NEW NFL ist kein Experimentier-Notizbuch, sondern ein langfristig wartbares
privates Daten- und Analysesystem mit hohem Anspruch an Robustheit,
Nachvollziehbarkeit, Redundanz und Wiederanlaufbarkeit.

Dieses Manifest gilt für:
- Architektur
- Implementierung
- Tests
- Datenmodellierung
- Ingestion
- Deployment
- Betrieb
- Handoffs
- Dokumentation

## 2. Prioritätenreihenfolge

Bei Zielkonflikten gilt diese Reihenfolge:

1. Korrektheit und Datenintegrität
2. Reproduzierbarkeit und Nachvollziehbarkeit
3. Robustheit und Betriebsfähigkeit
4. Verständlichkeit und Wartbarkeit
5. Testbarkeit und Observability
6. Geschwindigkeit der Umsetzung
7. Eleganz oder technische Raffinesse

## 3. Grundprinzipien

### 3.1 Small Batches
Es werden kleine, klar abgrenzbare Tranches gebaut.
Jede Tranche muss einen fachlich verständlichen Zweck haben und separat testbar sein.

### 3.2 Vertical Evidence
Eine Änderung gilt erst dann als belastbar, wenn es dafür belastbare Evidenz gibt:
Code, Tests, Logs, Doku und bei Bedarf Screenshots oder Export-Artefakte.

### 3.3 No Blind Trust in AI Output
KI-generierter Code ist grundsätzlich untrusted, bis er geprüft, getestet und dokumentiert wurde.

### 3.4 Docs are Part of the System
Dokumentation ist kein Beiwerk. Wenn Doku veraltet ist, ist das ein Systemmangel.

### 3.5 Fail Loud on Data Integrity
Bei Risiken für Datenintegrität, Schema-Konsistenz, Deduplizierung oder Provenance
wird nicht stillschweigend weitergemacht. Solche Fehler müssen sichtbar werden.

### 3.6 Designed Degradation
Wenn Teilquellen ausfallen, soll das System so weit wie sinnvoll degradiert weiterlaufen.
Degradation muss bewusst entworfen, protokolliert und in Reports oder UI nachvollziehbar sein.

### 3.7 Clear Ownership
Jede Tranche hat klar benannte Ziele, Dateien, Tests, Gates und einen definierten nächsten Schritt.

## 4. Regeln für Architektur und Implementierung

### 4.1 Keine vorschnelle Breite
Neue Quellen, Tabellen, Jobs oder UI-Module werden erst eingeführt, wenn Zielzweck,
Verantwortlichkeiten und Teststrategie klar sind.

### 4.2 Kanonische Layer
Das System wird schichtweise gedacht. Rohdaten, source-nahe Normalisierung,
konsolidierter Faktenkern, UI-Read-Modelle und Simulations-/Prediction-Daten
dürfen nicht unkontrolliert vermischt werden.

### 4.3 Provenance Pflicht
Jeder relevante persistierte Datensatz braucht eine nachvollziehbare Herkunft.
Wo sinnvoll, sind Quelle, Abrufzeitpunkt, Run-ID, Hash oder Konfliktstatus zu speichern.

### 4.4 Idempotenz vor Bequemlichkeit
Ingestion und Konsolidierung sollen so gebaut werden, dass Wiederholungsläufe
keinen unkontrollierten Datenmüll produzieren.

### 4.5 Explizite Entscheidungen
Wichtige Architekturentscheidungen werden per ADR dokumentiert.
Stillschweigende Richtungswechsel sind unzulässig.

## 5. Regeln für Tests und Qualität

### 5.1 Kein ungetesteter Kern
Änderungen an Kernlogik, Datenmodellen, Ingestion, Konsolidierung, APIs,
Scheduler-Jobs oder Deployment-Skripten benötigen Tests oder eine belastbare Begründung.

### 5.2 Green Gate vor Fortschritt
Ein Schritt gilt erst als abgeschlossen, wenn die zugehörigen Gates grün sind.
Auf roten Gates wird nicht einfach weitergebaut.

### 5.3 Reproduzierbare Befehle
Tests und Qualitätsprüfungen müssen mit dokumentierten, wiederholbaren Befehlen ausführbar sein.

### 5.4 Defekte ehrlich behandeln
Unklare Zustände, Workarounds, intermittierende Fehler und nicht verstandene Effekte
werden als Risiko markiert und nicht schönformuliert.

### 5.5 Repo-Hygiene ist Teil der Qualität
Zeilenenden, Ignore-Regeln, Dateistruktur und generierte Artefakte werden bewusst geführt.
Drift in diesen Bereichen gilt nicht als Kosmetik, sondern als Wartbarkeitsrisiko.

## 6. Regeln für Betrieb und Deployment

### 6.1 Betriebsrealität ist dokumentiert
Dienste, Scheduler, Ports, Secrets-Handling, Logs, Recovery-Schritte und Gesundheitsprüfungen
müssen dokumentiert sein.

### 6.2 Observability ist Pflicht
Ein produktionsnahes System ohne verwertbare Logs, Health-Checks und Run-Evidence gilt als unfertig.

### 6.3 Security und Secrets
Keine Secrets im Repo. Keine stillschweigende Vermischung von Test- und Produktivwerten.

## 7. Regeln für Zusammenarbeit Andreas ↔ ChatGPT

### 7.1 In der Konzeptphase
Alternativen sind erlaubt, aber nur mit klarer Empfehlung.

### 7.2 In der Umsetzungsphase
Keine unverbindlichen Mehrfachoptionen für operative Schritte.
Es werden eindeutige Befehle und klare Reihenfolgen geliefert.

### 7.3 Ausführungsort immer benennen
Jeder Befehl ist mit einem dieser Orte zu kennzeichnen:
- DEV-LAPTOP
- VPS-USER
- VPS-ADMIN

### 7.4 Dateilieferung in Paketen
Code und Dokumente werden als vollständige Dateipakete geliefert,
bevorzugt als ZIP mit passender Ordnerstruktur.

### 7.5 Kein Fortschritt ohne Ist-Bild
Debugging und nächste Schritte basieren auf realen Outputs, nicht auf Annahmen.

## 8. Ausnahmen

Ausnahmen von diesem Manifest sind nur zulässig, wenn:
- die Abweichung explizit benannt wird,
- der Grund dokumentiert ist,
- das Risiko beschrieben wird,
- und die Entscheidung als ADR oder in einem Handoff festgehalten wird.

## 9. Definition of Done für Tranches

Eine Tranche ist erst dann done, wenn mindestens Folgendes erfüllt ist:

- Ziel und Scope sind klar
- Dateien sind konsistent
- relevante Tests/Gates sind ausgeführt oder die Abweichung ist dokumentiert
- Ergebnis ist fachlich verständlich
- Doku ist aktualisiert
- Handoff ist aktualisiert
- nächster Schritt ist eindeutig benannt
