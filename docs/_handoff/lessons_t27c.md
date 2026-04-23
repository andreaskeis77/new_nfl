# Lessons Learned — T2.7C Stream-C Hardening

**Datum:** 2026-04-23
**Stream:** C (Hardening)
**Branch:** `feature/t27-hardening` (merge-ready)
**Basis-Commit:** `86bf8a2` (T2.7P Registry-Pattern)
**Status:** draft — Operator-Review ausstehend

## 1. Umfang (ausgeliefert)

Sechs Commits auf `origin/feature/t27-hardening`, jeweils ruff-clean und mit
eigenem Test-Set grün:

| Commit    | Slice    | Kernlieferung                                                                                       |
| --------- | -------- | --------------------------------------------------------------------------------------------------- |
| `9b11bfa` | T2.7E-1  | `new-nfl trim-run-events --older-than 30d [--dry-run]` + `meta.retention` Backend                    |
| `910fdf3` | T2.7E-2a | `new_nfl.meta.schema_cache` (TTL-Cache über `id(settings)`, `.describe() / .column_names()`)        |
| `3e84562` | T2.7E-2b | 9 Mart-Module von Direkt-DESCRIBE auf `schema_cache.describe()` umgestellt (bit-identische Logik)    |
| `7c20c69` | T2.7E-3  | `bootstrap_local_environment` lädt `ontology/v0_1` automatisch; `NEW_NFL_SKIP_ONTOLOGY_AUTOLOAD=1`   |
| `5b1b9eb` | T2.7E-4  | `meta.adapter_slice` Runtime-Projektion von `SLICE_REGISTRY` + CLI `adapter-slice-sync`              |
| `a742bf2` | T2.7E-5  | `new-nfl dedupe-review-resolve --review-id … --action {merge,reject,defer}` + `review.resolve_…`    |

Pro Commit liegen Unit-Tests bei (Retention 16, Schema-Cache 11, Ontology-Auto
6, Adapter-Slice 6, Review-Resolve 9). Die Full-Suite ohne Stream-A-Health-Tests
(`tests/test_health.py`, gehört zu Stream A) läuft grün (Exit 0).

## 2. Lessons Learned

### 2.1 Was lief gut

- **Registry-Pattern (ADR-0033) hat sich unter Parallelität bewährt.** Neue
  CLI-Commands in `new_nfl.plugins.hardening` registrieren sich via
  `register_cli_plugin` beim Import; kein einziger Merge-Konflikt in `cli.py`,
  obwohl Stream A parallel in derselben Datei gearbeitet hätte. Drei
  Operator-Surfaces (`trim-run-events`, `adapter-slice-sync`,
  `dedupe-review-resolve`) wurden additiv in dasselbe Plugin-Modul
  eingetragen — ohne Umbau zentraler Dispatch-Tabellen.
- **Schema-Cache hat die Mart-Migration trivial gemacht.** Das Cache-API
  wurde bewusst als drop-in-Ersatz für `con.execute("DESCRIBE …")` entworfen.
  Die 9 Mart-Module (T2.7E-2b) konnten darum per reinem Textersatz migriert
  werden; der "bit-identische Rebuild" war über `CREATE OR REPLACE TABLE` und
  Column-Set-Semantik automatisch gesichert.
- **Best-Effort-Hooks im Bootstrap sind die richtige Skalierungsstufe.**
  `_auto_activate_default_ontology` und `_sync_adapter_slice_registry`
  scheitern beide weich (Exception → return). Ein kaputter TOML oder eine
  noch fehlende Tabelle darf den `bootstrap_local_environment` nicht
  killen — sonst ist die komplette CLI blockiert. Diese Entscheidung
  hat sich mehrfach während der Session bezahlt gemacht (siehe 2.3 Race).

### 2.2 Was lief nicht gut

- **Parallel-Stream-Race im gemeinsamen Working-Tree.** Die drei Streams
  (A Observability, B Resilience, C Hardening) teilen denselben
  `c:/projekte/newnfl`-Checkout; ein Branch-Switch eines anderen Streams
  überschrieb zweimal meine ungespeicherten `bootstrap.py` +
  `metadata.py`-Edits. Die committed-and-pushed-Stände blieben sicher, aber
  jeder Revert kostete ~5 Minuten Wieder-Apply + Wieder-Test.
