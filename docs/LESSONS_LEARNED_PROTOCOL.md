# NEW NFL — Lessons-Learned-Protokoll v1.0

**Status:** Adopted
**Last Updated:** 2026-04-13

## 1. Zweck

NEW NFL betreibt eine **interne Verbesserungs- und Qualitätsschleife**. Nach jedem größeren Schritt prüfen wir, ob unsere Vorgehensweise verbessert werden kann oder muss. Erkenntnisse fließen in Manifest, Protokolle und Templates zurück. Ziel: kontinuierlich kürzere Wege, weniger Wiederholungsfehler, besseres Engineering.

Dieses Dokument definiert **wann**, **wie** und **wohin** Lessons Learned festgehalten werden.

## 2. Wann eine Lessons-Learned-Analyse Pflicht ist

- **Nach jeder Tranche** (Definition gemäß Manifest §9 erfüllt).
- **Nach jedem RC-Cut** und jedem Release (z. B. v1.0).
- **Nach jedem nicht-trivialen Bug oder Quarantäne-Fall**, der über reines Re-Run hinausging.
- **Nach jeder VPS- oder Deployment-Aktion** mit operativer Wirkung.
- **Nach jedem Chat-Handoff** (kurz, eingebettet in das Handoff-Dokument).
- **Optional, aber empfohlen:** wenn die KI oder der Operator merkt, dass etwas „komisch lief" — Bauchgefühl ist ein gültiger Trigger.

## 3. Format einer Lessons-Learned-Eintrag

Pro Eintrag genau **fünf Felder**, kurz und ehrlich:

1. **Was lief gut** — was wollen wir bewahren?
2. **Was lief nicht gut** — was hat Zeit, Klarheit oder Qualität gekostet?
3. **Root Cause** — *warum* lief es nicht gut? (nicht das Symptom, die Ursache).
4. **Konkrete Methodänderung** — was ändern wir an Prozess, Manifest, Template, Tooling? Mit Ziel-Datei.
5. **Verifikation** — woran erkennen wir in der nächsten Tranche, dass die Änderung wirkt?

**Anti-Pattern:** „lief alles gut, weiter so." Wenn das wirklich stimmt, schreibe es so — aber prüfe ehrlich, ob nichts vermeidbar Reibung erzeugt hat.

## 4. Ablage

- **Sammeldatei:** `docs/LESSONS_LEARNED.md` — chronologische Liste aller Einträge, neueste oben.
- **Verweise:** Tranche-Handoffs verlinken den zugehörigen Eintrag.
- **Method-Änderungen, die aus Lessons folgen, landen sofort** in:
  - `ENGINEERING_MANIFEST_v1_x.md` (Versions-Bump bei substantieller Änderung)
  - `HANDOFF_GUIDE.md`, `CHAT_HANDOFF_PROTOCOL.md`, `DELIVERY_PROTOCOL.md`, `VALIDATION_PROTOCOL.md`
  - oder einem neuen ADR, wenn die Änderung architektonischer Natur ist.

## 5. Wer schreibt die Lessons Learned

- **Erstentwurf:** die KI, am Ende einer Tranche oder Session, automatisch.
- **Review und Freigabe:** der Operator (Andreas).
- Ohne Operator-Freigabe ist ein Eintrag im Status `draft`, mit Freigabe `accepted`.

## 6. Aggregation und Trend-Review

- **Quartalsweise** (oder nach jedem Major-Milestone): die KI fasst alle `accepted`-Einträge zusammen, erkennt Wiederholungen und schlägt eine **Method-Bump-Tranche** vor (z. B. Manifest v1.4).
- Diese Aggregation landet als eigener Eintrag in `LESSONS_LEARNED.md` mit Präfix `[AGG]`.

## 7. Beispiel-Eintrag (illustrativ)

```markdown
## 2026-04-13 — T2.2A VPS-Runbook
**Status:** accepted

1. **Was lief gut:** Pflichtlektüre-Liste im Starter-Prompt hat den Wiedereinstieg in
   unter zwei Minuten ermöglicht.
2. **Was lief nicht gut:** PROJECT_STATE.md war einen Schritt hinter dem realen
   Stand, sodass der Plan zwei Tranches doppelt nannte.
3. **Root Cause:** PROJECT_STATE.md wird nicht automatisch nach jeder Tranche
   aktualisiert, sondern nur „wenn dran gedacht".
4. **Konkrete Methodänderung:** CHAT_HANDOFF_PROTOCOL §3 macht
   PROJECT_STATE-Update zum Pflicht-Schritt 1 vor jedem Handoff. Zusätzlich
   prüft die KI bei jedem Tranche-Abschluss aktiv, ob PROJECT_STATE noch
   stimmt.
5. **Verifikation:** im nächsten Handoff sind PROJECT_STATE und Plan deckungsgleich.
```

## 8. Pflege dieses Protokolls

Jeder substantielle Method-Bump (Manifest v1.x → v1.x+1) referenziert die Lessons, aus denen er folgt. So wird die Verbesserungsschleife sichtbar und auditierbar.

## 9. Verweise

- `ENGINEERING_MANIFEST_v1_3.md` §3.4 (Docs are part of the system)
- `CHAT_HANDOFF_PROTOCOL.md` §3
- `HANDOFF_GUIDE.md`
- `RETROSPECTIVE_T1_X.md` (historisches Vorbild)
