# NEW NFL — Lessons Learned (Sammeldatei)

**Format und Regeln:** siehe `LESSONS_LEARNED_PROTOCOL.md`.
**Reihenfolge:** neueste oben.

---

## 2026-04-16 — T2.4B Dedupe-Pipeline-Skelett
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **Fünf-Stufen-Trennung explizit als Module** (`normalize`, `block`, `score`, `cluster`, `review`, plus `pipeline.py`). Jede Stufe hat eine schlanke API (Funktion in, Datenklasse out), ist isoliert testbar (sechs Stage-Tests vor dem ersten E2E-Lauf) und lässt sich später ohne Pipeline-Rewrite austauschen — speziell `Scorer` als `typing.Protocol` macht den späteren ML-Tausch zu einer Drei-Zeilen-Änderung in `pipeline.py`.
   - **Demo-Set deckt alle drei Buckets in einem Lauf** (Auto-Merge: Mahomes-Twin, Review: A. Rodgers vs Aaron Rodgers + P. Mahomes Initial-Match, No-Match: Tom Brady singleton). Damit ist der DoD-Smoke-Pfad nicht synthetisch-leer, sondern führt jeden Code-Pfad einmal aus.
   - **Score-Tabelle ist bewusst flach** (sechs feste Stufen 1.00/0.95/0.80/0.70/0.60/0.50). Reicht für Phase-1, ist trivial dokumentier- und review-bar; Operator versteht nach 30 Sekunden, warum ein Pair in Auto-Merge oder Review landet. Komplexere gewichtete Summen wären für einen Stub Premature Optimization.
   - **Block-Drop für Records ohne Last-Name.** Statt sie als O(n)-Vergleichspartner durchzuschieben, fallen sie aus dem Block-Pool — fail-loud-Prinzip aus dem Manifest. In realen Daten sind das Datenfehler, kein Match-Kandidat.
   - **Singletons als eigene Cluster gezählt.** `cluster_count` spiegelt die wahre Anzahl distinkter Entitäten, nicht nur die Auto-Merge-Cluster — sonst gäbe es bei sechs Inputs ohne jeden Auto-Merge `cluster_count = 0`, was irreführend ist.

2. **Was lief nicht gut:**
   - **`meta.cluster_assignment` fehlt.** Cluster werden in v0_1 nicht persistiert (nur `cluster_count`). Für T2.5C ist das ein Vorausschulden — die Pipeline kann nicht out-of-the-box „welche Records gehören zur selben Entität" beantworten, sobald sie den DuckDB-Lebenszyklus verlässt. Bewusst akzeptiert: persistente Cluster-Tabelle wäre Vorgriff auf T2.5C-Anforderungen, die heute nicht bekannt sind.
   - **`dedupe-review-resolve` CLI fehlt.** Operator kann Review-Items nur lesen (`dedupe-review-list`), nicht direkt schließen. Analog zu `quarantine-resolve` aus T2.3C — wäre symmetrisch sinnvoll, ist aber nicht im DoD von T2.4B. Backlog-Eintrag in ADR-0027 §Offene Punkte.
   - **Kein Adapter zwischen `core.player` und `RawPlayerRecord`.** Die Pipeline läuft heute nur gegen das eingebaute Demo-Set oder gegen extern injizierte `list[RawPlayerRecord]`. Sobald T2.5C echte Player-Records erzeugt, braucht es einen `core_to_dedupe_input(...)`-Adapter. Heute zu früh — Schema von `core.player` steht noch nicht fest.
   - **Kein Runner-Executor für `dedupe-run`.** Der CLI-Pfad ruft `run_player_dedupe` direkt, nicht über `meta.job_run`. Begründung: T2.3D/T2.3C-Pattern routen Schreibpfade über den Runner, aber Demo-Smokes sind keine Produktions-Runs. Sobald T2.5C Dedupe gegen reale Daten fährt, sollte ein `dedupe_run`-Executor analog zu `mart_build` her.

3. **Root Cause:**
   - Cluster-Persistenz und Review-Resolve-Pfad hängen am Player-Schema. Solange `core.player` nicht existiert (kommt mit T2.5C), gibt es keinen Pin, an dem ein FK festgemacht werden könnte. Manifest §3.7: keine Schema-Entscheidungen unter spekulativem Druck.
   - Runner-Bypass ist temporär — der Demo-Pfad braucht keine Replay-Garantie. Sobald „echte" Dedupe-Runs Quarantäne erzeugen können, dreht sich das.

