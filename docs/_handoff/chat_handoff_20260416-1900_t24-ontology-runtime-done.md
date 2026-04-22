# Chat-Handoff 2026-04-16 19:00 — T2.4 Ontology Runtime abgeschlossen

## Trigger

§2.1 „Tranche-Abschluss + größerer Themenwechsel": **T2.4 (T2.4A + T2.4B) ist vollständig abgeschlossen** (Ontologie-as-Code, Dedupe-Pipeline-Skelett mit fünf Stufen). Der nächste Block **T2.5 — Domain Expansion (KW 20–22)** ist thematisch deutlich anders: sechs sequentielle Sub-Tranches (Teams, Games, Players, Rosters, Team-Stats, Player-Stats) mit dem immer gleichen Muster *Adapter → Stage-Load → Core-Promotion → Read-Modell* gegen reale externe Quellen (nflverse, ESPN). Das ist die erste vollständige Orchestrierung aller bisher gebauten Foundation-Komponenten (Runner, Mart, Quarantäne, Ontologie, Dedupe).

Zusätzlich §2.1 „Kontext-Druck": Diese Session hat T2.3C → T2.3D → T2.3E → T2.4A → T2.4B in einem Zug ausgeführt — fünf Tranchen, fünf Commits, ~250 Test-Cases dazu, sechs ADRs `Accepted` gesetzt. Vor dem Eintauchen in T2.5 ist ein sauberer Cut sinnvoll.

## Was wurde in dieser Session erreicht

### T2.3C — Quarantäne-Domäne (Commit `0c61b84`)
- `meta.quarantine_case` + `meta.recovery_action`, Auto-Hook im Runner bei `runner_exhausted`.
- CLI `list-quarantine`, `quarantine-show`, `quarantine-resolve --action replay|override|suppress`.
- ADR-0028 → `Accepted`.

### T2.3D — Read-Modell-Trennung (Commit `71b206b`)
- `mart.schedule_field_dictionary_v1` als versionierte Read-Projektion.
- Spalten-toleranter Builder (`DESCRIBE` auf Source, optionale Provenance-Spalten).
- AST-basierter Lint-Test verbietet `core.*`/`stg.*`/`raw/` in Read-Modulen.
- CLI `mart-rebuild`; `core-load --execute` triggert Mart-Build implizit.
- ADR-0029 → `Accepted`.

### T2.3E — ADR-Index aufgeräumt (Commit `0718743`)
- `docs/adr/README.md` als vollständiger Index ADR-0001 bis ADR-0030 mit Status + Tranchen-Anker.

### T2.4A — Ontology-as-Code-Skelett (Commit `22462e8`)
- 6 `meta.ontology_*`-Tabellen (`version`, `term`, `alias`, `value_set`, `value_set_member`, `mapping`).
- Loader [src/new_nfl/ontology/loader.py](../../src/new_nfl/ontology/loader.py) idempotent über `content_sha256` (Hash über sortierte Datei-Inhalte).
- 3 TOML-Seeds in [ontology/v0_1/](../../ontology/v0_1): `term_position.toml`, `term_game_status.toml`, `term_injury_status.toml` (3 Terms, 8 Aliases, 4 Value Sets, 34 Members).
- CLI `ontology-load --source-dir`, `ontology-list`, `ontology-show --term-key <key|alias>` (Alias-Auflösung über `alias_lower`).
- **TOML statt YAML** (stdlib `tomllib`, keine PyYAML-Abhängigkeit) — siehe ADR-0026 Implementierungs-Notiz.
- ADR-0026 → `Accepted`.

### T2.4B — Dedupe-Pipeline-Skelett (Commit `baab7f7`)
- 5 explizite Stufen unter [src/new_nfl/dedupe/](../../src/new_nfl/dedupe): `normalize`, `block`, `score`, `cluster`, `review` + `pipeline.py`.
- `RuleBasedPlayerScorer` (`kind=rule_based_v1`) mit 6 Score-Stufen (1.00/0.95/0.80/0.70/0.60/0.50), `Scorer` als `typing.Protocol` für späteren ML-Tausch.
- Connected-Components-Cluster mit Singleton-Erhalt.
- `meta.dedupe_run` + `meta.review_item` als Evidence.
- CLI `dedupe-run --domain players --demo`, `dedupe-review-list`.
- Demo-Set (6 QB-Records inkl. Mahomes-Twin, A. Rodgers-Initial-Match, Tom-Brady-Singleton) deckt Auto-Merge + Review + No-Match in einem Lauf.
- ADR-0027 → `Accepted`.

### Test-Suite
- **136 Tests grün** (von 73 zu Beginn der T2.3-Tranche).

### Doku
- `PROJECT_STATE.md`, `T2_3_PLAN.md`, `LESSONS_LEARNED.md`, `docs/adr/README.md` nach jeder Tranche aktualisiert.
- Lessons-Learned-Drafts für T2.3C, T2.3D, T2.3E, T2.4A, T2.4B sind sämtlich vom Operator freigegeben.
- ADR-0025/26/27/28/29 sind `Accepted`. Nur ADR-0030 (UI Stack) bleibt `Proposed` bis T2.6A.

