# NEW NFL — Lessons Learned (Sammeldatei)

**Format und Regeln:** siehe `LESSONS_LEARNED_PROTOCOL.md`.
**Reihenfolge:** neueste oben.

---

## 2026-04-14 — T2.3D Read-Modell-Trennung (`mart.*`)
**Status:** accepted (Operator-Freigabe 2026-04-14)

1. **Was lief gut:**
   - Schema + Builder + Runner-Executor + CLI + Lint-Test in einer geschlossenen Tranche. Nach Abschluss zeigt der `qualified_table` aller Read-Wege auf `mart.schedule_field_dictionary_v1`, kein gemischter Zustand.
   - `core-load --execute` ruft den Mart-Builder direkt am Ende des Execute-Pfads — kein zweiter Operator-Schritt nötig, kein Risiko, dass UI gegen veraltetes Mart läuft. Gleichzeitig bleibt `cli mart-rebuild` als unabhängiger Runner-Job verfügbar (für `_v2`-Bumps oder Repair).
   - **AST-basierter Lint-Test** (`test_read_modules_do_not_reference_core_or_stg_directly`) erkennt String-Literale, die `core.` / `stg.` / `raw/` enthalten — Docstrings sind sauber exempt. Damit wird die ADR-0029-Pflicht zu einem objektiven Code-Review-Kriterium statt einer Erinnerung.
   - **Spalten-toleranter Builder**: Quell-Schema von `core.schedule_field_dictionary` darf optionale Provenance-Spalten (`_source_file_id`, `_adapter_id`, `_canonicalized_at`/`_loaded_at`) tragen oder weglassen. Tests-Fixtures, die die alte Form pflegten, brauchten keine Schema-Anpassung.

2. **Was lief nicht gut:**
   - Die Read-Module heißen weiterhin `core_browse.py`/`core_lookup.py`/`core_summary.py`. Inhaltlich sind es jetzt Mart-Reader. Konsistente Umbenennung bewusst aufgeschoben, weil sie ansonsten Diff-Volumen ohne Verhaltensgewinn produziert; bleibt offener Refactor-Punkt für T2.5.
   - `MAX(built_at)`-Roundtrip in DuckDB schlug initial mit `ModuleNotFoundError: pytz` fehl — aufgefallen erst beim Test, nicht beim Local-Smoke. Dropdown auf `datetime.now()` aus Python war die richtige Wahl, aber das Pytz-Problem ist eine Latenzbombe für jede künftige `MAX(timestamp)`-Aggregation.
   - `assert qualified_table == MART_SCHEDULE_FIELD_DICTIONARY_V1` ist in den Read-Modulen verteilt redundant. Bleibt als billige Defense-in-Depth, lässt sich aber bei jedem neuen Mart-Reader vergessen — sollte beim Refactor in T2.5 zentralisiert werden.

3. **Root Cause:**
   - DuckDB-`pytz`-Abhängigkeit für Timestamp-Aggregate ist eine bekannte Eigenheit, die in unserem `requirements.txt` nicht abgedeckt ist. Wir vermeiden sie heute, indem Build-Timestamps Python-seitig erzeugt werden — aber die Falle bleibt für jeden, der naiv `SELECT MAX(timestamp_col)` in DuckDB schreibt.
   - Die Read-Modul-Namensgebung stammt aus T2.0C, wo es noch keine Mart-Schicht gab. Refactor-Aufschub ist eine Scope-Entscheidung.

4. **Konkrete Methodänderung:**
   - Jeder neue Mart-Reader-Modul wird ab T2.5 direkt unter dem `mart_*.py`-Präfix angelegt; bestehende `core_*.py`-Reader werden im Rahmen der ersten T2.5-Domäne mit umbenannt (atomarer Rename + Test-Update).
   - DuckDB-Pytz-Falle in `LESSONS_LEARNED` als Snippet-Warnung dokumentiert; bei künftigen `built_at`/`updated_at`-Aggregaten Python-seitig oder über `epoch_ms`-Casts arbeiten.
   - Lint-Wand erweitern, sobald HTTP-API-Module entstehen (T2.6): die `READ_MODULES`-Liste wird einfach ergänzt.

