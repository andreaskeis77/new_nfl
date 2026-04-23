# Lessons Learned — T2.7A + T2.7B (Stream A: Observability)

**Branch:** `feature/t27-observability`
**Commits auf Origin:**
- `9507cc7` — T2.7A: health-probe CLI plugin + JSON envelope
- `ed6b5d5` — T2.7B: structured JSON logger + runner executor hooks

**Datum Abschluss:** 2026-04-23
**Operator:** Andreas (Single-Operator-Modus)

---

## 1. Scope & Ergebnis

### T2.7A — Health-Endpoints (CLI-first)

Neues CLI-Kommando `new-nfl health-probe --kind <live|ready|freshness|deps>` mit
kanonischem JSON-Envelope:

```json
{
  "schema_version": "1.0",
  "checked_at": "<ISO-8601 UTC>",
  "status": "ok" | "warn" | "fail",
  "details": { ... kind-spezifisch ... }
}
```

Exit-Codes: `0` = ok, `1` = warn, `2` = fail (shell-friendly für Monitoring-Scripte).

| Kind | Semantik |
|---|---|
| `live` | Prozess-Signal, ohne DB. Liefert `{pid}` und immer `ok`. |
| `ready` | DB connect + `mart.freshness_overview_v1` vorhanden? |
| `freshness` | JSON-Spiegel von `build_home_overview()` — ADR-0029 Read-only-Mart. |
| `deps` | Pro Primary-Slice letzte `meta.load_events`-Zeit. |

**Design-Pfeiler:**
- **ADR-0029** (Read-Model-Separation): `freshness` liest ausschließlich `mart.*`,
  niemals `core.*` / `stg.*`.
- **ADR-0033** (Registry-Pattern): Neues CLI-Kommando via
  `register_cli_plugin(CliPlugin(...))` in `src/new_nfl/plugins/health.py` —
  kein Eingriff in den 50+-Befehle-Monolithen `cli.py`.

**Aggregations-Policy `freshness`:** Severity-Ladder
`ok=0 < stale=1 < warn=2 < fail=3`, schlimmster Row gewinnt, `stale` kollabiert
zu `warn`. So bekommt der Operator aus dem Synthetic-Stale-Fallback
(Bootstrap ohne Mart) ein einheitliches `warn` statt `ok`.

### T2.7B — Structured Logging

Neuer JSON-Line-Logger `new_nfl.observability.logging.get_logger(settings)` mit
Pflicht-Envelope:

```json
{
  "event_id": "<uuid4>",
  "ts": "<ISO-8601 UTC ms>",
  "level": "DEBUG" | "INFO" | "WARN" | "ERROR",
  "msg": "<kurze Zusammenfassung>",
  "details": { ... }
}
```

Optionale Kontext-Felder `adapter_id`, `source_file_id`, `job_run_id` — genau die
drei Achsen, über die die bestehende `mart.run_evidence_v1` Log-Events an
Job/Ingest-Runs joint.

**Konfiguration nur über `Settings`-Properties (kein Struktur-Change am
frozen dataclass):**
- `NEW_NFL_LOG_LEVEL` (default `INFO`)
- `NEW_NFL_LOG_DESTINATION` (`stdout` | `file:<dir>`)

**`file:`-Destination** schreibt `<dir>/events_YYYYMMDD.jsonl` (UTC-Tag) und
legt das Verzeichnis lazy beim ersten Event an.

**Runner-Hooks:** In jedem der vier `_executor_*` (fetch_remote, stage_load,
custom, mart_build) wird genau ein `executor_start`- und ein
`executor_complete`-Event emittiert — 2 Log-Aufrufe pro Executor, je nach
Signatur mit `adapter_id` / `source_file_id`. Die Aufrufe sind unter dem
aktuellen Settings konstruiert (`get_logger(settings).event(...)`), d.h. bei
`log_level=WARN` fallen sie kostenlos durch die Severity-Gate.

### Phase 2 (HTTP-Mirror) — bewusst deferred

Master-Prompt erlaubt optionalen HTTP-Endpoint `/health/<kind>`. Per ADR-0033
wird das zurückgestellt, bis ein echter Web-Router landet — aktuell ist
`web_server.py` ein Preview-Singleton ohne Router-Abstraktion, und ein
Ad-hoc-Endpoint wäre Tech-Debt ohne Nutzen gegenüber dem CLI-Plugin.

---