4. **Konkrete Methodänderung:**
   - **Pipeline-Stufen werden ab T2.5 immer mit eigenem Pydantic-Modell als Stage-Output definiert** (nicht: Tuple/Dict). T2.4B folgt dem schon (`NormalizedPlayer`, `BlockedPair`, `ScoredPair`, `Cluster`); ist die Default-Form für jede neue Pipeline.
   - **Stub-Pipelines bekommen Demo-Inputs aus dem Code, nicht aus Test-Fixtures.** Tests fahren auf demselben Demo-Set wie der CLI-Smoke (`DEMO_PLAYER_RECORDS`). Gleichzeitig sind sie Doku — ein neuer Mitarbeiter sieht in einer Datei, was die Pipeline tut.
   - **Scorer-Tausch geht über `Scorer`-Protocol-Argument** in der Top-Level-Funktion (`run_player_dedupe(scorer=...)`). Kein Registry, kein Settings-Schalter. Wenn T2.5C einen anderen Scorer braucht, wird er als Default-Argument durchgereicht.

5. **Verifikation:**
   - `pytest` grün: 13 Tests in [tests/test_dedupe.py](../tests/test_dedupe.py), gesamte Suite 136 passed.
   - `cli dedupe-run --domain players --demo` erzeugt einen `meta.dedupe_run`-Datensatz mit `RUN_STATUS=success`, `INPUT_RECORD_COUNT=6`, `AUTO_MERGE_PAIR_COUNT >= 1`, `REVIEW_PAIR_COUNT >= 1`.
   - `cli dedupe-review-list --domain players` listet die offenen Review-Pairs sortiert nach Score.
   - ADR-0027 final `Accepted` mit Implementierungs-Notizen + Offenen-Punkte-Backlog für T2.5C.
   - `PROJECT_STATE.md` markiert T2.4 vollständig abgeschlossen, nächster Bolzen ist T2.5A (Teams-Domäne).

---

## 2026-04-16 — T2.4A Ontology-as-Code-Skelett
**Status:** draft (wartet auf Operator-Freigabe)

1. **Was lief gut:**
   - **TOML statt YAML.** Stdlib `tomllib` (Python 3.12+) deckt die rein deklarative Struktur (Term, Aliases, Value Sets) vollständig ab — keine zusätzliche Runtime-Abhängigkeit (PyYAML), keine Versionspflege. ADR-0026 hatte YAML als Default vorgesehen, das war im Implementierungs-Druck eine vermeidbare Abhängigkeit.
   - **`content_sha256`-Idempotenz** über sortierten Hash aus `(Dateiname, Inhalt)` — wiederholter Load identischer Quelle ist garantiert No-Op und liefert dieselbe `ontology_version_id` zurück. Kein Diff-Vergleich pro Tabelle, kein UPSERT-Pfad: einmal geladen, fertig. `is_active`-Flag pro `source_dir` macht Versions-Switching billig.
   - **Service-Surface mit Pydantic-Modellen** (`OntologyTerm`, `OntologyValueSet`, `OntologyValueSetMember`, `OntologyTermDetail`) — CLI, Tests und (später) Web-Routen reden über stabile Typen, nicht über rohe Dicts. Konsistenz zur Quarantäne- und Mart-Surface aus T2.3C/D.
   - **Alias-Auflösung in `describe_term`** — `cli ontology-show --term-key pos` findet `position`, ohne dass Operator die kanonische Form raten muss. `alias_lower`-Spalte ist vorberechnet, kein `LOWER(...)` in der WHERE-Klausel.

2. **Was lief nicht gut:**
   - `meta.ontology_mapping` ist als Tabelle angelegt, in v0_1 aber unbenutzt — der Schema-Aufwand ist gerechtfertigt, weil T2.5 die Tabelle braucht, aber das ist genau der Typ Vorgriff, vor dem Manifest §3.7 warnt. Bewusst akzeptiert: das Schema einer einzelnen Tabelle ist günstig, ein Migration-Pfad mit FK-Hinzufügung später wäre teurer.
   - Kein impliziter Bootstrap-Load. Der Operator muss `cli ontology-load --source-dir ontology/v0_1` einmal explizit ausführen. Das ist gewollt (Promotion soll explizite Version referenzieren), aber für die nächste Tranche eine offene UX-Frage: `cli bootstrap` könnte v0_1 aus dem Repo-Root automatisch laden.
   - Im Loader hartcodiert: TOML-Erwartung an `term_key`, `aliases`, `value_sets[*].key`, `value_sets[*].members[*].value`. Kein Schema-Validator (Pydantic gegen Roh-TOML) — Fehler werden als `ValueError` mit Dateiname geworfen. Reicht für v0_1, aber sobald externe Beiträger Terme schreiben, will man Pydantic-Validation auf der Rohstruktur.

