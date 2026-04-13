# ADR-0026: Ontology-as-Code with Runtime Projection

## Status
Proposed (target: Accepted at end of T2.4A)

## Kontext
NEW NFL braucht eine kanonische Ontologie für Begriffe, Aliases, Mappings, Value Sets und Constraints (Spielerpositionen, Stat-Familien, Verletzungs-Status, Off-Field-Kategorien, Wetter-Variablen). Eine reine Code-Repräsentation ist schwer reviewbar, ein Triple-Store wäre für ein single-operator-System überdimensioniert.

## Entscheidung
Die Ontologie liegt **als Code im Repository** unter `ontology/<version>/*.yaml`. Beim Bootstrap und bei Ontologie-Releases projiziert ein Loader sie deterministisch in `meta.ontology_*`-Tabellen in DuckDB:

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
- T2.4A: `ontology/v0_1/` mit Stammbegriffen (Position, Game-Status, Verletzungs-Status).
- Loader idempotent.

## Offene Punkte
- Format-Detail (YAML vs TOML) — Default YAML.
- Migrations-Strategie zwischen Ontologie-Versionen.
