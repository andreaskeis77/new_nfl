# Chat-Handoff 2026-04-23 23:50 — T2.7P Registry-Pattern abgeschlossen, parallel-ready

## Trigger

§2.1 „Tranche-Abschluss + thematischer Wechsel zwischen Substreams": **T2.7P abgeschlossen**. Das Projekt hat ab jetzt einen Decorator-Registry-Extensionpunkt für alle 14 Mart-Builder und einen CLI-Plugin-Hook — die drei parallelen T2.7-Streams (A Observability, B Resilience, C Hardening) können ab dem neuen `main`-HEAD in getrennten Claude-Code-Sessions additiv arbeiten, ohne an `jobs/runner.py::_executor_mart_build` oder `cli.py::build_parser()` zu mergen. Nächste Session ist eine von drei parallelen Stream-Sessions.

Zusätzlich §2.1 „Kontext-Druck": Diese Session hat ADR-0033-Entwurf → Decorator-Infrastruktur → 14 Builder dekoriert → CLI-Plugin-Hook → Smoke-Tests → Full-Suite → Doku + Lessons in einem autonomen Zug ausgeführt. Vor den Stream-Sessions ist ein sauberer Cut sinnvoll, weil jede Stream-Session eine eigene Session-Identität + Branch braucht.

## Was wurde in dieser Session erreicht

### T2.7P — Registry-Pattern (Commit wird im Anschluss gesetzt)

**Mart-Builder-Registry** ([src/new_nfl/mart/_registry.py](../../src/new_nfl/mart/_registry.py)):
- `@register_mart_builder("<mart_key>")`-Decorator mit `_REGISTRY: dict[str, MartBuilder]`.
- `type MartBuilder = Callable[[Settings], Any]` (PEP 695, Python 3.12-Baseline).
- Duplicate-Registrierung wirft `ValueError` (verhindert stilles Shadow bei parallelen Streams); idempotente Self-Re-Registrierung (gleiches Funktions-Objekt → No-Op) schützt gegen Test-Harness-Reloads.
- `get_mart_builder(mart_key)` raises `ValueError` mit sortierter Liste bekannter Keys.
- `list_mart_keys()` für Introspektion.

**14 Mart-Builder dekoriert** — alle Builder-Module unter [src/new_nfl/mart/](../../src/new_nfl/mart/) tragen `@register_mart_builder("<key>")`:
- `freshness_overview_v1`, `game_overview_v1`, `player_overview_v1`
- `player_stats_career_v1`, `player_stats_season_v1`, `player_stats_weekly_v1`
- `provenance_v1`, `roster_current_v1`, `roster_history_v1`
- `run_evidence_v1` (der Builder produziert drei Mart-Tabellen `run_overview_v1`/`run_event_v1`/`run_artifact_v1` unter einem Key — T2.6H-Pattern bleibt erhalten)
- `schedule_field_dictionary_v1`, `team_overview_v1`, `team_stats_season_v1`, `team_stats_weekly_v1`.

**Runner-Dispatch vereinfacht** ([src/new_nfl/jobs/runner.py](../../src/new_nfl/jobs/runner.py)):
- `_executor_mart_build` von ~55-Zeilen-if/elif auf 3-Zeilen-Registry-Lookup reduziert:
  ```python
  import new_nfl.mart  # side-effect: register all mart builders
  from new_nfl.mart._registry import get_mart_builder
  builder = get_mart_builder(mart_key)
  result = builder(settings)
  ```
- Der Side-Effect-Import `import new_nfl.mart` triggert `new_nfl/mart/__init__.py`, das alle Builder-Module importiert, wodurch die Decorators beim ersten Dispatch-Call feuern.

**CLI-Plugin-Hook** ([src/new_nfl/cli_plugins.py](../../src/new_nfl/cli_plugins.py)):
- `CliPlugin`-Dataclass (`name`, `register_parser: (subparsers) -> ArgumentParser`, `dispatch: (Namespace) -> int`).
- `register_cli_plugin(plugin)` mit Duplicate-Detection + idempotentem Self-Re-Register (gleiche Instance → No-Op).
- `get_cli_plugin(name)` / `list_cli_plugins()` für Lookup + `--help`-stabile Sortierung.
- `attach_plugins_to_parser(subparsers)` ruft alle Plugins' `register_parser` auf.

**Plugin-Namespace + Referenz-Plugin** ([src/new_nfl/plugins/](../../src/new_nfl/plugins/)):
- `__init__.py` importiert alle Plugin-Module (Side-Effect registriert sie).
- [src/new_nfl/plugins/registry_inspect.py](../../src/new_nfl/plugins/registry_inspect.py) bindet `new-nfl registry-list --kind mart` und druckt `MART_KEY_COUNT=N` plus die sortierte Key-Liste.