## Was ist offen / unklar / Risiko

- **Backlog aus ADR-0027 §Offene Punkte (für T2.5C):**
  - `meta.cluster_assignment` als persistente Cluster-Tabelle.
  - `core.player → RawPlayerRecord`-Adapter, sobald `core.player` existiert.
  - `dedupe-review-resolve` CLI parallel zu `quarantine-resolve`.
  - Runner-Executor `dedupe_run` parallel zu `mart_build`.
- **`meta.ontology_mapping` ist als Tabelle angelegt, in v0_1 unbenutzt** — wird in T2.5 erstmals gebraucht (Cross-Source-Mappings).
- **Kein impliziter Bootstrap-Load der Ontologie**: Operator muss `cli ontology-load --source-dir ontology/v0_1` einmal explizit ausführen. UX-Frage offen, ob `cli bootstrap` v0_1 automatisch lädt.
- **Pre-existing Ruff-Befunde (~11)** bleiben unangetastet — nicht aus dieser Session.
- **Backlog aus T2.5-Vorüberlegung:** Roster-Domäne (T2.5D) bringt erstmals Bitemporalität (`valid_from`/`valid_to`); T2.5E/F bringen Window-Funktionen und Konflikt-Auflösung über Tier — beides Komplexitäts-Sprünge gegenüber der bisherigen einfachen Promotion. ADR-würdig, sobald konkret.
- **Git-Status:** sauber, alle T2.3C–T2.4B-Commits sind drin (`baab7f7` ist HEAD). Branch `main` ist 8 Commits ahead von `origin/main` — Push noch nicht erfolgt.

## Aktueller Arbeitsstand

- **Phase:** T2.4 vollständig abgeschlossen, Übergang zu T2.5 (Domain Expansion).
- **Letzter erfolgreicher Pflichtpfad:** `pytest` 136/136 grün (~3 min), inkl.:
  - `tests/test_ontology.py` (11 Cases)
  - `tests/test_dedupe.py` (13 Cases)
  - `tests/test_mart.py` (9 Cases inkl. AST-Lint)
  - `tests/test_quarantine.py` (13 Cases)
- **Letzter Commit:** `baab7f7 T2.4B: dedupe pipeline skeleton (5 stages + rule-based scorer)`.
- **Nächster konkreter Schritt:** **T2.5A — Teams** gemäß `T2_3_PLAN.md` §4.

## Strategische Analyse für die nächste Session

### Was die Foundation jetzt liefert (Stand HEAD `baab7f7`)
1. **Internal Job Runner** mit atomarem Claim, Retry-Policies, Replay (T2.3A/B).
2. **Quarantäne als First-Class-Domäne** mit Auto-Hook bei `runner_exhausted` (T2.3C).
3. **`mart.*` als alleiniger Read-Pfad** mit AST-Lint-Guard (T2.3D).
4. **Ontologie-as-Code v0_1** mit idempotentem Loader und Alias-Auflösung (T2.4A).
5. **Dedupe-Pipeline-Skelett** mit pluggable `Scorer`-Protocol (T2.4B).

### Was T2.5 zum ersten Mal orchestriert
T2.5 ist nicht mehr Bauen-eines-Bausteins, sondern **erste vollständige Anwendung** aller Foundation-Komponenten gegen reale externe Quellen:
- T2.5A (Teams) provoziert absichtlich einen **Tier-A vs Tier-B-Konflikt** zwischen nflverse und ESPN — das ist der erste echte Quarantäne-Test-Case in Production-ähnlicher Form.
- T2.5C (Players) ist die **erste echte Dedupe-Anwendung** und braucht den Adapter `core.player → RawPlayerRecord` plus `meta.cluster_assignment` (siehe ADR-0027 Offene Punkte).
- T2.5D (Rosters) bringt **Bitemporalität** (`valid_from`/`valid_to`) — erstmals in v1.0. ADR-würdig.
- T2.5E/F (Stats) bringen **Window-Functions auf Saison-/Karriere-Ebene** und Konflikt-Auflösung über Tiering.

### Risiken & Vorschläge für T2.5A
- **Konkretes erstes Bolt: T2.5A Teams.** Pflichtpfade: `cli register-job` für `teams_fetch_remote` und `teams_stage_load`, dann `core-load --adapter-id nflverse_bulk` für die Teams-Slice, schließlich `mart-rebuild --mart-key team_overview_v1`. Tier-A (nflverse) vs Tier-B (ESPN) Konflikt wird über Quarantäne sichtbar gemacht.
- **Schema-Frage vorab klären:** Welche Spalten gehören auf `core.team` (Stammdaten: `team_id`, `team_abbr`, `team_name`, `conference`, `division`, `team_color_primary`, …)? Wenige, präzise Spalten — keine spekulativen Felder. Der UI-Style-Guide §1 verlangt offizielle Vollnamen.
- **Adapter-Refactor anstehend:** Der bestehende `nflverse_bulk`-Adapter ist heute auf das Schedule-Dictionary verdrahtet. Für T2.5A muss er entweder mehrere Slices unterstützen (über `--source-file-id` plus Slice-Identifier) oder pro Domäne ein eigener Sub-Adapter werden. Empfehlung: **eigenes ADR (ADR-0031) zur Adapter-Slice-Strategie** vor T2.5A-Code.
- **Time-Box-Warnung:** T2.5 ist im Plan auf 3 Wochen (KW 20–22) für 6 Sub-Tranches angesetzt — das ist eng. Sobald T2.5A länger als 1 Woche dauert, Plan-Realität-Vergleich machen und mit Operator über Re-Slicing reden.

