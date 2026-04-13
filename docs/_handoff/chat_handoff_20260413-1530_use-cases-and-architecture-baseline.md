# Chat-Handoff 2026-04-13 15:30 — Use-Cases und Architektur-Baseline freigegeben

## Trigger
Logischer Schnittpunkt: Major Architektur-/Methoden-Baseline ist abgenommen. Vor Beginn der Implementierungsarbeit (T2.3A) und vor dem nächsten thematischen Wechsel (von Konzeption zu Code) ist ein Chat-Handoff sinnvoll, um die neue Session auf einer sauberen, dokumentierten Basis zu starten.

## Was wurde in dieser Session erreicht

- Use-Case-Validierung (`USE_CASE_VALIDATION_v0_1.md`) erstellt und vom Operator vollständig durchgegangen — alle 20 UC + 13 Strukturpunkte + 10 offene Fragen abgenommen.
- Zeitplan geklärt: v1.0 feature-complete bis Ende Juni 2026, Testphase Juli, produktiv vor Preseason-Start August.
- v1.0-Operator-Surface auf CLI-only festgelegt; UI-Buttons in v1.1.
- 5 Architektur-Dokumente geliefert und freigegeben:
  - `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md`
  - `ENGINEERING_MANIFEST_v1_3.md`
  - `UI_STYLE_GUIDE_v0_1.md`
  - `T2_3_PLAN.md`
  - 6 ADRs: ADR-0025 bis ADR-0030
- Verbesserungs- und Handoff-Infrastruktur etabliert:
  - `CHAT_HANDOFF_PROTOCOL.md`
  - `LESSONS_LEARNED_PROTOCOL.md`
  - `LESSONS_LEARNED.md` (erster Eintrag)

## Was ist offen / unklar / Risiko

- `PROJECT_STATE.md` ist noch auf T2.2A-Stand und muss vor Sessionende auf „T2.3 Foundation Hardening – ready to start" gehoben werden (siehe Vorbereitungs-Schritte).
- `ENGINEERING_MANIFEST.md` (v1.2) und `ENGINEERING_MANIFEST_v1_3.md` koexistieren bewusst — ab nächster Session ist v1.3 verbindlich; v1.2 sollte als historisch markiert werden.
- Lessons-Learned-Eintrag von heute ist `draft` und braucht Operator-Freigabe.
- T2.3A startet mit Job-/Run-Modell-Schema; das ist ein Migrations-Schritt auf der bestehenden DuckDB-Metadatenfläche — vorab Backup empfohlen.

## Aktueller Arbeitsstand

- **Phase:** Übergang T2.2 → T2.3.
- **Letzter erfolgreicher Pflichtpfad:** lokale Mini-Web-Preview für Core-Dictionary (T2.1D), `cli stage-load --adapter-id nflverse_bulk --execute` grün.
- **Nächster konkreter Schritt:** **T2.3A — Job-/Run-Modell-Skeleton** gemäß `T2_3_PLAN.md` §2 und ADR-0025.

## Geänderte / neue Dokumente in dieser Session

- `docs/USE_CASE_VALIDATION_v0_1.md` (neu, vollständig abgenommen)
- `docs/concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md` (neu)
- `docs/ENGINEERING_MANIFEST_v1_3.md` (neu)
- `docs/UI_STYLE_GUIDE_v0_1.md` (neu)
- `docs/T2_3_PLAN.md` (neu)
- `docs/adr/ADR-0025-internal-job-and-run-model.md` (neu)
- `docs/adr/ADR-0026-ontology-as-code-with-runtime-projection.md` (neu)
- `docs/adr/ADR-0027-dedupe-pipeline-as-explicit-stage.md` (neu)
- `docs/adr/ADR-0028-quarantine-as-first-class-domain.md` (neu)
- `docs/adr/ADR-0029-read-model-separation.md` (neu)
- `docs/adr/ADR-0030-ui-tech-stack.md` (neu)
- `docs/adr/README.md` (Index aktualisiert)
- `docs/INDEX.md` (Verweise ergänzt)
- `docs/CHAT_HANDOFF_PROTOCOL.md` (neu)
- `docs/LESSONS_LEARNED_PROTOCOL.md` (neu)
- `docs/LESSONS_LEARNED.md` (neu, erster Eintrag draft)

## Lessons-Learned-Eintrag

