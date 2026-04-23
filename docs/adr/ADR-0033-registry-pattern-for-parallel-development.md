# ADR-0033: Registry-Pattern für Mart-Builder und CLI-Subcommands — Voraussetzung für parallele Entwicklung

## Status
Accepted (2026-04-23, umgesetzt in T2.7P)

## Kontext

Nach Abschluss von T2.6 hat das Projekt einen Umfang erreicht, der sequenzielle Einzel-Session-Entwicklung teuer macht:

- **14 Mart-Builder** (16 Mart-Tabellen, weil `run_evidence_v1` drei Projektionen in einem Builder bündelt) wurden über einen hardcodierten `if/elif`-Baum in [src/new_nfl/jobs/runner.py](../../src/new_nfl/jobs/runner.py) `_executor_mart_build` (Z. 196–250) dispatcht
- **50+ CLI-Subcommands** in einem monolithischen `build_parser()` in [src/new_nfl/cli.py](../../src/new_nfl/cli.py) (1.461 Zeilen, eine einzelne Funktion)

Diese zwei Stellen sind **Konflikt-Zonen für parallele Arbeit**: jeder neue Mart bzw. jedes neue Subcommand erzwingt einen Edit am _gleichen_ zentralen File. Wenn zwei Feature-Branches gleichzeitig Marts hinzufügen, müssen sie an den gleichen Zeilen mergen — garantierter Merge-Konflikt.

T2.7 ist mit drei parallelen Streams (Observability, Resilience, Hardening) geplant (siehe [docs/PARALLEL_DEVELOPMENT.md](../PARALLEL_DEVELOPMENT.md)). Ohne Umbau an diesen Stellen würde jeder Stream bei jedem Merge an den gleichen Files rebasen. Der Rule-of-Three ist für diese zwei Hubs erfüllt: je ≥10 Einträge, je ein gemeinsames Dispatch-Pattern.