### Was *nicht* in T2.5 gehört
- **UI-Arbeit** — bleibt T2.6 (Web-UI v1.0).
- **VPS-Deploy** — verschoben auf nach v1.0 (T3.1).
- **ML-Scorer für Dedupe** — eigener ADR, nicht v1.0.
- **Provenance-UI** — T2.6G.

## Geänderte / neue Dokumente in dieser Session

### Neu
- `src/new_nfl/jobs/quarantine.py`
- `src/new_nfl/mart/__init__.py`, `src/new_nfl/mart/schedule_field_dictionary.py`
- `src/new_nfl/ontology/__init__.py`, `src/new_nfl/ontology/loader.py`
- `src/new_nfl/dedupe/__init__.py`, `src/new_nfl/dedupe/{normalize,block,score,cluster,review,pipeline}.py`
- `ontology/v0_1/term_{position,game_status,injury_status}.toml`
- `tests/test_quarantine.py`, `tests/test_mart.py`, `tests/test_ontology.py`, `tests/test_dedupe.py`
- `docs/_handoff/chat_handoff_20260416-1900_t24-ontology-runtime-done.md` (dieses Dokument)

### Geändert
- `src/new_nfl/metadata.py` (9 neue `TABLE_SPECS`-Einträge: 2 Quarantäne + 6 Ontologie + 2 Dedupe; minus Schedule-Dictionary-Anpassung in T2.3D)
- `src/new_nfl/jobs/runner.py` (Auto-Quarantäne-Hook + `mart_build`-Executor)
- `src/new_nfl/jobs/__init__.py` (Re-Exports)
- `src/new_nfl/core_load.py`, `src/new_nfl/core_browse.py`, `src/new_nfl/core_lookup.py`, `src/new_nfl/core_summary.py`, `src/new_nfl/web_preview.py`, `src/new_nfl/web_server.py` (alle auf `mart.*` umgestellt)
- `src/new_nfl/cli.py` (Quarantäne-, Mart-, Ontologie-, Dedupe-Kommandos)
- Bestehende Tests (`test_core_browse.py`, `test_core_lookup.py`, `test_core_summary.py`, `test_core_lookup_cli.py`, `test_web_preview.py`, `test_web_server.py`) auf `mart.*` umgestellt
- `docs/PROJECT_STATE.md`, `docs/T2_3_PLAN.md`, `docs/LESSONS_LEARNED.md`
- `docs/adr/README.md`, `docs/adr/ADR-0026..0029-*.md`

## Lessons-Learned-Einträge

Alle in `docs/LESSONS_LEARNED.md`, jeweils oberster Eintrag pro Tranche, **alle Status `accepted`** (Operator-Freigabe je Tranche erteilt):
- 2026-04-16 — T2.4B Dedupe-Pipeline-Skelett
- 2026-04-16 — T2.4A Ontology-as-Code-Skelett
- 2026-04-14 — T2.3E ADR-Index abgeschlossen
- 2026-04-14 — T2.3D Read-Modell-Trennung (`mart.*`)
- 2026-04-14 — T2.3C Quarantäne-Domäne

## Vor dem Wechsel noch zu tun (in dieser Session)

1. **Optional:** `git push origin main` (8 Commits ahead). Erfordert Operator-Freigabe.
2. **Empfohlen:** ADR-0031 (Adapter-Slice-Strategie für T2.5) als `Proposed`-Skelett anlegen, bevor die nächste Session damit anfängt — vermeidet Diskussion im Implementierungs-Druck.

## Starter-Prompt für die neue Session

Siehe Block am Ende dieses Dokuments.

## Verweise

- `docs/CHAT_HANDOFF_PROTOCOL.md`
- `docs/LESSONS_LEARNED_PROTOCOL.md`
- `docs/T2_3_PLAN.md` (T2.5 ab §4)
- `docs/adr/ADR-0026-ontology-as-code-with-runtime-projection.md` (Implementierungs-Notizen T2.4A)
- `docs/adr/ADR-0027-dedupe-pipeline-as-explicit-stage.md` (Implementierungs-Notizen T2.4B + Backlog)
- `docs/adr/README.md`
- `docs/_handoff/chat_handoff_20260413-1700_t23a-job-run-skeleton-done.md` (Vor-Handoff)
