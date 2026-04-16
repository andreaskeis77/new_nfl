# ADR-0026: Ontology-as-Code with Runtime Projection

## Status
Accepted (T2.4A, 2026-04-16)

## Kontext
NEW NFL braucht eine kanonische Ontologie für Begriffe, Aliases, Mappings, Value Sets und Constraints (Spielerpositionen, Stat-Familien, Verletzungs-Status, Off-Field-Kategorien, Wetter-Variablen). Eine reine Code-Repräsentation ist schwer reviewbar, ein Triple-Store wäre für ein single-operator-System überdimensioniert.

## Entscheidung
Die Ontologie liegt **als Code im Repository** unter `ontology/<version>/*.toml`. Beim Bootstrap und bei Ontologie-Releases projiziert ein Loader sie deterministisch in `meta.ontology_*`-Tabellen in DuckDB:

- `meta.ontology_version`
- `meta.ontology_term`
- `meta.ontology_alias`
- `meta.ontology_value_set`
- `meta.ontology_value_set_member`
- `meta.ontology_mapping`

Jede Promotion in `core.*` referenziert eine `ontology_version_id`. Änderungen an der Ontologie, die kanonische Felder betreffen, sind ADR-pflichtig.

**Nicht Teil dieser Entscheidung:** RDF-/OWL-/SHACL-Export. Bleibt optional als späterer Interop-Layer.

## Begründung
- versionierbar, reviewbar via Git.
- testbar mit Standard-Pytest.
- relationale Projektion passt zu DuckDB-zentriertem Read-Pfad.
- keine zusätzliche Laufzeit-Komponente nötig.

## Konsequenzen
**Positiv:** Ontologie-Änderungen sind PRs, kein „Datenbank-Edit". Promotions sind reproduzierbar gegen historische Ontologie-Versionen.
**Negativ:** keine eingebaute Reasoning-Engine — bewusst akzeptiert.

## Alternativen
1. Triple-Store (Apache Jena, Stardog) — überdimensioniert.
2. Reine Datenbank-Pflege — schlecht reviewbar.
3. Pydantic-only in Python-Code — keine Sichtbarkeit für nicht-Python-Operatoren.

## Rollout
- T2.4A (erledigt): `ontology/v0_1/` mit Stammbegriffen (Position, Game-Status, Verletzungs-Status); Loader idempotent.
- T2.5: Mapping-Tabelle füllen, sobald Cross-Source-Konflikte real auftreten.

## Implementierungs-Notizen (T2.4A, 2026-04-16)
- Quellformat: **TOML** (statt ursprünglich angenommenem YAML) via stdlib `tomllib`. Begründung: keine zusätzliche Runtime-Abhängigkeit (PyYAML), Python 3.12+ ist ohnehin Pflicht, TOML reicht für die rein deklarative Struktur (Term, Aliases, Value Sets).
- Tabellen in `meta`: `ontology_version`, `ontology_term`, `ontology_alias`, `ontology_value_set`, `ontology_value_set_member`, `ontology_mapping`. Schema in [src/new_nfl/metadata.py](../../src/new_nfl/metadata.py).
- Loader: [src/new_nfl/ontology/loader.py](../../src/new_nfl/ontology/loader.py). Idempotenz über `content_sha256` (sortierter Hash über Dateiname + Inhalt). Wiederholter Load identischer Quelle ist No-Op und liefert dieselbe `ontology_version_id` zurück. Ein neues Quellverzeichnis erzeugt eine zusätzliche Version; `is_active` markiert die jüngste pro `source_dir`.
- Seed-Verzeichnis: [ontology/v0_1/](../../ontology/v0_1) mit `term_position.toml`, `term_game_status.toml`, `term_injury_status.toml` (3 Terms, 8 Aliases, 4 Value Sets, 34 Members).
- CLI: `ontology-load --source-dir ontology/v0_1 [--version-label …] [--no-activate]`, `ontology-list`, `ontology-show --term-key <key|alias>`.
- Service-Surface: `load_ontology_directory`, `list_terms`, `describe_term` (Pydantic-Modelle mit `OntologyTermDetail`).
- `meta.ontology_mapping` ist als Tabelle bereits angelegt, aber in v0_1 noch ungenutzt — Mapping-Erfassung folgt mit T2.5 (echte Cross-Source-Konflikte).
- Kein impliziter Bootstrap-Load: `ontology-load` ist eine bewusste Operator-Aktion. Begründung: Promotion-Pfade in T2.5 sollen explizit eine geprüfte `ontology_version_id` referenzieren.

## Offene Punkte (für spätere Tranchen)
- Migrations-Strategie zwischen Ontologie-Versionen (Mapping `from_value` → `to_value` in `meta.ontology_mapping`) — kommt mit T2.5.
- Kopplung `core.*` → `ontology_version_id` als FK (heute nur logisch, noch nicht erzwungen).
