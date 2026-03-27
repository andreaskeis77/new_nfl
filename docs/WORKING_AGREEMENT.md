# NEW NFL – Working Agreement v1.1

## 1. Zweck

Dieses Dokument regelt die konkrete Zusammenarbeit zwischen Andreas und ChatGPT
bei Planung, Implementierung, Test, Debugging, Deployment und Betrieb von NEW NFL.

## 2. Gemeinsames Arbeitsmodell

- Andreas führt Befehle lokal oder auf dem VPS aus.
- ChatGPT entwirft Methode, Architektur, Dateien, Tests, Prüfschritte und Auswertungen.
- Andreas liefert echte Terminal-Ausgaben und Beobachtungen zurück.
- ChatGPT analysiert diese Outputs und gibt den nächsten eindeutigen Schritt vor.
- Der operative Standard ist **ein empfohlener Weg**, nicht ein Menü aus Varianten.

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

## 6. Regeln für Test und Debugging

- Es wird immer zuerst der Ist-Zustand erhoben.
- Fehler werden auf Basis realer Outputs analysiert.
- Hypothesen sind als Hypothesen zu markieren.
- Ein Fix ist erst dann akzeptiert, wenn der relevante Test oder Check grün ist.
- Bei unklaren Systemzuständen wird die Lage zuerst stabilisiert, bevor neue Änderungen erfolgen.
- Rote Gates stoppen den betroffenen Arbeitsstrang, bis Risiko oder Fix klar sind.

## 7. Git- und Repo-Regeln

- `main` ist der kanonische Stand.
- Kein Commit, der bewusst Secrets oder lokale Laufzeitartefakte eincheckt.
- Kein Release ohne Abgleich von Doku, `PROJECT_STATE` und Handoff.
- Commit-Messages sollen den Zweck der Tranche klar erkennen lassen.
- Repo-Hygiene-Dateien (`.gitignore`, `.gitattributes`, optional `.editorconfig`) sind verbindlich zu respektieren.

## 8. Umgang mit Unsicherheit

ChatGPT soll:
- Unsicherheit offen benennen,
- keine Betriebszustände erfinden,
- keine ungetesteten Annahmen als Fakten ausgeben,
- fehlende Informationen gezielt in Arbeitsbefehle übersetzen.

Andreas soll:
- echte Outputs und Beobachtungen zurückspielen,
- Unklarheiten im Systemzustand nicht glätten,
- bei abweichender Realität den tatsächlichen Zustand mitteilen.

## 9. Handoff- und Release-Disziplin

- Jede relevante Tranche aktualisiert das Handoff oder bestätigt bewusst, warum kein neues Handoff nötig ist.
- Jeder wiederaufnahmebedürftige Zustand bekommt ein Handoff.
- Ein Release ohne nachvollziehbare Evidence gilt nicht als belastbarer Stand.

## 10. Zielbild der Zusammenarbeit

Das Projekt soll auch über lange Zeiträume, Chat-Wechsel und Unterbrechungen hinweg
wiederaufnahmefähig bleiben. Das Working Agreement dient genau diesem Ziel:
weniger Rätselraten, weniger Drift, mehr reproduzierbare Fortschritte.
