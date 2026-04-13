# NEW NFL — Chat-Handoff-Protokoll v1.0

**Status:** Adopted
**Last Updated:** 2026-04-13
**Verhältnis zu anderen Dokumenten:**
- `HANDOFF_GUIDE.md` regelt **inhaltliche** Tranche-Handoffs (Arbeitsstand für Wiederaufnahme).
- Dieses Dokument regelt **chat-/session-spezifische** Handoffs (Übergabe an neues KI-Chat-Fenster wegen Kontextlimit oder Themenwechsel).

## 1. Zweck

KI-Chat-Sessions haben begrenzten Kontext. Lange Sessions werden langsam, ungenau und teuer. Ein sauberer Wechsel in eine neue Session darf keinen Wissensverlust erzeugen.

Ein Chat-Handoff stellt sicher, dass:

- alle relevanten Pläne und Dokumente **vor** dem Wechsel aktualisiert sind,
- ein **Starter-Prompt** existiert, der die neue Session in unter zwei Minuten arbeitsfähig macht,
- der ausgehende Stand belastbar dokumentiert ist (offene Fragen, laufende Tranche, nächster Schritt).

## 2. Wann einen Chat-Handoff machen

### 2.1 Pflicht-Trigger
Ein Handoff ist **Pflicht**, wenn einer dieser Punkte zutrifft:

- **Kontext-Druck:** Die KI signalisiert spürbare Verlangsamung, häufige Wiederholungsfragen oder beginnt, frühere Inhalte zu „vergessen".
- **Tranche-Abschluss + größerer Themenwechsel:** Eine Tranche ist done, der nächste Schritt liegt thematisch deutlich woanders (z. B. T2.3 abgeschlossen → Start UI-Implementierung).
- **Major-Milestone:** v1.0-Cut, VPS-Migration, Phase-Übergang.
- **Nach Lessons-Learned:** Wenn eine Lessons-Learned-Analyse Method-Änderungen ergibt, die in der nächsten Session konsequent gelten sollen.
- **Unterbrechung > 24 h:** Vor einer längeren Pause besser sauber übergeben als kalt wieder aufnehmen.

### 2.2 Ich (KI) signalisiere proaktiv
Die KI ist verpflichtet, einen Chat-Handoff **vorzuschlagen**, sobald sie merkt:

- Antworten werden langsamer oder fragmentierter,
- frühere Entscheidungen müssen erneut nachgelesen werden,
- die Session enthält bereits mehrere abgeschlossene größere Tranchen,
- ein logischer Schnittpunkt erreicht ist (Tranche done, Major-Milestone).

Vorschlag-Format der KI:
> „**Empfehlung Chat-Handoff:** Grund = [Trigger]. Vor dem Wechsel zu aktualisieren: [Liste]. Soll ich den Handoff vorbereiten?"

### 2.3 Anti-Trigger (kein Handoff)
- Mitten in einer laufenden Tranche.
- Wenn nur eine kleine Folge-Frage offen ist.
- Wenn ein Handoff im Verhältnis zur verbleibenden Arbeit teurer wäre als die Restarbeit.

## 3. Pflicht-Vorbereitungsschritte (vor dem Wechsel)

In dieser Reihenfolge:

1. **`PROJECT_STATE.md`** aktualisieren (Phase, Completed-Liste, Current-Cycle, Preferred-Next-Bolt).
2. **Aktiver Plan** aktualisieren (z. B. `T2_3_PLAN.md` — Status pro Tranche).
3. **Betroffene Konzepte / ADRs / Style-Guides** aktualisieren, falls neue Entscheidungen getroffen wurden.
4. **Lessons-Learned-Eintrag** anlegen, falls die Session welche produziert hat (siehe `LESSONS_LEARNED_PROTOCOL.md`).
5. **Inhaltliches Tranche-Handoff** unter `docs/_handoff/handoff_YYYYMMDD-HHMM_<kurztitel>.md` schreiben (gemäß `HANDOFF_GUIDE.md`).
6. **Chat-Handoff-Dokument** schreiben (Template Abschnitt 4).
7. **Starter-Prompt** generieren und ausgeben (Template Abschnitt 5).
8. **Git-Commit** aller Doku-Updates mit Message-Präfix `Handoff:`.