Siehe `docs/LESSONS_LEARNED.md` Eintrag „2026-04-13 — Use-Case-Validierung + Architektur-Baseline".

## Vor dem Wechsel noch zu tun (in dieser Session)

1. `PROJECT_STATE.md` aktualisieren auf T2.3-Start.
2. Operator-Freigabe für Lessons-Learned-Eintrag einholen.
3. Optional: Git-Commit aller neuen Dokumente mit Präfix `Handoff:`.

## Starter-Prompt für die neue Session

```text
Du übernimmst das Projekt **NEW NFL** (privates NFL-Daten-/Analysesystem,
Single-Operator, Python 3.12, DuckDB-Zentrum, Windows-VPS-Ziel ab v1.0).
Repo lokal: c:\projekte\newnfl
Repo remote: https://github.com/andreaskeis77/new_nfl

**Pflichtlektüre vor jedem größeren Schritt — in dieser Reihenfolge:**
1. docs/PROJECT_STATE.md
2. docs/_handoff/chat_handoff_20260413-1530_use-cases-and-architecture-baseline.md
3. docs/ENGINEERING_MANIFEST_v1_3.md
4. docs/concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md
5. docs/T2_3_PLAN.md
6. docs/UI_STYLE_GUIDE_v0_1.md (für UI-Tranches)
7. docs/CHAT_HANDOFF_PROTOCOL.md
8. docs/LESSONS_LEARNED_PROTOCOL.md
9. docs/LESSONS_LEARNED.md
10. docs/USE_CASE_VALIDATION_v0_1.md (abgenommene Use Cases)
11. docs/adr/README.md (Index, ADR-0025 bis ADR-0030 sind die neuesten)

**Verbindliche Regeln:**
- Engineering Manifest v1.3 gilt vollständig (Prio-Reihenfolge §2, Prinzipien §3.1–3.13).
- Befehle immer mit Ausführungsort kennzeichnen: DEV-LAPTOP / VPS-USER / VPS-ADMIN.
  In dieser Phase ist alles DEV-LAPTOP.
- Vollständige Dateien liefern, keine Patch-Snippets (Manifest §7.5).
- Operator-Aktionen sind in v1.0 CLI-only, UI-Buttons erst v1.1.
- UI/API liest ausschließlich aus mart.* (ADR-0029).
- Quarantäne ist First-Class (ADR-0028), Replay aus immutable Raw ist Pflicht.
- Personen-/Teamnamen immer in offizieller Vollform (UI Style Guide §1).
- Schlage proaktiv einen Chat-Handoff vor, sobald ein Trigger aus
  CHAT_HANDOFF_PROTOCOL.md §2.1 zutrifft.
- Aktualisiere PROJECT_STATE und den aktiven Plan (T2_3_PLAN.md) automatisch
  nach jedem Tranche-Abschluss.
- Erstelle nach jeder Tranche einen Lessons-Learned-Eintrag (draft) gemäß
  LESSONS_LEARNED_PROTOCOL.md.

**Aktueller Stand:**
- Phase T2.2 abgeschlossen, Übergang zu T2.3.
- Architektur-Baseline v0.3 / Manifest v1.3 / UI Style Guide v0.1 sind freigegeben.
- 6 neue ADRs (0025–0030) sind „Proposed".
- Zielkorridor: v1.0 feature-complete bis Ende Juni 2026.

**Konkreter nächster Schritt:**
**T2.3A — Job-/Run-Modell-Skeleton** gemäß T2_3_PLAN.md §2 und ADR-0025.
Konkret: DuckDB-Migration für meta.job_definition, meta.job_schedule,
meta.job_queue, meta.job_run, meta.run_event, meta.run_artifact,
meta.retry_policy. Modul src/new_nfl/jobs/model.py mit Pydantic-Modellen.
Tests. CLI-Oberflächen `cli list-jobs` und `cli describe-job`.

Lies erst die Pflichtlektüre, dann bestätige Verständnis in 5 Bullets,
dann frage nach Freigabe für T2.3A.
```

## Verweise

- `docs/CHAT_HANDOFF_PROTOCOL.md`
- `docs/LESSONS_LEARNED_PROTOCOL.md`
- `docs/T2_3_PLAN.md`
- `docs/concepts/NEW_NFL_SYSTEM_CONCEPT_v0_3.md`
- `docs/ENGINEERING_MANIFEST_v1_3.md`