**CLI-Integration** ([src/new_nfl/cli.py](../../src/new_nfl/cli.py), vier surgical Edits):
- Import `from new_nfl.cli_plugins import attach_plugins_to_parser, get_cli_plugin` ergänzt.
- Function-local `import new_nfl.plugins` in `build_parser()` triggert Plugin-Registrierung beim ersten Call.
- `attach_plugins_to_parser(sub)` am Ende von `build_parser()` nach den built-in-Subparsern.
- `main()` dispatcht `get_cli_plugin(args.command)` vor `parser.error('Unknown command')`.

**Strangler-Fig-Migration:** Die 1461-zeilige monolithische `cli.py` bleibt strukturell unverändert. Neue Subcommands gehen über die Plugin-Registry, die bestehenden 50+ bleiben im Monolith. Big-Bang-Rewrite wäre gegen das Ziel „parallel-arbeitsfähig" ein Rückschritt gewesen.

**Scope-Reality-Check — Web-Routen-Registry deferred:** Die ursprüngliche ADR-0033 listete eine dritte Registry für „alle 10 Web-Routen" auf. Bei der Umsetzung zeigte ein Grep, dass `web_server.py` eine legacy Core-Dictionary-Preview ist und die `web/render_*_page`-Funktionen pure Library-API ohne HTTP-Mount sind — es existiert schlicht kein Router. Die Web-Routen-Registry wurde in ADR-0033 als explizites Deferral dokumentiert (wird beim nächsten echten Router-Landing nachgeholt).

### Tests

- **9 neue Registry-Smoke-Tests** in [tests/test_registry.py](../../tests/test_registry.py):
  - `test_mart_registry_lists_every_known_key` — frozenset-Vergleich aller 14 erwarteten Keys
  - `test_mart_registry_get_unknown_key_raises`
  - `test_mart_registry_duplicate_registration_raises`
  - `test_mart_registry_idempotent_self_reregistration`
  - `test_cli_plugin_registry_lists_bundled_plugin`
  - `test_cli_plugin_registry_duplicate_name_raises`
  - `test_cli_plugin_registry_idempotent_self_reregistration`
  - `test_cli_build_parser_attaches_plugin_subcommand` — argparse-Round-Trip
  - `test_cli_plugin_dispatch_prints_registered_mart_keys` — end-to-end-dispatch mit stdout-Capture
- **Full-Suite 332/332 grün** (323 Baseline + 9 neu, 656.48s / 0:10:56 via Background-Task).
- Ruff sauber auf allen T2.7P-scope Files.

### Doku

- [docs/adr/ADR-0033-registry-pattern-for-parallel-development.md](../adr/ADR-0033-registry-pattern-for-parallel-development.md) — Status → `Accepted (2026-04-23)`, Scope auf tatsächlich geliefertes reduziert (14 Builder + CLI-Plugin-Hook), Web-Router-Deferral dokumentiert.
- [docs/adr/README.md](../adr/README.md) — ADR-0033-Row → `Accepted (2026-04-23)`.
- [docs/PROJECT_STATE.md](../PROJECT_STATE.md) — Phase-Header T2.7P abgeschlossen; Completed-Entry für T2.7P; Runtime-Posture-Eintrag „Registry-Pattern für Parallel-Entwicklung".
- [docs/T2_3_PLAN.md](../T2_3_PLAN.md) §6 — T2.7P-Block auf „abgeschlossen (2026-04-23)" mit Umgesetzter-Scope + tatsächlicher Deferral-Begründung; ADR-Block-Tabelle aktualisiert.
- [docs/LESSONS_LEARNED.md](../LESSONS_LEARNED.md) — T2.7P-Draft oben ergänzt (Scope-Reality-Check, Strangler-Fig, Ruff-vor-pytest, `collections.abc.Callable`).

## Aktueller Arbeitsstand

- **Phase:** T2.7P abgeschlossen, Übergang zu T2.7A/B/C (drei parallele Streams in getrennten Sessions).
- **Letzter erfolgreicher Pflichtpfad:** `pytest` 332/332 grün (Full-Suite-Laufzeit ~10:56).
- **Letzter Commit:** wird im Anschluss an diese Doku gesetzt.
- **Nächster konkreter Schritt:** drei Feature-Branches vom neuen `main`-HEAD anlegen (`feature/t27-observability`, `feature/t27-resilience`, `feature/t27-hardening`), dann **T2.7A — Health-Endpunkte** in einer neuen Claude-Code-Session auf `feature/t27-observability` starten.
- **Git-Status:** wird nach Commit/Push sauber sein, 332 Tests grün, alle Änderungen auf `origin/main`.