## 2. Was funktioniert hat

### Registry-Pattern als Parallelisierungsinterface

Die ADR-0033-Verkabelung `CliPlugin` + `register_cli_plugin` hat in der Praxis
genau die versprochene Isolation geliefert: Stream A's CLI-Surface wird durch
den Import von `new_nfl.plugins.health` in `plugins/__init__.py` aktiviert —
eine additive Zeile, kein Eingriff in den Legacy-Monolithen. Stream B und C
konnten ihre eigenen Plugins daneben registrieren, ohne je denselben Code zu
berühren. Parallelentwicklung funktioniert — wenn die Streams sich an
Registries halten.

### `get_logger(settings)` pro Call statt Modul-Globals

Der Logger wird pro Executor-Aufruf aus `settings` gebaut. Das klingt nach
Overhead, ist aber bewusst: `settings` ist ein frozen dataclass, `get_logger`
liest zwei `@property`-Werte, und `sys.stdout` wird bei jedem `_write` neu
aufgelöst — damit greifen `contextlib.redirect_stdout` und pytest-Capture ohne
Monkey-Patching. Erste Tests haben die naive Variante (gecachtes
`sys.stdout`-Ref) entlarvt, als `capfd` und `redirect_stdout` ins Leere
schrieben.

### Tests als Dokumentation des Happy/Warn/Fail-Pfads

`test_health.py` enthält 16 Tests, die jeden der vier Probe-Kinds durch Cold-,
Warn- und Happy-Pfad schleifen. Das war zu Beginn nicht geplant, stellte
sich aber beim Schreiben des `freshness`-Probes als unverzichtbar heraus: der
Synthetic-Stale-Fallback produziert `warn` aus einer leeren DB heraus, und ohne
Test gegen diesen Pfad hätte ich den Fall übersehen, dass eine frische
Installation "alles grün" meldet, obwohl kein einziger Mart existiert.

### Stream-A-Scope diszipliniert einhalten

Keine Zeile in `cli.py`, `bootstrap.py`, `runner.py`-Kernlogik oder Migrationen
berührt — außer dem einen Import + 8 Log-Aufrufen in `runner.py`. Die
Master-Prompt-Regel "≤2 Log-Zeilen pro Executor" wurde als logische Einheit
(ein `event()`-Call, multi-line formatiert) interpretiert; das hält
`runner.py`-Diff bei 52 Zeilen und bricht keine Pre-Existing-Ruff-Regel.

---

## 3. Was nicht funktioniert hat

### Parallele Streams im gleichen Working-Directory