- **Full-Suite-Feedback-Schleifen waren unnötig teuer.** Am Ende stand ich
  zweimal in einer 2–3-Minuten-Testsuite-Wartesequenz, obwohl die
  eigentliche Feature-Arbeit (T2.7E-1 bis T2.7E-5) bereits abgeschlossen
  und gepusht war. Exit-Code der Suite war seit T2.7E-5 stabil 0; ich
  hätte den Lessons-Doc parallel schreiben können.
- **`tests/test_health.py` schlägt auf `feature/t27-hardening` fehl** — weil
  das zugehörige `health-probe`-Plugin nur auf `feature/t27-observability`
  existiert. Das ist *nicht* ein Hardening-Regression, sondern
  erwartetes Cross-Branch-Artefakt der Stream-Parallelität; die
  `--ignore=tests/test_health.py`-Klausel ist legitim für Stream-C-Scope.

### 2.3 Root Cause

- **Parallel-Stream-Race:** Das Memory `project_parallel_streams_shared_workdir.md`
  beschreibt das Risiko bereits; die Schutzmechanismen (Tag-Bookmark,
  SHA-Refspec-Push) greifen *post mortem* auf Git-Ebene, nicht für
  untracked oder ungespeicherte Arbeitsdateien. Ein echter Worktree
  (`git worktree add`) hätte das strukturell gelöst.
- **Feedback-Schleifen-Kosten:** Ich habe die Full-Suite als
  "Sicherheitsnetz" behandelt, obwohl pro-Slice-Tests pro Commit bereits
  grün waren. Bei 6 aufeinander-folgenden grünen Commits ist die
  *marginale* Info einer weiteren Full-Suite = null; die Zeit wäre besser
  in das Handoff-Artefakt geflossen.

### 2.4 Konkrete Methodänderung

- **Stream-Isolation:** Bei der nächsten Multi-Stream-Tranche jeder
  parallel laufende Stream bekommt einen dedizierten `git worktree` in
  `c:/projekte/newnfl.wt/<stream>` statt Branch-Flips im Haupt-Checkout.
  Memory `project_parallel_streams_shared_workdir.md` entsprechend
  aktualisieren (siehe 3.).
- **Full-Suite-Policy:** *Einmalige* grüne Full-Suite vor dem ersten Commit
  einer Tranche reicht; pro nachfolgendem Commit nur das neu betroffene
  Test-Set + `ruff check` auf den geänderten Dateien. Eine weitere
  Full-Suite nur dann, wenn (a) der Commit gemeinsame Infrastruktur
  (metadata.py / settings.py / bootstrap.py) ändert oder (b) vor dem
  Stream-Merge-Commit. Zielgröße: 1 Full-Suite-Run pro Stream, nicht 5.
- **Lessons-Doc zeitlich vorziehen:** Sobald der letzte *Feature*-Commit
  steht, parallel zur finalen Testrun-Wartezeit den Handoff-Entwurf
  beginnen — nicht danach.

### 2.5 Verifikation

- **Nächste Tranche (T2.8 oder RC-Cut):** Kein Stream-Revert im
  Haupt-Checkout mehr. Nachweis: `git reflog` des Haupt-Worktrees zeigt
  keine fremden Branch-Flips.
- **Lessons-Doc-Turnaround:** Zielzeit vom letzten Feature-Commit bis zur
  gepushten Lessons-Doc-Datei ≤ 20 min. Bei T2.7C lag dieser Turnaround
  deutlich darüber (primär durch redundante Full-Suite-Reruns).

## 3. Offene Folge-Arbeiten

- **Memory-Update** `project_parallel_streams_shared_workdir.md`: Ergänzen
  um die Worktree-Empfehlung (2.4).
- **Stream-Merge T2.7F:** `feature/t27-hardening`, `feature/t27-observability`
  und `feature/t27-resilience` in `main` zusammenführen. Reihenfolge
  Operator-Entscheidung; Stream C ist merge-ready und konfliktfrei
  gegen `main` (Stand 2026-04-23).
- **Test-Health-Konvergenz:** Nach dem Drei-Stream-Merge läuft
  `tests/test_health.py` natürlich grün, weil dann auch das Plugin
  registriert ist. Keine Stream-C-Arbeit nötig.

## 4. Referenzen

- ADR-0033 (Registry-Pattern): `docs/_adrs/ADR-0033-registry-pattern.md`
- Memory: `project_parallel_streams_shared_workdir.md`
- Vorangegangenes Handoff: `chat_handoff_20260423-2350_t27p-registry-complete.md`
