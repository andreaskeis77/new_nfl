# NEW NFL – Working Agreement v1.1

## 1. Zweck

Dieses Dokument regelt die konkrete Zusammenarbeit zwischen Andreas und ChatGPT
bei Planung, Implementierung, Test, Debugging, Deployment und Betrieb von NEW NFL.

## 2. Gemeinsames Arbeitsmodell

- Andreas führt Befehle lokal oder auf dem VPS aus.
- ChatGPT entwirft Methode, Architektur, Dateien, Tests, Prüfschritte und Auswertungen.
- Andreas liefert echte Terminal-Ausgaben und Beobachtungen zurück.
- ChatGPT analysiert diese Outputs und gibt den nächsten eindeutigen Schritt vor.

## 3. Phasenmodell

### 3.1 Konzept- und Methodikphase
Erlaubt:
- Diskussion von Alternativen
- Vor- und Nachteile
- klare Empfehlung
- saubere Entscheidungsgrundlagen

Nicht erlaubt:
- voreilige Implementierung
- technische Festlegungen ohne begründete Einordnung

### 3.2 Implementierungsphase
Erlaubt:
- eindeutige Lösung
- klare Reihenfolge
- exakte Dateiänderungen
- exakte Testbefehle

Nicht erwünscht:
- mehrere operative Varianten ohne Not
- vage Hinweise statt klarer Instruktionen

## 4. Formatregeln für operative Anweisungen

Jeder operative Schritt muss enthalten:

1. **Ort**
   - DEV-LAPTOP
   - VPS-USER
   - VPS-ADMIN

2. **Ziel**
   - Was wird geprüft, geändert oder gestartet?

3. **Befehle**
   - vollständig kopierbar
   - in sinnvoller Reihenfolge
   - ohne unnötige Alternativen

4. **Erwartetes Ergebnis**
   - welche Ausgabe oder Wirkung wird erwartet?

5. **Was Andreas zurückmeldet**
   - z. B. PowerShell-Output, Fehlertext, Screenshot, Status

## 5. Regeln für Dateilieferungen

Wenn ChatGPT Dateien liefert, dann bevorzugt als vollständige Tranche mit:

- ZIP-Datei oder klarer Ordnerstruktur
- Liste der enthaltenen Dateien
- Zweck der Tranche
- Acceptance Criteria
- Testbefehle
- erwartete Ergebnisse
- Commit-Message-Vorschlag
- Doku-Update-Hinweise

Keine halbfertigen Dateifragmente als Endzustand.

## 6. Vollständige-Dateien-Regel

Für NEW NFL gilt ab jetzt ausdrücklich:

- In der Implementierungsphase liefert ChatGPT standardmäßig vollständige betroffene
  Dateien.
- In der Fix- und Debugging-Phase liefert ChatGPT standardmäßig vollständige
  betroffene Dateien.
- In der Qualitäts-Gate-Reparatur liefert ChatGPT standardmäßig vollständige
  betroffene Dateien.
- Diese Dateien werden als ZIP-Paket geliefert, sofern Andreas nicht ausdrücklich
  etwas anderes verlangt.

Nicht der Standard sind:
- Such-/Ersetz-Anweisungen
- Zeilen- oder Snippet-Patches
- Aufforderungen an Andreas, einzelne Zeilen selbst zusammenzusuchen
- fragmentierte Mini-Änderungen ohne vollständige Datei

Eine Abweichung davon ist nur zulässig, wenn:
1. Andreas ausdrücklich um eine manuelle Änderung bittet, oder
2. ein echter Hotfix eine minimale Sofortmaßnahme erfordert

Auch dann ist die Abweichung explizit zu benennen.

## 7. Regeln für Test und Debugging

- Es wird immer zuerst der Ist-Zustand erhoben.
- Fehler werden auf Basis realer Outputs analysiert.
- Hypothesen sind als Hypothesen zu markieren.
- Ein Fix ist erst dann akzeptiert, wenn der relevante Test oder Check grün ist.
- Bei unklaren Systemzuständen wird die Lage zuerst stabilisiert, bevor neue
  Änderungen erfolgen.

## 8. Umgang mit Unsicherheit

ChatGPT soll:
- Unsicherheit offen benennen,
- keine Betriebszustände erfinden,
- keine ungetesteten Annahmen als Fakten ausgeben,
- fehlende Informationen gezielt in Arbeitsbefehle übersetzen.

Andreas soll:
- Outputs möglichst vollständig zurückgeben,
- Abweichungen von den Befehlen klar markieren,
- reale Randbedingungen offen nennen.

## 9. Dokumentationspflicht

Nach jeder relevanten Tranche ist zu prüfen, ob mindestens eines der folgenden
Dokumente angepasst werden muss:

- PROJECT_STATE.md
- HANDOFF
- RUNBOOK
- TEST_STRATEGY
- RELEASE_PROCESS
- ADR
- Konzeptdokumente
- DELIVERY_PROTOCOL.md

## 10. Eskalationsregel

Wenn eine Änderung unerwartet:
- Datenintegrität gefährdet,
- das Deployment destabilisiert,
- Scheduler/Jobs unklar macht,
- oder das Verständnis des Systemzustands verschlechtert,

dann wird nicht einfach weitergebaut. Stattdessen erfolgt:
1. Stop
2. Lagebild
3. Ursachenanalyse
4. gezielte Korrektur
5. erneute Verifikation

## 11. Definition eines guten nächsten Schritts

Ein guter nächster Schritt ist:
- klein genug für eine kontrollierte Ausführung,
- groß genug für echten Fortschritt,
- klar testbar,
- dokumentierbar,
- und fachlich begründet.

## 12. Anti-Pattern

Nicht Teil der NEW-NFL-Arbeitsweise sind:

- große ungetestete Umbauten
- „wir machen erstmal weiter und sehen später“
- nicht dokumentierte Hotfixes
- Deployment ohne klare Rückfallstrategie
- operatives Rätselraten
- zu frühe Quellenexplosion ohne Konsolidierungsplan
- manuelle Such-/Ersetz-Arbeit für Andreas, obwohl vollständige Dateien geliefert
  werden könnten
