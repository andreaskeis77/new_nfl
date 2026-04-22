# ADR-0031: Adapter Slice Strategy — Ein Adapter, N Slices via Python-Registry

## Status
Accepted (2026-04-22, Treiber: T2.5A Teams-Domain, bestätigt in T2.5B Games-Domain)

## Kontext

Bis T2.4 hat jeder `adapter_id` genau **eine** Nutzlast:

- `nflverse_bulk.default_remote_url` → `dictionary_schedules.csv` (hart verdrahtet in `DEFAULT_SOURCES`, `remote_fetch.py`)
- `stage_dataset = f"stg.{adapter_id}"` (hart verdrahtet in `adapters/base.py::StaticSourceAdapter.build_plan`)
- `execute_core_load` dispatched über `_source_table_for_adapter(adapter_id)` und `_target_table_for_adapter(adapter_id)` — beides Mappings, die aktuell nur `adapter_id="nflverse_bulk" → core.schedule_field_dictionary` kennen
- `_executor_mart_build` dispatched über `params["mart_key"]` mit aktuell genau einem Key

Für T2.5A–T2.5F (Teams, Games, Players, Rosters, TeamStats, PlayerStats) brauchen wir aus **demselben** `nflverse_bulk`-Adapter mindestens sechs separate CSV-Datensätze, jeder in ein eigenes `stg.*`/`core.*`/`mart.*`-Paar. Gleichzeitig wollen wir die bestehende Skelett-Klarheit nicht durch sechs neue `adapter_id`s (`nflverse_bulk_teams`, `nflverse_bulk_games`, …) aufweichen — die Tier-/Priority-/Transport-Konfiguration bleibt pro Quelle stabil, nur die Nutzlast variiert.

Parallel wollen wir für die Konflikt-/Quarantäne-Demo in T2.5A denselben Slice (`teams`) aus einer **zweiten** Quelle (`official_context_web`) cross-prüfen — der Slice-Begriff ist also orthogonal zum Adapter, nicht ein Unter-Attribut.

## Entscheidung

Wir führen eine **Slice-Registry auf Python-Ebene** ein, kein neues `meta.*`-Schema.

```python
# src/new_nfl/adapters/slices.py
@dataclass(frozen=True)
class SliceSpec:
    adapter_id: str
    slice_key: str
    label: str
    remote_url: str             # "" wenn fixture-driven (Tier-B/C ohne HTTP)
    stage_target_object: str    # -> stg.<stage_target_object>
    core_table: str             # -> core.<name>, leer-string wenn slice nur staged
    mart_key: str               # -> Dispatch in _executor_mart_build, leer wenn kein Mart
    tier_role: Literal["primary", "cross_check"]
    notes: str

SLICE_REGISTRY: dict[tuple[str, str], SliceSpec] = { ... }
```

**Regeln:**

1. **Quelle der Wahrheit für Slice-Dispatch ist ausschließlich `SLICE_REGISTRY`.** `stage_load.py`, `core_load.py`, `remote_fetch.py`, Runner-Executors und CLI schauen hier nach — keine verstreuten `if adapter_id == "X"`-Zweige mehr für slice-spezifische Pfade.
2. **`source_registry` bleibt pro `adapter_id` granular.** `default_remote_url` darf dort stehen (für den historischen `schedule_field_dictionary`-Slice, Backwards-Compat), ist aber kein kanonischer Pfad mehr — der `SliceSpec.remote_url` gewinnt.
3. **`stage_dataset` in `AdapterPlan`** bleibt der konservative Default `stg.<adapter_id>` für dry-runs ohne Slice-Kontext; der konkrete Stage-Tabellenname wird bei `stage-load --slice X` zur Laufzeit aus `SliceSpec.stage_target_object` aufgelöst.
4. **CLI- und Executor-Signaturen bekommen einen expliziten `slice_key`-Parameter**. Default `slice_key="schedule_field_dictionary"` für Rückwärtskompatibilität T2.0A–T2.4.
5. **Tier-Rolle ist Teil des Slices, nicht des Adapters**. Ein Adapter kann in Slice A `primary` (Tier-A) und in Slice B `cross_check` (Tier-B) sein. Für T2.5A: `(nflverse_bulk, teams)` ist `primary`, `(official_context_web, teams)` ist `cross_check`.
6. **`core.*`-Promotion ist slice-zentrisch, nicht adapter-zentrisch**. `execute_core_load_teams(settings, execute=True)` liest alle Slices mit `core_table="core.team"` und joint Tier-A-Basis mit Tier-B-Cross-Checks; Diskrepanzen eröffnen `meta.quarantine_case` (siehe ADR-0028), Tier-A-Werte gewinnen nach Tier-Hierarchie (ADR-0007).

## Alternativen

1. **N Sub-Adapter** (`nflverse_bulk_teams`, `nflverse_bulk_games`, …).
   Vorteil: triviale Abbildung in bestehender Struktur.
   Nachteil: Bläht `source_registry` und Adapter-Katalog 6× auf, duplizierte Tier-/Transport-Konfiguration, verwirrt die Operator-Sicht (`health`, `browse-adapters`). Abgelehnt.

