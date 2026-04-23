# ADR-0033: Registry-Pattern für Mart-Builder, CLI-Subcommands und Web-Routen — Voraussetzung für parallele Entwicklung

## Status
Proposed (2026-04-23, Treiber: T2.7P Parallelisierungs-Prep vor T2.7-Streams)

## Kontext

Nach Abschluss von T2.6 hat das Projekt einen Umfang erreicht, der sequenzielle Einzel-Session-Entwicklung teuer macht:

- **16 Marts** unter einem Mart-Key in [src/new_nfl/jobs/runner.py](../../src/new_nfl/jobs/runner.py) `_executor_mart_build` (Z. 196–250) als hardcodierter `if/elif`-Baum
- **50+ CLI-Subcommands** in einem monolithischen `build_parser()` in [src/new_nfl/cli.py](../../src/new_nfl/cli.py) (1.461 Zeilen, eine einzelne Funktion)
- **10 `render_*_page`-Entrypoints** in [src/new_nfl/web/renderer.py](../../src/new_nfl/web/renderer.py) plus zugehörige Re-Exports in [src/new_nfl/web/__init__.py](../../src/new_nfl/web/__init__.py) und [src/new_nfl/mart/__init__.py](../../src/new_nfl/mart/__init__.py)

Diese drei Stellen sind **Konflikt-Zonen für parallele Arbeit**: jeder neue Mart / jedes neue Subcommand / jede neue Route erzwingt einen Edit am _gleichen_ zentralen File. Wenn zwei Feature-Branches gleichzeitig Marts hinzufügen, müssen sie an den gleichen Zeilen mergen — garantierter Merge-Konflikt.

T2.7 ist mit drei parallelen Streams (Observability, Resilience, Hardening) geplant (siehe `docs/PARALLEL_DEVELOPMENT.md`). Ohne Umbau an diesen drei Stellen würde jeder Stream täglich Rebase-Konflikte produzieren. Der Rule-of-Three ist erfüllt: wir haben drei unabhängige Hubs (runner, cli, web) mit jeweils 10+ Einträgen, die ein gemeinsames Registry-Pattern vertragen.

## Entscheidung

Wir führen **drei Registries** ein, alle mit dem gleichen Pattern:

### 1. Mart-Builder-Registry

```python
# src/new_nfl/mart/_registry.py
from collections.abc import Callable
from typing import Any, TypeAlias

MartBuilder: TypeAlias = Callable[[Any], Any]  # (settings) -> MartResult
_REGISTRY: dict[str, MartBuilder] = {}

def register_mart_builder(mart_key: str) -> Callable[[MartBuilder], MartBuilder]:
    def _decorator(fn: MartBuilder) -> MartBuilder:
        if mart_key in _REGISTRY:
            raise ValueError(f"duplicate mart_key: {mart_key}")
        _REGISTRY[mart_key] = fn
        return fn
    return _decorator

def get_mart_builder(mart_key: str) -> MartBuilder:
    if mart_key not in _REGISTRY:
        raise ValueError(f"unknown mart_key: {mart_key}")
    return _REGISTRY[mart_key]

def list_mart_keys() -> list[str]:
    return sorted(_REGISTRY.keys())
```

Jedes Mart-Modul dekoriert seinen Top-Level-Builder:

```python
# src/new_nfl/mart/run_evidence.py
from new_nfl.mart._registry import register_mart_builder

@register_mart_builder("run_evidence_v1")
def build_run_evidence_v1(settings: Settings) -> MartRunEvidenceResult:
    ...
```

`_executor_mart_build` in runner.py reduziert sich auf:

```python
from new_nfl.mart._registry import get_mart_builder

def _executor_mart_build(settings, params):
    mart_key = params["mart_key"]
    builder = get_mart_builder(mart_key)
    return builder(settings)
```

`mart/__init__.py` importiert alle Mart-Module (das triggert die Decorator-Registrierung) — der Rest der 16-elif-Kaskade fällt weg.

### 2. CLI-Subcommand-Plugin-Registry

```python
# src/new_nfl/cli/_plugins.py
from collections.abc import Callable
from argparse import _SubParsersAction

CliPlugin: TypeAlias = Callable[[_SubParsersAction], None]
_PLUGINS: list[CliPlugin] = []

def register_cli_plugin(fn: CliPlugin) -> CliPlugin:
    _PLUGINS.append(fn)
    return fn

def install_plugins(subparsers: _SubParsersAction) -> None:
    for plugin in _PLUGINS:
        plugin(subparsers)
```

Jedes Domain-Modul registriert seine Subcommands in einem eigenen Plugin-Modul:

```python
# src/new_nfl/cli/plugins/mart.py
from new_nfl.cli._plugins import register_cli_plugin

@register_cli_plugin
def register(subparsers):
    p = subparsers.add_parser("mart-rebuild", help="Rebuild a mart projection")
    p.add_argument("--mart-key", default="schedule_field_dictionary_v1")
    p.set_defaults(command="mart-rebuild", handler=_handle_mart_rebuild)
```

`build_parser()` in cli.py ruft `install_plugins(subparsers)` statt alle Subcommands selbst zu definieren. Migration schrittweise — erstmal bestehende Commands in Plugin-Gruppen sortieren, dann alte Definitionen löschen.

### 3. Web-Route-Registry

```python
# src/new_nfl/web/_routes.py
@dataclass(frozen=True)
class WebRoute:
    name: str              # z.B. "runs", "runs_detail"
    path: str              # z.B. "/runs", "/runs/<job_run_id>"
    handler: Callable      # die render_*_page-Funktion
    active_nav: str        # z.B. "runs"

_ROUTES: list[WebRoute] = []

def register_route(route: WebRoute) -> None:
    _ROUTES.append(route)

def list_routes() -> list[WebRoute]:
    return list(_ROUTES)
```