Erst danach Chat-Wechsel.

## 4. Template — Chat-Handoff-Dokument

Ablage: `docs/_handoff/chat_handoff_YYYYMMDD-HHMM_<kurztitel>.md`

```markdown
# Chat-Handoff YYYY-MM-DD HH:MM — <Kurztitel>

## Trigger
Welcher Trigger aus §2.1 hat den Handoff ausgelöst.

## Was wurde in dieser Session erreicht
- punktuelle Liste, fachlich verständlich.

## Was ist offen / unklar / Risiko
- Liste mit Verweis auf Datei und Stelle.

## Aktueller Arbeitsstand
- aktuelle Phase / Tranche
- letzter erfolgreicher Pflichtpfad
- nächster konkreter Schritt (genau einer)

## Geänderte / neue Dokumente in dieser Session
- Liste mit Pfaden.

## Lessons-Learned-Eintrag
- Verweis oder „keine".

## Starter-Prompt für die neue Session
Eingebettet als Code-Block (siehe Template §5).
```

## 5. Template — Starter-Prompt für neue Session

Der Starter-Prompt soll:
- Rolle und Projekt setzen,
- den verbindlichen Lese-Stack verlinken,
- den nächsten konkreten Schritt benennen,
- die KI verpflichten, vor jeder größeren Aktion den aktuellen Stand zu lesen.

Vorlage (anzupassen pro Handoff):

```text
Du übernimmst das Projekt **NEW NFL** (privates NFL-Daten-/Analysesystem,
Single-Operator). Repo: c:\projekte\newnfl bzw.
https://github.com/andreaskeis77/new_nfl

**Pflichtlektüre vor jedem größeren Schritt (in dieser Reihenfolge):**
1. docs/PROJECT_STATE.md
2. docs/_handoff/<NEUESTES_CHAT_HANDOFF>.md  ← *hier konkreten Pfad einsetzen*
3. docs/ENGINEERING_MANIFEST_v1_3.md
4. docs/concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md
5. docs/T2_3_PLAN.md  ← *aktuellen Plan einsetzen*
6. docs/UI_STYLE_GUIDE_v0_1.md (für UI-Arbeit)
7. docs/LESSONS_LEARNED.md (Method-Updates)
8. docs/CHAT_HANDOFF_PROTOCOL.md

**Verbindliche Regeln:**
- Manifest gilt vollständig (Prio-Reihenfolge §2, Prinzipien §3).
- Befehle immer mit Ausführungsort kennzeichnen: DEV-LAPTOP / VPS-USER / VPS-ADMIN.
- Vollständige Dateien liefern, keine Patch-Snippets (Manifest §7.5).
- Operator-Aktionen sind in v1.0 CLI-only.
- UI/API liest ausschließlich aus mart.* (ADR-0029).
- Schlage proaktiv einen Chat-Handoff vor, sobald ein Trigger aus
  CHAT_HANDOFF_PROTOCOL §2.1 zutrifft.
- Aktualisiere Pläne und Doku automatisch bei jeder relevanten Entscheidung.

**Aktueller Stand (kurz):**
<3–5 Zeilen, was als nächstes ansteht>

**Konkreter nächster Schritt:**
<genau ein Schritt>

Lies erst die Pflichtlektüre, dann bestätige Verständnis in 5 Bullets,
dann frage nach Freigabe für den nächsten Schritt.
```

## 6. Pflege dieses Protokolls

Änderungen am Protokoll sind ADR-frei, müssen aber im Manifest §7 referenziert bleiben. Versions-Bump (`v1.x`) bei jeder substantiellen Änderung.

## 7. Verweise

- `HANDOFF_GUIDE.md` — inhaltliche Tranche-Handoffs
- `HANDOFF_MANIFEST.md`
- `LESSONS_LEARNED_PROTOCOL.md`
- `ENGINEERING_MANIFEST_v1_3.md` §7