**Scope-Reality-Check im Verlauf von T2.7P:** Der ursprüngliche Draft sah auch eine Web-Route-Registry vor. Die Prüfung im Code zeigte aber: es existiert *kein* HTTP-Router, der `render_*_page`-Funktionen bindet — [src/new_nfl/web/renderer.py](../../src/new_nfl/web/renderer.py) stellt die Render-Funktionen als stateless Library-API bereit, [src/new_nfl/web_server.py](../../src/new_nfl/web_server.py) ist der alte Core-Dictionary-Preview und kennt die Mart-basierte UI gar nicht. Es gibt also keine aktuelle Konflikt-Zone für Web-Routen. Eine Registry zu erfinden, bevor der Router existiert, wäre Design für hypothetische Requirements (Manifest §Don't-over-engineer). Wir verschieben die Entscheidung, bis eine Bolzen-Arbeit einen echten HTTP-Mount landet.

## Entscheidung

Wir führen **zwei Registries** ein:

### 1. Mart-Builder-Registry (umgesetzt)

Datei [src/new_nfl/mart/_registry.py](../../src/new_nfl/mart/_registry.py):

```python
from collections.abc import Callable
from typing import Any
from new_nfl.settings import Settings

type MartBuilder = Callable[[Settings], Any]
_REGISTRY: dict[str, MartBuilder] = {}

def register_mart_builder(mart_key: str) -> Callable[[MartBuilder], MartBuilder]:
    def _decorator(fn: MartBuilder) -> MartBuilder:
        if mart_key in _REGISTRY:
            existing = _REGISTRY[mart_key]
            if existing is fn:
                return fn  # idempotent re-registration under module reload
            raise ValueError(f"duplicate mart_key={mart_key!r}: ...")
        _REGISTRY[mart_key] = fn
        return fn
    return _decorator

def get_mart_builder(mart_key: str) -> MartBuilder: ...
def list_mart_keys() -> list[str]: ...
```

Jedes der 14 Mart-Module dekoriert seinen Top-Level-Builder:

```python
# src/new_nfl/mart/run_evidence.py
from new_nfl.mart._registry import register_mart_builder

@register_mart_builder("run_evidence_v1")
def build_run_evidence_v1(settings: Settings) -> MartRunEvidenceResult: ...
```

`_executor_mart_build` in runner.py ist jetzt eine Drei-Zeiler:

```python
import new_nfl.mart  # noqa: F401  # side-effect: register all mart builders
from new_nfl.mart._registry import get_mart_builder

mart_key = params.get("mart_key", "schedule_field_dictionary_v1")
builder = get_mart_builder(mart_key)
result = builder(settings)
```

`new_nfl.mart.__init__` importiert bereits alle Mart-Module — das triggert die Decorator-Registrierung bei jedem `import new_nfl.mart`.

### 2. CLI-Plugin-Registry (umgesetzt)

Datei [src/new_nfl/cli_plugins.py](../../src/new_nfl/cli_plugins.py):

```python
from collections.abc import Callable
from dataclasses import dataclass
import argparse

RegisterParser = Callable[[argparse._SubParsersAction], argparse.ArgumentParser]
Dispatch = Callable[[argparse.Namespace], int]

@dataclass(frozen=True)
class CliPlugin:
    name: str
    register_parser: RegisterParser
    dispatch: Dispatch

_REGISTRY: dict[str, CliPlugin] = {}

def register_cli_plugin(plugin: CliPlugin) -> CliPlugin: ...
def get_cli_plugin(name: str) -> CliPlugin | None: ...
def list_cli_plugins() -> list[CliPlugin]: ...
def attach_plugins_to_parser(subparsers): ...
```

Plugin-Module leben unter [src/new_nfl/plugins/](../../src/new_nfl/plugins/) und registrieren sich bei Import. `new_nfl/cli.py::build_parser` lädt `new_nfl.plugins` (function-local Import), was alle Plugin-Module durchläuft, und ruft anschließend `attach_plugins_to_parser(sub)`. `main()` fällt bei unbekannten Commands auf `get_cli_plugin(args.command)` zurück, bevor es `parser.error` wirft.

**Wichtige Scope-Abgrenzung:** Die 50+ bestehenden Subcommands bleiben in `build_parser()` / `main()` unverändert — sie *funktionieren* und umzuschreiben wäre reine Energie-in-den-Wind. Streams fügen **neue** Commands nur noch als Plugin hinzu. Altkommandos migrieren lazy, wenn ein Stream eh ein Command in deren Gruppe anfasst. Das ist die "Strangler-Fig"-Strategie statt Big-Bang-Rewrite.

Referenz-Plugin: [src/new_nfl/plugins/registry_inspect.py](../../src/new_nfl/plugins/registry_inspect.py) registriert `new-nfl registry-list` — zeigt dem Operator alle registrierten `mart_key`s aus der Registry. Nützliche Diagnose-API + Beweis dass die Mechanik end-to-end funktioniert.

### 3. Web-Route-Registry (aus Scope zurückgezogen)

Der ursprüngliche Draft enthielt eine dritte Registry für Web-Routen. Bei der Umsetzung stellte sich heraus: es gibt heute keinen HTTP-Router, der `render_*_page`-Funktionen bindet. Die Render-Funktionen sind stateless Library-API; ein Webserver-Mount existiert nur als Legacy-Core-Dictionary-Preview in [src/new_nfl/web_server.py](../../src/new_nfl/web_server.py), der von der Mart-basierten UI nichts weiß.

**Entscheidung:** Web-Route-Registry wird verschoben, bis eine Bolzen-Arbeit (vermutlich T2.6I oder T2.9) einen echten HTTP-Mount landet. Solange nur Template-Funktionen existieren, ist kein Konflikt-Hub vorhanden — wir warten, bis ein echtes Problem entsteht, bevor wir Infrastruktur dagegen bauen.

## Alternativen

### A. Weiter monolithisch, mit Merge-Disziplin
**Verworfen.** Bei drei parallelen Streams mit je mehreren neuen Marts/Commands sind Merge-Konflikte an den Hub-Files unvermeidbar. Manuelle Disziplin skaliert nicht.

### B. Entry-Points via `importlib.metadata`
**Verworfen.** Das Projekt ist nicht als Plugin-Framework gedacht, alle Module leben im gleichen Git-Repo. Entry-Points würden eine Paket-Installation für jede Änderung erzwingen — zu viel Reibung für Single-Operator-Entwicklung.

### C. Auto-Discovery via `pkgutil.iter_modules`
**Verworfen.** Implizites Discovery macht Lint/AST-Checks schwieriger (welche Marts gibt es? Wir wissen es erst zur Laufzeit). Explizite Registry mit `register_mart_builder`-Decorator bleibt grep-bar.

### D. Monolithische cli.py in `cli/`-Package zersplittern
**Verworfen für T2.7P.** Die 1461-Zeilen-Datei auf zwölf Plugin-Module zu zerschneiden wäre ein Großrefactor, der selbst Merge-Konflikte mit laufender Arbeit riskiert. Stattdessen Plugin-Hook *neben* dem Monolithen — neue Commands laufen über die Registry, alte bleiben wo sie sind. Strangler-Fig über Zeit.

## Konsequenzen

**Positive:**
- Parallele Streams können neue Marts (nur Decorator) und neue CLI-Commands (nur Plugin-Modul) hinzufügen, **ohne** runner.py oder cli.py anzufassen
- `list_mart_keys()` gibt introspektions-API für CLI-Help und Operator-Diagnose (`new-nfl registry-list`)
- AST-Lint bleibt gültig: Registry ist eine Python-Datenstruktur, keine Abhängigkeit zum Read-Surface
- Duplicate-Detection ist laut (beide Registries werfen `ValueError` bei doppeltem Key/Name) — verhindert silent-overwrite bei Merge-Fehlern

**Negative:**
- Eine zusätzliche Indirektion: `mart_key → Registry-Lookup → Builder` statt direktem `elif`
- Import-Reihenfolge wird relevanter: `new_nfl.mart.__init__` muss alle Submodule importieren, damit die Decorators feuern. Das war schon vorher so wegen Re-Exports — also kein neues Risiko, aber gutes zu wissen für Maintainer
- Die CLI-Strangler-Fig bedeutet zwei Pfade für Commands (monolithisch + Plugin). Kurzfristig erhöht das die Komplexität der CLI-Datei marginal; langfristig werden Commands in Gruppen migriert, wenn Streams sie eh anfassen

## Umsetzung (T2.7P)

1. ✅ **Mart-Registry angelegt:** `src/new_nfl/mart/_registry.py` mit Decorator, Migration aller 14 Mart-Builder (16 Mart-Tabellen) in einem Commit.
2. ✅ **`_executor_mart_build` vereinfacht:** if/elif-Baum durch zwei-Zeilen-Lookup ersetzt, Regression durch vorhandene Mart-Tests abgesichert.
3. ✅ **CLI-Plugin-Hook angelegt:** `src/new_nfl/cli_plugins.py` + `src/new_nfl/plugins/__init__.py` + Referenz-Plugin `registry_inspect.py`. `cli.py::build_parser` und `main()` kennen Plugins, alte Commands unverändert.
4. ✅ **Smoke-Tests:** `tests/test_registry.py` — 9 Tests decken Decorator-Registrierung, Duplicate-Handling, Plugin-Registrierung und end-to-end-Dispatch ab.
5. ✅ **Ruff + pytest grün** — keine Regression an bestehenden 323 Tests, +9 neue Tests.
6. ⤴ **Web-Route-Registry verschoben** — sauber dokumentiert warum, kein Vorwärtsbau ohne Requirement.

## DoD

- [x] `mart/_registry.py` existiert, alle 14 Mart-Keys (16 Mart-Tabellen) sind per Decorator registriert
- [x] `_executor_mart_build` ist eine zwei-Zeilen-Funktion (Lookup + Call)
- [x] `cli_plugins.py` + sample Plugin `registry_inspect.py` gewired in `cli.py::build_parser` / `main()`
- [x] `tests/test_registry.py` deckt Smoke-Tests ab (9 Tests, alle grün)
- [x] Full-Suite grün (Regression prüft, dass bestehende Tests unverändert bestehen)
- [x] ADR-0033 Status → `Accepted`
- [~] Web-Route-Registry: dokumentiert als verschoben bis HTTP-Mount existiert

## Referenzen

- [docs/PARALLEL_DEVELOPMENT.md](../PARALLEL_DEVELOPMENT.md) — Stream-Definition, Branch-Strategie, Integrations-Protokoll
- [docs/T2_3_PLAN.md](../T2_3_PLAN.md) §6 — T2.7P als Pre-Parallel-Bolzen
- ADR-0031 (Adapter-Slice-Registry) — verwandtes Registry-Pattern für Slices
