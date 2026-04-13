# NEW NFL — Lessons Learned (Sammeldatei)

**Format und Regeln:** siehe `LESSONS_LEARNED_PROTOCOL.md`.
**Reihenfolge:** neueste oben.

---

## 2026-04-13 — T2.3A Job-/Run-Modell-Skeleton
**Status:** accepted (Operator-Freigabe 2026-04-13)

1. **Was lief gut:**
   - Wiederverwendung der bestehenden `TABLE_SPECS`/`ensure_metadata_surface`-Infrastruktur hat 7 neue `meta.*`-Tabellen ohne separates Migrations-Framework erlaubt. Idempotent, Test-grün im ersten Lauf.
   - Klarer Schnitt: Schema + Pydantic-Modelle + Service-Funktionen + CLI als eine Tranche. Keine halbe Abstraktion zurückgelassen.
   - Test-First-Gefühl durch deterministische `tmp_path`-Bootstraps — 12 neue Tests, volle Suite grün (73/73) in ~78s.

2. **Was lief nicht gut:**
   - `src/new_nfl/jobs/model.py` hat eine kleine Helfer-Duplikation (`_connect`, `_row_to_dict`, `_new_id`) gegenüber `metadata.py`. Bewusst in Kauf genommen, um zirkuläre Imports zu vermeiden, aber riecht nach Refactor-Bedarf spätestens bei T2.3B.
   - Kein expliziter Rollback-Test (Tabellen löschen + neu aufbauen mit Bestandsdaten). Für T2.3A akzeptabel, weil Neu-Tabellen; ab T2.3B nachziehen.

3. **Root Cause:**
   - `metadata.py` exportiert die privaten Helper nicht, und bei Erstanlage eines neuen Sub-Pakets war der Weg des geringsten Widerstands, sie zu duplizieren.
   - Die Test-Strategie in `TEST_STRATEGY.md` nennt Replay-Tests, aber keinen expliziten Schema-Rollback-Test für neue Migrations-Schritte.

4. **Konkrete Methodänderung:**
   - In T2.3B: gemeinsames Basis-Modul `src/new_nfl/_db.py` (oder `metadata._internal`) für `_connect`/`_row_to_dict`/`_new_id`, bevor Runner, Quarantine und Ontology weitere Duplikate erzeugen. Als To-do im ADR-0025-Folge-Eintrag festhalten.
   - `TEST_STRATEGY.md` um Punkt „Schema-Evolution: neues `TABLE_SPECS`-Feld muss mit Alt-DB und leerer DB getestet werden" ergänzen, ab T2.3B verbindlich.

5. **Verifikation:**
   - In T2.3B existiert ein geteiltes DB-Helper-Modul und `jobs/model.py` importiert es (kein eigenes `_connect` mehr).
   - `TEST_STRATEGY.md` enthält die Schema-Evolution-Regel; der Runner-Test nutzt sie.

---

## 2026-04-13 — Use-Case-Validierung + Architektur-Baseline (v0.3 / v1.3)
**Status:** accepted (Operator-Freigabe 2026-04-13)

1. **Was lief gut:**
   - Strukturiertes Use-Case-Dokument mit OK/Nein/Kommentar-Slots hat in einem Durchgang vollständige Abnahme aller fachlichen Punkte ermöglicht.
   - Bündel-Lieferung (5 Dokumente in einem Durchgang) hat Architektur-, Manifest-, UI-, Plan- und ADR-Ebene konsistent verzahnt.
   - Frühzeitiges Aufdecken des Widerspruchs UC-14/UC-15 (UI-Aktionen) ↔ Frage 6 (CLI-only) hat eine spätere Doppelarbeit verhindert.

2. **Was lief nicht gut:**
   - Erster Zeitplan-Vorschlag (v1.0 bis Ende April) war ohne Rückfrage übernommen und hätte zu unrealistischer Tranche-Dichte geführt. Korrektur erst auf Operator-Hinweis.
   - Kein expliziter Chat-Handoff-Plan vor Freigabe der 5 Dokumente — Operator musste das Thema selbst einbringen.

3. **Root Cause:**
   - Termin wurde aus User-Antwort übernommen, ohne gegen real vorhandene Tranche-Last geprüft zu werden.
   - Es gab bisher kein Protokoll, das die KI verpflichtet, proaktiv Chat-Handoffs vorzuschlagen.

4. **Konkrete Methodänderung:**
   - `CHAT_HANDOFF_PROTOCOL.md` §2.2: KI ist verpflichtet, Chat-Handoff aktiv vorzuschlagen, sobald Trigger zutreffen.
   - Vor Übernahme von Terminen prüft die KI implizit: passt das in den existierenden Plan? Wenn nicht, Hinweis vor Übernahme.
   - In Manifest v1.4 (späterer Bump) Aufnahme als eigenes Prinzip „Termine werden gegen reale Tranche-Last validiert".

5. **Verifikation:**
   - Nächste Termin-Übernahme erfolgt mit explizitem Sanity-Check.
   - Die KI bietet im nächsten logischen Schnittpunkt (z. B. nach T2.3) den Chat-Handoff aktiv an.

---
