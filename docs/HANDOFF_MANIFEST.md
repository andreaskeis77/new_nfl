# NEW NFL – Handoff Manifest v1.0

## 1. Zweck

Handoffs sind Pflichtartefakte.
Sie dienen nicht der schönen Zusammenfassung, sondern der belastbaren Übergabe
eines realen Projektzustands über Chat-, Zeit- oder Kontextgrenzen hinweg.

## 2. Wann ein Handoff Pflicht ist

Ein Handoff ist zu aktualisieren oder neu zu erzeugen, wenn mindestens eines davon zutrifft:

- Abschluss einer Tranche
- Unterbrechung eines mehrstufigen Vorhabens
- Übergang von Konzept zu Implementierung
- signifikanter Debugging-Fortschritt
- Änderung an Architektur, Schema, Betriebsmodus oder Deployment
- Release-Kandidat
- unsauberer Zwischenzustand, der später wieder aufgenommen werden muss

## 3. Mindestinhalt eines Handoffs

Jedes Handoff muss diese Abschnitte enthalten:

### 3.1 Zielkontext
- Worum geht es?
- Warum ist das wichtig?
- In welcher Phase befindet sich das Projekt?

### 3.2 Validierter Ist-Zustand
- Was ist wirklich vorhanden?
- Welche Dateien / Module / Dokumente wurden geändert?
- Welche Tests oder Checks sind grün?
- Welche Zustände sind nur angenommen und nicht bestätigt?

### 3.3 Offene Punkte
- Was ist noch nicht gelöst?
- Welche Risiken sind bekannt?
- Welche Fragen sind absichtlich offen?

### 3.4 Nächster Schritt
Genau ein bevorzugter nächster Schritt, mit Zweck und erwarteter Wirkung.

### 3.5 Operative Hinweise
- Ausführungsort
- relevante Befehle
- bekannte Stolperstellen
- benötigte Artefakte / Logs / Dateien

## 4. Qualitätsregeln für Handoffs

Ein gutes Handoff ist:
- präzise,
- vollständig genug für Wiederaufnahme,
- frei von Wunschdenken,
- klar getrennt in Fakt / Annahme / Risiko,
- direkt nutzbar ohne Rückgriff auf lange Chat-Historien.

## 5. Verbotene Handoff-Muster

Unzulässig sind Handoffs, die:
- nur eine Erzählung ohne validierten Status liefern,
- keine Tests nennen,
- unklare "vielleicht"-Befunde als Fakten darstellen,
- keinen eindeutigen nächsten Schritt enthalten,
- wesentliche Pfade oder Dateien verschweigen.

## 6. Empfohlene Ablage

Handoffs werden versionsnah und systematisch abgelegt.
Empfohlen:
- `docs/_handoff/`
- eindeutige Dateinamen mit Datum/Zeit oder Tranche
- Verweis auf den aktuell gültigen Stand in `PROJECT_STATE.md`

## 7. Handoff-Template

```md
# Handoff – <Titel>

## Zielkontext
...

## Validierter Ist-Zustand
- ...
- ...

## Ausgeführte Checks
- ...
- ...

## Offene Punkte / Risiken
- ...
- ...

## Bevorzugter nächster Schritt
...

## Operative Hinweise
- Ort:
- Befehle:
- Erwartetes Ergebnis:
```