**Das kritischste Problem dieser Session.** Streams A, B und C laufen laut
Plan in isolierten Worktrees. De facto teilen sie sich `c:\projekte\newnfl\`.
Konsequenzen während der Session:

- `src/new_nfl/plugins/__init__.py` wurde mehrfach extern überschrieben (mal
  mit Stream-C's `hardening`-Import, mal mit nur `registry_inspect`) —
  jedes Mal, wenn ich meine `health`-Registrierung wieder eingefügt hatte,
  verschwand sie Minuten später.
- **Branch-Flips unter den Füßen:** Nach einem `git add` + `git commit` auf
  `feature/t27-observability` landete der Commit (zweimal!) auf
  `feature/t27-resilience` — der externe Prozess hatte zwischen meinen
  Commands `git checkout` ausgeführt.
- `src/new_nfl/bootstrap.py` bekam Stream-C's Ontology-Auto-Activate-Block
  hinzu-editiert, während ich auf Stream-A-Branch arbeitete.

### Recovery-Pattern, das sich bewährt hat

Weil die Umgebung unter mir atmet, wurden folgende Tricks nötig:

1. **Nach jeder Änderung sofort `git add` + `git commit`.** Jede Sekunde
   Wartezeit ist eine Einladung zur Contamination.
2. **Tag als Bookmark:** `git tag -f __t27a_commit <sha>` nach jedem Commit,
   damit der SHA beim nächsten Branch-Flip nicht verloren geht.
3. **Push direkt per SHA:** `git push origin <sha>:refs/heads/feature/t27-observability`
   umgeht die Branch-Flip-Problematik komplett — egal auf welcher lokalen
   Branch ich gerade lande, der Commit-SHA ist stabil.
4. **`git update-ref` statt `reset --hard`:** bewegt nur den Branch-Pointer,
   rührt die Working-Tree nicht an (wichtig, um Stream B/C keine
   uncommitteten Änderungen zu zerstören).
5. **Nie `-u` beim ersten Push, immer explizit per refspec.** Verhindert,
   dass der lokale Tracking-Status falsch gesetzt wird, wenn Branches sich
   extern verschieben.

### Ruff-Grenzen bei Single-line-Log-Calls

Der erste Anlauf, `get_logger(settings).event("INFO", ...)` einzeilig zu
schreiben, riss 166-Zeichen-Lines. Multi-line-Formatting war kein Schönheits-
sondern ein Ruff-Zwang (E501 @ 100). Die "≤2 Zeilen pro Executor"-Regel aus
dem Master-Prompt wurde daher als "zwei logische Aufrufe, formatiert nach
Ruff" gelesen.

### Tests gegen `monkeypatch.setenv` + `load_settings()` sind stateless

Das T2.7A-Pattern `_bootstrap(tmp_path, monkeypatch)` funktioniert 1:1 für
T2.7B — `NEW_NFL_LOG_LEVEL` und `NEW_NFL_LOG_DESTINATION` werden pro Test
isoliert gesetzt, `load_settings()` liest sie frisch. Keine
Logger-Re-Initialization zwischen Tests nötig, weil der Logger selbst
pro-Call gebaut wird.

---

## 4. Regressionslage

**Full-Suite (Stream-A-only, ohne Stream-B/C-Dateien):** 344 Tests collected,
alle grün. Baseline (vor T2.7A) = 316 Tests. Delta:
- T2.7A test_health.py: +16 Tests
- T2.7B test_logging.py: +12 Tests

**Quality-Gates:**
- Ruff auf allen Stream-A-Dateien: clean (pre-existing UP035/UP037 in
  `runner.py` nicht von mir eingeführt, Baseline hat 45 Ruff-Errors projektweit).
- Kein neuer Import in `cli.py`, kein Schema-Change, keine Migrationen.
- `Settings`-Dataclass strukturell unverändert (zwei neue `@property`s).

---

## 5. Offene Punkte für Folge-Streams

### Für den Merge-Koordinator (Stream F oder Final-Handoff)

1. **`plugins/__init__.py` wird zum Merge-Konfliktpunkt.** Jeder Stream will
   dort seine eine Import-Zeile. Das ist eigentlich der einzige realistische
   Konflikt — linearer Diff, trivial zu resolven. Empfehlung: als letzten
   Schritt des Merges von allen drei Streams die Imports zusammenführen.
2. **`runner.py`-Import `from new_nfl.observability.logging import get_logger`**
   muss nur von Stream A landen; Stream B/C hatten keinen Anlass, runner.py
   zu patchen.
3. **`settings.py` `log_level` / `log_destination` Properties** sind
   kollisionsfrei — Stream C's `schema_cache_ttl_seconds` liegt sauber
   dahinter, kein Diff-Konflikt zu erwarten.

### Optionales Follow-up (Post-v1.0)

- HTTP-Mirror `/health/<kind>` erst wenn ein echter Web-Router-Refactor
  ansteht (Anthony-Port von `web_server.py` → fastapi/flask-dispatch).
- Log-Rotation / Retention für `file:`-Destination: aktuell läuft
  `events_YYYYMMDD.jsonl` unbegrenzt, Cleanup per Stream-C-Retention-CLI
  (`trim-run-events`) als Analogie denkbar.
- `job_run_id`-Kontext in den Runner-Executor-Hooks: aktuell nicht gesetzt,
  weil der `job_run_id` im Executor-Body nicht direkt verfügbar ist.
  Follow-up: Executor-Signatur um `job_run_id: str | None = None` erweitern,
  dann durch Logger threaden — kostenneutral für den Call-Path.

---

## 6. Verwendete Referenzen

- **ADR-0029** Read-Model-Separation (UI/API lesen nur `mart.*`)
- **ADR-0033** Registry-Pattern für Parallel-Streams (Accepted 2026-04-23)
- **Engineering Manifest v1.3 §3.9** (Replay-Pflicht) / **§3.13** (Autonomie
  mit Sichtbarkeit)
- `src/new_nfl/mart/freshness_overview.py` — Mart-Builder, den `freshness`
  implizit testet
- `src/new_nfl/adapters/slices.py` `SLICE_REGISTRY` — Quelle für `deps`-Probe

---

*Ende Lessons-Draft T2.7A+B.*