2. **Slice als ontology-term** (`ontology/v0_1/term_slice.toml`).
   Vorteil: konsistent mit ADR-0026.
   Nachteil: Ontology-Terme sind Fachsemantik (Position, Conference, Division) — Slices sind technische Datenschnitte. Vermischt Concerns. Abgelehnt.

3. **`meta.adapter_slice`-Tabelle** (gleich als DB-Registry).
   Vorteil: dynamisch pflegbar, operator-inspizierbar.
   Nachteil: zu früh — Slices sind aktuell (und absehbar bis v1.0) code-deklariert (bekannte CSVs, bekannte Schemas). Eine Python-Registry ist redeploy-trivial, eine DB-Tabelle braucht Migration + Seeding. Verschoben (Trigger: erste dynamisch konfigurierte Slice, frühestens v1.1).

## Konsequenzen

**Positiv:**
- Ein Adapter kann ohne Katalog-Aufblähung mehrere CSVs bedienen.
- Tier-A/Tier-B-Cross-Check auf demselben Slice ist explizit modellierbar (ADR-0007 praktisch anwendbar).
- Dispatch-Logik zentralisiert in `SLICE_REGISTRY`; ein neuer Slice = ein Registry-Eintrag + Core-Promoter + Mart-Builder.

**Negativ:**
- CLI- und Executor-Signaturen wachsen um `--slice`-Parameter; Operator muss den Slice-Begriff verstehen.
- Doppelte Wahrheit zwischen `source_registry.default_remote_url` (legacy) und `SliceSpec.remote_url` (kanonisch) bis `default_remote_url` mit dem nächsten Metadata-Migration-Bump entfernt wird (T2.6 vorgesehen).

## Rollout

- **T2.5A (jetzt):** Registry + Slices `(nflverse_bulk, schedule_field_dictionary)`, `(nflverse_bulk, teams)`, `(official_context_web, teams)`. CLI-Flag `--slice` additiv, Default zeigt auf `schedule_field_dictionary` (alte Pfade grün).
- **T2.5B–T2.5F:** pro neuer Domain je ein Registry-Eintrag + Core-Promoter + Mart-Builder. Kein Katalog-Eingriff.
- **T2.6:** `source_registry.default_remote_url` deprecated; Cleanup + Migration zum Slice-only-Modell.
- **v1.1 (optional):** Migration der Registry nach `meta.adapter_slice`, falls dynamische Slice-Konfiguration nötig wird.

## Offene Punkte

- **Konvention `core_table` leer-string**: Noch nicht endgültig — für Slices, die rein in `stg.*` leben sollen (z. B. reine Cross-Checks, die erst bei Core-Promotion des primären Slices gelesen werden), ist `core_table=""` vorgesehen. Beispiel in T2.5A/T2.5B: `(official_context_web, teams)` und `(official_context_web, games)` haben `core_table=""` — ihre Daten fließen nicht direkt nach `core.team`/`core.game`, sondern werden beim Promoten des primären Slices als Cross-Check konsultiert.
- **Versionierung der Slice-Registry**: aktuell implizit durch Code-Stand. Bei `_v2`-Schema-Bumps ist der Slice-Key (`schedule_field_dictionary_v1` → `_v2`) der Freiheitsgrad; die Entscheidung, ob Slice-Versionierung eigenes Attribut wird, fällt in T2.6.

## Implementierungsnotizen (2026-04-22, T2.5B)

- **CLI `list-slices` geliefert** (T2.5B): pipe-separierte Operator-Sicht über `SLICE_REGISTRY`; Spalten `adapter_id | slice_key | tier_role | stage_qualified_table | core_table | mart_key | has_url | label`.
- **Registry nach T2.5B**: 5 Einträge — `(nflverse_bulk, schedule_field_dictionary)`, `(nflverse_bulk, teams)`, `(nflverse_bulk, games)`, `(official_context_web, teams)`, `(official_context_web, games)`.
- **Erste produktive HTTP-Runde**: `(official_context_web, games)` wird in T2.5B mit einem stdlib-`ThreadingHTTPServer` in den Tests echt über `urllib.request.urlopen` in `execute_remote_fetch` geladen — bestätigt, dass `remote_url=""` zusammen mit `--remote-url`/`remote_url_override` der korrekte Einsprungspunkt für Tier-B-Fixtures bleibt.
- **Tier-B-Quarantäne belastbar**: Score-/Venue-Diskrepanzen zwischen Tier-A (`nflverse_bulk`) und Tier-B (`official_context_web`) öffnen `meta.quarantine_case` mit `scope_type='game'`, `reason_code='tier_b_disagreement'`; Tier-A-Werte gewinnen in `core.game` (ADR-0007).
- **`core.*` slice-zentrisch bestätigt**: `execute_core_game_load` liest alle Slices mit `core_table='core.game'` aus der Registry, promoviert Tier-A und vergleicht Tier-B Feld für Feld — identisches Muster wie `execute_core_team_load`; Skalierung auf T2.5C–T2.5F ohne Strukturbruch.