3. **Root Cause:**
   - YAML im ADR war Erblast aus dem A0-Konzept, wo eine breite Werkzeug-Auswahl noch sinnvoll war. Im Implementierungs-Druck zeigt sich, dass für drei flach strukturierte Term-Dateien TOML reicht — und die Manifest-§3.13-Pflicht zur minimal-möglichen Abhängigkeit gewinnt.
   - `ontology_mapping`-Tabelle ohne Loader-Pfad: bewusster Trade-off zwischen jetzigem Schema-Vorgriff und späterem ALTER-TABLE-Risiko.

4. **Konkrete Methodänderung:**
   - **Default-Format für deklarative Repo-Quellen ist TOML**, solange stdlib reicht. YAML nur, wenn Anchors/Multiline/Komplexstruktur das brauchen. ADR-Updates spiegeln diese Entscheidung als Implementierungs-Notiz wider.
   - **Neue Domänen-Loader stempeln `content_sha256`** auf der Versions-Zeile (nicht erst pro Datei). Erlaubt Idempotenz auf Verzeichnisebene.
   - Nächster Bolzen (T2.4B) prüft, ob ein gemeinsamer `Loader`-Helper-Layer (`hash_directory`, `apply_idempotent`) die Wiederholung lohnt — heute zu früh, T2.4A ist die erste Instanz.

5. **Verifikation:**
   - `pytest` grün: 11 Tests in [tests/test_ontology.py](../tests/test_ontology.py), gesamte Suite 123 passed.
   - CLI-Smoke: `ontology-load` druckt `IS_NEW=yes` beim ersten Lauf, `IS_NEW=no` beim zweiten gegen identische Quelle.
   - `meta.ontology_version` enthält pro Quellverzeichnis genau eine `is_active=TRUE`-Zeile; ein zweiter Load aus alternativem Verzeichnis erzeugt zweite aktive Version (parallele Quellen erlaubt).
   - ADR-0026 final `Accepted` mit Implementierungs-Notizen; `docs/adr/README.md` zeigt neuen Status; `PROJECT_STATE.md` markiert T2.4A ✅.

---

## 2026-04-14 — T2.3E ADR-Index abgeschlossen
**Status:** accepted (Operator-Freigabe 2026-04-14)

1. **Was lief gut:**
   - `docs/adr/README.md` ist jetzt ein vollständiger Index ADR-0001–ADR-0030 mit Status + Tranchen-Anker. Status-Quelle bleibt das ADR-Dokument selbst (single source of truth), der Index ist nur Navigations- und Übersichts-Layer.
   - Bewusste Trennung: T2.3-eigene ADRs (0025/0028/0029) sind `Accepted`. ADR-0026/0027/0030 bleiben `Proposed` bis zur Umsetzung in T2.4A/T2.4B/T2.6A — keine vorgezogene Akzeptanz, die später relativiert werden müsste.

2. **Was lief nicht gut:**
   - ADR-0001 bis ADR-0018 verwenden eine ältere Status-Konvention (`Status: Accepted` als Inline-Zeile statt eigener Section). Der Index normalisiert das nach außen, aber die Heterogenität bleibt im Bestand. Kein Refactor, weil low-value.
   - Die Tabelle ist statisch — Status-Drift im ADR-Dokument selbst wird nicht automatisch gespiegelt. Bei nächster Tranche prüfen, ob ein Mini-Skript den Index regeneriert.

3. **Root Cause:**
   - Die Inline-Status-Konvention der frühen ADRs ist Erblast aus A0 vor `LESSONS_LEARNED_PROTOCOL.md`. Die neueren ADRs nutzen `## Status` als Section, was maschinenlesbar ist.

4. **Konkrete Methodänderung:**
   - Neue ADRs (ab ADR-0031) verwenden ausschließlich die `## Status`-Section-Konvention. Bestand bleibt unangetastet.
   - Beim nächsten Index-Update (T2.4-ADRs `Accepted` setzen) Snippet `awk '/^## Status/{getline; print}'` als Regenerator verwenden.

5. **Verifikation:**
   - `docs/adr/README.md` mit Tabelle ADR-0001–ADR-0030 + Status + Tranchen-Anker.
   - `PROJECT_STATE.md` und `T2_3_PLAN.md` markieren T2.3E ✅; nächster Bolzen ist T2.4A (Ontology-as-Code).

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