5. **Verifikation:**
   - `tests/test_mart.py` (9 Tests) + volle Suite grün (112/112).
   - ADR-0029 auf `Accepted` mit Implementierungs-Notizen.
   - `PROJECT_STATE.md` und `T2_3_PLAN.md` aktualisiert auf Nächstpunkt T2.3E (ADR-Indexpflege).

---

## 2026-04-14 — T2.3C Quarantäne-Domäne
**Status:** accepted (Operator-Freigabe 2026-04-14)

1. **Was lief gut:**
   - Schema + Domain-Modul + Runner-Hook + CLI + Tests in einem geschlossenen Rutsch. Kein Pfad bleibt „still" — jeder `runner_exhausted`-Run öffnet automatisch einen `meta.quarantine_case` (Manifest §3.5 / §3.12 erfüllt).
   - DoD-Test (`test_quarantine_replay_resolves_case_on_success`) deckt den vollen Operator-Zyklus ab: Fehler → Auto-Case → Defektbehebung → `quarantine-resolve --action replay` → neuer `job_run_id` → Case `resolved` → `recovery_action` verlinkt.
   - Replay-Failed-Pfad explizit getestet (`test_quarantine_replay_failed_keeps_case_in_progress`): alter Case bleibt `in_progress`, Runner-Hook öffnet sauber einen neuen Case für den neuen Failed Run — keine stille Vermischung.
   - Import-Zyklus `runner ↔ quarantine` ohne neue Zwischenschicht gelöst (Lazy-Imports in beiden Hook-Funktionen). Kein Architektur-Krater für einen technischen Import-Effekt.

2. **Was lief nicht gut:**
   - Severity-Eskalation ist im SQL mit mehrstufiger `CASE`-Kaskade umgesetzt. Funktionsfähig und getestet, aber die Ordnungsregel (`info < warning < error < critical`) lebt halb in Python-Literalen und halb in SQL. Wenn ein fünftes Level dazukommt, muss an zwei Stellen gepflegt werden.
   - Das CLI-Kommando für die „offenen" Listenansicht zeigt beide Stati (`open` + `in_progress`) zusammen, filtert aber nicht prominent in der Ausgabe — Operator muss den Detailview nehmen, um `in_progress` zu erkennen. Akzeptabel in v1.0 CLI-Only, aber bleibt UI-Punkt für T2.6.
   - `evidence_refs_json` bleibt frei-form. Für den Auto-Quarantäne-Pfad ist das Schema implizit stabil, aber externe Opener (künftige Stage-Load-Parser-Fehler) haben noch keinen Vertrag.

3. **Root Cause:**
   - Severity-Ordnung als Literal-Strings war Design-Default aus T2.3A-Mustern; für Phase-1 tragfähig, aber nicht skalierend. Eine `meta.quarantine_severity`-Referenz-Tabelle wäre konsequenter, ist aber für nur vier Werte Overkill.
   - Das generische `evidence_refs`-Feld ist gewollt offen gelassen, weil jede Quell-Domäne eine andere Art Beleg liefert (Dateizeile, Adapter-Request, Schema-Diff). Formalisierung kommt, wenn die ersten drei Opener-Stellen existieren (T2.4/T2.5).

4. **Konkrete Methodänderung:**
   - Bei jedem neuen Executor in T2.4/T2.5: Fehlerpfad muss explizit entscheiden, ob er `open_quarantine_case` selbst ruft (mit scope-spezifischem `reason_code`) oder auf den Runner-Hook vertraut. Wird als Checkliste in den LL-Eintrag jeder Domäne-Tranche aufgenommen.
   - Sobald drei verschiedene Opener existieren: `evidence_refs`-Shape konsolidieren (Pydantic-Model oder JSON-Schema).
   - `quarantine-resolve --action replay` wird zur erwarteten Demo-Flow-Abnahme für jede Phase-1-Domäne (T2.5).