## Was ist offen / unklar / Risiko

### Direkt für T2.7A (Observability) — siehe [PARALLEL_DEVELOPMENT.md §4](../PARALLEL_DEVELOPMENT.md)

- **Plugin-Host für neue CLI-Subcommands:** Health-Commands sollen über den T2.7P-Plugin-Hook registriert werden. Template-Beispiel: [src/new_nfl/plugins/registry_inspect.py](../../src/new_nfl/plugins/registry_inspect.py). Scope-Beschränkung: Stream A berührt `src/new_nfl/observability/` (neuer Namespace) + `src/new_nfl/plugins/health.py` + Tests, keine Edits an bestehenden Domain-Modulen.
- **Healthz-Endpunkt-Pfad-Konvention:** `/livez`+`/readyz` (Kubernetes-Style) vs. `/health/*` (Namespace). T2_3_PLAN §6 listet beide — Operator-Entscheidung empfohlen vor T2.7A-Start.
- **Run-Event-Retention vor `/readyz`:** offen seit T2.6H. Zwei Optionen: (a) `readyz` liest nur Overview-Mart, (b) Retention via T2.7E-1 `trim-run-events --older-than 30d`. Die Stream-Trennung lässt beide zu — (a) kommt in T2.7A, (b) in T2.7E.

### Direkt für T2.7B (Resilience)

- **Backup-Target-Format:** ZIP mit DuckDB-File + `data/raw/`. Deterministisch (gleiche Input-Daten → gleicher Payload-Hash) ist Pflicht für Verify. Scope-Beschränkung: `src/new_nfl/resilience/`.
- **Replay-Drill-Diff-Tool:** `diff_tables(db_a, db_b, table, key_cols, exclude_cols=['_canonicalized_at', '_loaded_at'])` — die Exklusionen sind nicht verhandelbar; sonst liefert jeder Replay-Diff false-positives.

### Direkt für T2.7C (Hardening-Backlog, 5 Punkte)

- T2.7E-1 Event-Retention · T2.7E-2 Schema-DESCRIBE-Cache · T2.7E-3 Ontology-Auto-Aktivierung · T2.7E-4 `meta.adapter_slice`-Runtime-Projektion · T2.7E-5 `dedupe-review-resolve`.
- Schema-Cache-Integration berührt ~10 Marts — erlaubt, weil andere Streams dort nicht schreiben.

### T2.7F (Integrations-Session nach allen drei Streams)

- Merge-Reihenfolge A→B→C nach Risiko aufsteigend.
- Konflikt-Erwartung: null oder minimal (Registry-Files append-only, Stream-Scope disjunkt).
- ADR-0030 auf `Accepted`, ADR-0032 auf Operator-Validation-Check, ADR-0033 bleibt `Accepted`.

### Backlog, nicht-blockierend

- **Web-Router-Registry** (ADR-0033-Deferral): nachzuholen, sobald ein echter HTTP-Router landet (frühestens T2.6I falls doch nachgezogen, sonst T2.9).
- **Ontology-Auto-Aktivierung** (T2.7E-3): `position_is_known` in `mart.player_overview_v1` ist NULL-wertig auf fresh DB.
- **`_ensure_metadata_tables` im Builder ist schreibend** (T2.6H-Lesson): ok für Cold-Start, aber die Idempotenz-Logik liegt jetzt im Builder, nicht im `bootstrap_local_environment`. Bei späterer Bootstrap-Verschärfung nachziehen.

## Referenzen für die nächste Session

- [ADR-0033](../adr/ADR-0033-registry-pattern-for-parallel-development.md) — Registry-Pattern als verbindliche Entscheidungsbasis.
- [PARALLEL_DEVELOPMENT.md](../PARALLEL_DEVELOPMENT.md) — Stream-Architektur, Branch-Strategie, Master-Prompts für A/B/C.
- [tests/test_registry.py](../../tests/test_registry.py) — Smoke-Tests als Template für Stream-Registry-Tests.
- [src/new_nfl/plugins/registry_inspect.py](../../src/new_nfl/plugins/registry_inspect.py) — Referenz-Plugin für neue CLI-Commands.
- [src/new_nfl/mart/_registry.py](../../src/new_nfl/mart/_registry.py) — Decorator-Registry-Template für zukünftige additive Domänen.