Jedes View-Modul registriert sich in seinem `__init__.py`-Level-Aufruf. `web/renderer.py` behält die `render_*_page`-Funktionen als öffentliche Entrypoints (Tests rufen sie direkt), aber die Route-Table wird aus der Registry gelesen — kein hardcodierter Dispatch mehr in `web_server.py`.

## Alternativen

### A. Weiter monolithisch, mit Merge-Disziplin
**Verworfen.** Bei drei parallelen Streams mit je ~5 neuen Marts/Commands/Views sind Merge-Konflikte an den Hub-Files unvermeidbar. Manuelle Disziplin ("nicht gleichzeitig Mart-Keys hinzufügen") skaliert nicht.

### B. Entry-Points via `importlib.metadata`
**Verworfen.** Das Projekt ist nicht als Plugin-Framework gedacht, alle Module leben im gleichen Git-Repo. Entry-Points würden eine Paket-Installation für jede Änderung erzwingen — zu viel Reibung für Single-Operator-Entwicklung.

### C. Auto-Discovery via `pkgutil.iter_modules`
**Verworfen.** Implizites Discovery macht Lint/AST-Checks schwieriger (welche Marts gibt es? Wir wissen es erst zur Laufzeit). Explizite Registry mit `register_mart_builder`-Decorator bleibt grep-bar.

### D. Nur Mart-Registry, CLI und Web-Routen lassen
**Verworfen.** Dann bleiben cli.py und web_server.py Konflikt-Zonen. Wenn wir den Refactor machen, dann für alle drei Hubs — die Arbeit pro Hub ist gering (je ~50 Zeilen neue Registry-Infrastruktur plus schrittweise Migration der Einträge).

## Konsequenzen

**Positive:**
- Parallele Streams können neue Marts/Commands/Views hinzufügen, ohne zentrale Files zu editieren
- Neue Domänen (z.B. zukünftige T3.x-Analysen) sind vollständig additiv — eine neue Datei, ein Decorator, fertig
- `list_mart_keys()` als introspektions-API für CLI-Help (`mart-rebuild --list` zeigt alle verfügbaren Keys)
- AST-Lint bleibt gültig: die Registry ist eine Python-Datenstruktur, keine Abhängigkeit zum Read-Surface

**Negative:**
- Eine zusätzliche Indirektion — `mart_key → Registry-Lookup → Builder` statt `mart_key → elif → Builder`
- Import-Reihenfolge wird relevanter: `mart/__init__.py` muss alle Submodule importieren, damit die Decorators feuern, bevor irgendein Runner aufgerufen wird (mitigiert durch konsequentes `from new_nfl.mart import ...` im Top-Level)
- Bestehende Tests, die `_executor_mart_build` direkt testen, brauchen keinen Change (das ist der ganze Witz des Refactors — die öffentliche API bleibt stabil)
- Migration ist schrittweise: T2.7P migriert nur die Infrastruktur + 1-2 Beispiele; die volle Migration der 16 Marts und 50+ Commands kann über T2.7A-E laufen (jedes Feature migriert seine neuen Einträge sofort über Registry, alte Einträge folgen bei Bedarf)

## Migrations-Plan (T2.7P-Bolzen)

1. **Mart-Registry anlegen:** `src/new_nfl/mart/_registry.py` mit Decorator, Migration **aller 16** Mart-Builder auf Decorator in einem Commit (weil `_executor_mart_build` nur gewechselt werden kann, wenn alle Keys in der Registry sind).
2. **CLI-Plugin-Registry anlegen:** `src/new_nfl/cli/_plugins.py` plus `src/new_nfl/cli/plugins/` Unterordner. Migration der Subcommands kann schrittweise pro Domain-Gruppe erfolgen — T2.7P migriert exemplarisch die Mart-Gruppe und die Job-Gruppe, T2.7A-E migrieren ihre neuen Commands direkt über die Registry.
3. **Web-Route-Registry anlegen:** `src/new_nfl/web/_routes.py`. Migration aller 10 bestehenden Routes + aller `render_*_page`-Aufrufer in einem Commit.
4. **Smoke-Tests:** `tests/test_registry.py` prüft, dass nach Import der Top-Level-Pakete alle erwarteten Keys/Routes/Plugins registriert sind. Das ist ein Regressions-Safety-Net.
5. **Ruff + pytest grün** nach jedem Teilschritt.

## DoD

- [ ] `mart/_registry.py` existiert, alle 16 Marts sind per Decorator registriert
- [ ] `_executor_mart_build` ist eine zwei-Zeilen-Funktion (Lookup + Call)
- [ ] `cli/_plugins.py` + mindestens zwei Plugin-Gruppen migriert (Mart + Jobs)
- [ ] `web/_routes.py` existiert, alle 10 Routes registriert
- [ ] `tests/test_registry.py` deckt Smoke-Tests ab
- [ ] Full-Suite grün (Regression prüft, dass bestehende Tests unverändert bestehen)
- [ ] ADR-0033 Status → `Accepted`

## Referenzen

- [docs/PARALLEL_DEVELOPMENT.md](../PARALLEL_DEVELOPMENT.md) — Stream-Definition, Branch-Strategie, Integrations-Protokoll
- [docs/T2_3_PLAN.md](../T2_3_PLAN.md) §6 — T2.7P als Pre-Parallel-Bolzen
- ADR-0031 (Adapter-Slice-Registry) — verwandtes Registry-Pattern für Slices