5. **Verifikation:**
   - `tests/test_quarantine.py` (13 Tests) + volle Suite grün (103/103).
   - ADR-0028 auf `Accepted` mit Implementierungs-Notizen.
   - `PROJECT_STATE.md` und `T2_3_PLAN.md` aktualisiert auf Nächstpunkt T2.3D.

---

## 2026-04-13 — T2.3B Internal Runner
**Status:** accepted (Operator-Freigabe 2026-04-13)

1. **Was lief gut:**
   - Klares Bündel Runner-Modul + CLI-Migration + geteilter DB-Helper in einem Rutsch. Kein halber Pfad übrig: `fetch-remote` und `stage-load` laufen ausschließlich über den Runner, jedes CLI-Invocation hinterlässt `meta.job_run`-Evidence (Manifest §3.13 erfüllt).
   - Test-Paket deckt alle DoD-Punkte ab: Claim-Atomarität (Threads + `duckdb.Error`-Toleranz), Concurrency-Key-Block, Retry-Pfad, Retry-Exhausted, deterministischer Replay mit Event-Verkettung, Serve-Mode mit `stop_when_idle`.
   - Suche nach „darkem" Pfad an CLI-Surface vor Runner-Routing hat sich gelohnt: die vorhandene `_run_cli_job`-Helper-Klammer hält beide Kommandos symmetrisch und erlaubt spätere Executor-Zuschaltung ohne Reib.

2. **Was lief nicht gut:**
   - `JobType`-Literal musste mitten im Testlauf zu `str` geöffnet werden, weil Pydantic bei Test-Executoren (`flaky_test`, `always_fails_test`) validiert und ablehnte. Hätte beim Design früher auffallen können — Executor-Registry ist der wahre Gate, nicht das Pydantic-Feld.
   - `metadata.py` behält eigene private Helper (`_connect`/`_row_to_dict`/`_new_id`). Der geteilte `_db.py` ist eingeführt, aber die Alt-Duplikate sind nicht entfernt. Bewusste Scope-Begrenzung, aber bleibt offener Refactor-Punkt.
   - Zwei Alt-Tests (`test_cli_remote_fetch`, `test_cli_stage_load`) prüfen nicht, dass ein `meta.job_run` entsteht — sie bleiben grün, weil die CLI-Ausgabe strukturgleich ist. Der neue Test `test_cli_fetch_remote_routes_through_runner_records_job_run` schließt die Lücke.

3. **Root Cause:**
   - Pydantic-`Literal` wurde aus Dokumentationsnutzen gewählt, nicht als echte Vertragsfläche — die Erweiterbarkeit (ADR-0026 Ontology, ADR-0028 Quarantäne, Tests) erzwingt offene Job-Type-Strings.
   - Der geteilte Helper ist jetzt eingeführt, aber die vorhandene Duplikation in `metadata.py` wurde als nicht blockierend eingestuft, um die Tranche fokussiert zu halten.

4. **Konkrete Methodänderung:**
   - Künftig bei neuen Pydantic-Feldern zwischen „dokumentarischer Liste" (Tuple/Set von Konstanten) und „harter Vertragsfläche" (Literal) explizit unterscheiden. Aufnehmen in `ENGINEERING_MANIFEST` beim nächsten Bump (v1.4).
   - Alt-Helper in `metadata.py` konsolidieren, sobald eine ohnehin anstehende Migration dort Code anfasst (z. B. T2.3D Read-Modell-Trennung). Kein eigener Refactor-Sprint.
   - Ab T2.3C wird jede Operator-CLI, die Daten verändert, in einem Runner-Job gekapselt — keine neuen Direktpfade zu Core- oder Mart-Schreibungen.

5. **Verifikation:**
   - `tests/test_jobs_runner.py::test_replay_failed_run_reproduces_deterministically` bleibt grün.
   - Nächste CLI-Erweiterung (Quarantäne in T2.3C) wird reviewed darauf, dass sie `meta.job_run` erzeugt.
   - `docs/adr/ADR-0025-internal-job-and-run-model.md` auf Status `Accepted`, inklusive „Implementierungs-Notizen (T2.3B)".

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
