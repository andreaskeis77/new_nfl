# NEW NFL System Concept v0.3

**Status:** Draft for adoption — supersedes v0.2
**Phase:** A0.3
**Scope:** Architektur-Anker für Phase-1 bis v1.0 und unmittelbar danach.
**Last Updated:** 2026-04-13
**Vorgänger:** `NEW_NFL_SYSTEM_CONCEPT_v0_2.md` (2026-03-27)

## 0. Was sich gegenüber v0.2 ändert

v0.3 ist keine Kursänderung, sondern eine **Schärfung**. Die Grundentscheidungen aus v0.2 (Python 3.12, DuckDB-Zentrum, Parquet, Filesystem-Raw-Landing, server-rendered Web, Windows-VPS-Ziel) bleiben gültig.

Neu / verbindlich in v0.3:

1. **v1.0-Zielkorridor** ist gesetzt: feature-complete Mitte bis Ende Juni 2026, Testphase Juli, produktiv vor Preseason-Start Anfang August 2026.
2. **Deployment-Phasen** sind gesetzt: bis v1.0 ausschließlich DEV-LAPTOP, Migration auf Windows-VPS erst nach v1.0.
3. **Sechs Architektur-Schärfungen** sind verbindlich (Abschnitt 6).
4. **Read-Modell-Trennung** ist verbindlich: UI/API lesen ausschließlich aus `mart.*`.
5. **Erweiterbarkeit als Constraint**: Neue Datendomänen müssen ohne Bruch des kanonischen Kerns ergänzbar sein.
6. **Ontologie-as-Code** ist die verbindliche Form des Ontologie-Managements.
7. **Quarantäne** ist eine First-Class-Domäne, kein Logging-Detail.
8. **Replay** aus immutable Raw-Artefakten ist Pflicht für jeden Pipeline-Schritt.
9. **Gossip / Off-Field** ist als Datendomäne aufgenommen (Phase-1.5).
10. **Wetter** ist Pflicht für künftige Spiele, opportunistisch für ≥ 2 Saisons rückwirkend.

## 1. Produktziel (bestätigt)

NEW NFL ist eine private, langfristig betriebene NFL-Daten- und Analyseplattform für einen primären Operator. Sie sammelt redundant aus mehreren Quellen, konsolidiert in einen kanonischen Kern und macht alles über eine grafisch hochwertige read-only Web-Oberfläche zugänglich.

Leitsätze:

- **Lieber dreifach als vergessen** — Redundanz ist Feature.
- **Zahlen, Daten, Fakten + Kontext** — keine Bilder/Videos, aber strukturierter Off-Field-Kontext.
- **Autonomie im Sammeln** — Scheduler holt selbstständig, toleriert Quellenausfälle, holt Lücken nach.
- **UI-Qualität ist Systemqualität** — eine schlechte UI verhindert Operator-Verständnis.

## 2. Deployment-Modell

### 2.1 Bis v1.0: DEV-LAPTOP only
Code, DuckDB-Warehouse, Raw-Landing, Mini-Webserver, Scheduler laufen ausschließlich auf dem Entwicklungslaptop. Kein VPS-Deployment in dieser Phase.

### 2.2 Nach v1.0: Migration auf Windows-VPS
Kontrollierte Migration auf den Contabo Windows-VPS gemäß VPS-Dossier:
- Tailscale-RDP für Admin (kein öffentliches RDP).
- Cloudflare Tunnel für Web/UI (kein öffentlicher Inbound).
- Windows Defender Firewall aktiv.
- Anwendung bindet lokal auf `127.0.0.1`.
- Cloudflare Access als Auth vor der Web-UI (ausreichend).

### 2.3 OS-Neutralität
Anwendungslogik bleibt OS-neutral (Python). Nur die Service-Supervisor-Schicht (Windows-Service / Task Scheduler) ist Windows-spezifisch. Späterer Wechsel auf Linux-VPS bleibt möglich, ist aber nicht geplant.

### 2.4 Definition v1.0
v1.0 gilt als erreicht, wenn:
- alle Phase-1-Domänen (Abschnitt 3.1) regelmäßig befüllt werden,
- Web-UI alle v1.0-Pflicht-Views liefert,
- Scheduler autonom mit Retry und Quarantäne läuft,
- Run-Evidence und Provenance vollständig vorhanden sind,
- Backup/Restore und Replay einmal real getestet wurden,
- alle Operator-Aktionen über CLI verfügbar sind.

UI-Buttons für Refresh / Replay / Quarantäne-Override sind **nicht** v1.0-Pflicht; sie sind v1.1.

### 2.5 Zielkorridor
- v1.0 feature-complete: bis Ende Juni 2026.
- Testphase: Juli 2026, 4–6 Wochen.
- Produktiv auf VPS: vor Preseason-Start Anfang August 2026.

## 3. Datendomänen

### 3.1 Phase-1 (must-have für v1.0)
1. Seasons / Weeks
2. Teams
3. Games / Schedules / Results
4. Players (Stammdaten)
5. Rosters (zeitbezogen)
6. Team-Level Aggregated Stats
7. Player-Level Aggregated Stats

### 3.2 Phase-1.5 (kurz nach v1.0)
Reihenfolge nach Operator-Bestätigung:
1. Injuries
2. Depth Charts
3. Snap Counts
4. Betting Lines (große US-Anbieter)
5. Wetter / Venue (große US-Anbieter)
6. Off-Field / Gossip

### 3.3 Wetter
- **Pflicht** für alle künftigen Spiele (Forecast vor dem Spiel + Ist-Wetter am Spieltag).
- **Nice-to-have** rückwirkend mindestens 2 Saisons; ältere Backfills nur opportunistisch.
- Quellen: große US-Anbieter (mehrfach, redundant).

### 3.4 Off-Field / Gossip
Strukturierte Erfassung mit Spieler-/Team-Bezug, Datum, Quelle(n), Confidence-Level (gesichert / berichtet / Gerücht), Kurztext, Quell-URL.
Kategorien: Polizei/Justiz, Suspensions, öffentlich gemachte private Konflikte, Trade-Gerüchte, Vertragskonflikte, Coaching-/Front-Office-Wechsel.
**Keine Bilder, keine Videos, kein Volltext-Social-Media-Archiv.**

### 3.5 Historische Tiefe
Standardziel: ~15 Jahre für Stammdaten und Stats. Wetter rückwirkend nur 2 Saisons. Gossip nur ab Erfassungsbeginn vorwärts.

### 3.6 Aktualisierungs-Kadenz
In-Season täglich. Außerhalb der Saison wöchentlich oder seltener je Domäne. Spieltag-spezifisches Wetter wird mehrfach am Spieltag aktualisiert (Forecast → Ist).

### 3.7 Quellen-Tiering
Tier-A offizielle/nflverse, Tier-B etablierte Stat-Sites, Tier-C Aggregatoren, Tier-D Gossip/News.
Konfliktauflösung: Tier-A schlägt Tier-B; bei Gleichstand jüngerer Run; Konflikte werden gespeichert und im UI sichtbar.

### 3.8 Redundanz pro Faktum
Wo möglich ≥ 2 unabhängige Quellen. Single-Source-Fakten erlaubt, aber als solche im UI markiert.

### 3.9 Erweiterbarkeit (Constraint, nicht optional)
Die Architektur muss neue Datendomänen und neue Statistik-Familien aufnehmen können, ohne den kanonischen Kern strukturell zu brechen. Konkret:
- Adapter-Pattern für neue Quellen ohne Touch am Core.
- Metadata-driven Ingestion-Registry.
- Neue Stat-Familien als zusätzliche `core.*`-Tabellen, nicht als breite Spaltenerweiterung bestehender Tabellen.
- Read-Modelle (`mart.*`) sind versioniert.

## 4. Plattform-Posture (bestätigt)

- **Python 3.12** als Implementierungssprache.
- **DuckDB** als analytisches Zentrum.
- **Parquet** als persistiertes Tabellen-/Evidenzformat.
- **Filesystem** für Raw-Landing und Artefakte.
- **Server-rendered Web-UI** (Jinja-Templates) + **HTTP-API** in Python.
- **Interner DB-gestützter Scheduler** auf der DuckDB-Metadatenfläche, OS-Scheduler nur als Trigger/Watchdog.
- **Cloudflare Tunnel** für Exposition (ab VPS-Phase).
- **Tailscale** für Admin-Zugang (ab VPS-Phase).

Bewusst **nicht** gewählt: PostgreSQL als Hauptkern, SQLite als Hauptanalysestore, Lakehouse-Stack mit externen Services, Microservices, externe Orchestrator (Airflow/Dagster/Temporal/Celery).

## 5. Layer-Modell

| Layer | Inhalt | Mutabilität | Zugriff |
|---|---|---|---|
| `raw/` (Filesystem) | unveränderte Quell-Artefakte, Header, Receipts | **immutable** | nur Ingestion / Replay |
| `stg.*` (DuckDB) | source-shaped Staging-Tabellen | rebuildbar | nur Pipeline-Code |
| `core.*` (DuckDB) | kanonischer Faktenkern | mutierend mit Provenance | nur Pipeline-Code |
| `mart.*` (DuckDB) | publizierte Read-Modelle für UI/API | rebuildbar | **einziger Lese-Pfad für UI/API** |
| `meta.*` (DuckDB) | Source-Registry, Runs, Jobs, Quarantäne, Ontologie-Runtime | mutierend | Pipeline + Operator |
| `forecast.*` (DuckDB, später) | Predictions / Simulationen | append, versioniert | strikt getrennt vom Kern |

**Verbindlich:** UI und HTTP-API lesen ausschließlich aus `mart.*` und `meta.*`. Direktzugriff auf `stg.*`, `core.*` oder `raw/` aus UI/API ist Architekturfehler.

## 6. Sechs Architektur-Schärfungen (verbindlich ab v0.3)

### 6.1 Internes Job-/Run-Modell als eigene Tabellenfamilie
In `meta.*`: `job_definition`, `job_schedule`, `job_queue`, `job_run`, `run_event`, `run_artifact`, `retry_policy`, `quarantine_case`, `recovery_action`. Claims über DuckDB-Transaktionen mit Idempotency-Keys. Kein externer Orchestrator in Phase 1.

### 6.2 Ontologie-as-Code
Begriffe, Aliases, Mappings, Value Sets, Constraints liegen versioniert im Repository unter `ontology/`. Beim Bootstrap und bei Ontologie-Releases werden sie deterministisch in `meta.ontology_*`-Tabellen projiziert. Jede Promotion in `core.*` referenziert eine Ontologie-Version.

### 6.3 Dedupe-Pipeline als eigener Schritt
Verbindlicher Ablauf: deterministische Normalisierung → Blocking/Match-Kandidaten → Score → Cluster → Review-Queue für Grenzfälle. Kein impliziter Dedupe in Adapter- oder Stage-Load-Code.

### 6.4 Quarantäne als First-Class-Domäne
Fehler werden nie still verworfen. Jeder fachlich oder strukturell unklare Fall landet in `meta.quarantine_case` mit `reason_code`, `severity`, `evidence_refs`, `status`, `owner`. Recovery-Aktionen erzeugen neue Runs mit Verweis auf den Quarantäne-Fall.

### 6.5 Read-Modell-Trennung
UI und API lesen ausschließlich aus `mart.*`. `mart.*` ist vollständig aus `core.*` rebuildbar. UI-Performance-Optimierungen erfolgen ausschließlich im Read-Modell, nie durch Denormalisierung im Kern.

### 6.6 Replay-Fähigkeit als Pflicht
Jeder Pipeline-Schritt muss aus dem unveränderten Raw-Artefakt reproduzierbar sein. Raw-Artefakte sind immutable. Replay erzeugt einen neuen Run mit Verweis auf die ursprünglichen Artefakte und die genutzten Code-/Ontologie-Versionen.

## 7. Kanonische Identitäten

Stabile interne Keys für: `Season`, `Week`, `Team`, `Game`, `Player`, `RosterMembership`, `Venue`, `InjuryEvent`, `OffFieldEvent`, `WeatherObservation`, `BettingLine`.

Externe IDs (nflverse_id, espn_id, pfr_id, …) werden als Referenzen mitgeführt, nicht als Wahrheit.

Display-Regel (verbindlich für UI/API): **immer offizielle vollständige Namen** (z. B. „Travis Kelce", nicht „T. Kelce" oder „T Kel"). Abkürzungen nur dort, wo sie offiziell sind (Team-Codes wie „KC").

## 8. Resilienz und Observability

### 8.1 Resilienz-Anforderungen
- Quellenausfall stoppt nicht den Gesamtbetrieb (Designed Degradation).
- Retries mit Backoff für transiente Fehler.
- Quarantäne für strukturelle/fachliche Fehler.
- Backup des DuckDB-Warehouses und der Raw-Landing als geübter Vorgang (auf VPS via Provider-Snapshot).

### 8.2 Health-Endpunkte (Pflicht ab v1.0)
- `/livez` — Prozess lebt
- `/readyz` — bereit für Requests
- `/health/deps` — DuckDB / Filesystem / Tunnel-Status
- `/health/freshness` — pro Domäne letzter erfolgreicher Run

### 8.3 Observability-Minimum
Strukturierte Logs mit `run_id`, `job_name`, `source_id`, `outcome`, `duration_ms`, `error_code`.
Basis-Metriken: `runs_started_total`, `runs_succeeded_total`, `runs_failed_total`, `freshness_seconds{dataset=*}`, `queue_depth`, `quarantines_total`.

### 8.4 Run-Evidence (Pflicht pro Run)
Source/Scope, Request-Kontext, Validatoren (ETag/Last-Modified), Roh-Artefakt-Referenz, Checksum, Parser-Version, Code-Version, Ontologie-Version, Row Counts, DQ-Ergebnisse, Diff-Zusammenfassung, Promotion-/Publish-Resultat.

## 9. Web-UI-Surface (v1.0)

Pflicht-Views für v1.0:
- Home / Freshness-Dashboard
- Season → Week → Game-Liste
- Team-Profil
- Player-Profil
- Game-Detail Pre-Game
- Game-Detail Post-Game
- Provenance-Drilldown
- Run-Evidence

Erweiterungen v1.1+: Vergleich Spieler/Team, Verletzungs-League-View, Wetter-Vorschau, Gossip-Feed, Quarantäne-Review-UI, Suche/Command-Palette.

Tech-Stack v1.0: Jinja-Server-Rendered, Tailwind CSS, Observable Plot oder ECharts für Charts, htmx für gezielte Interaktivität. Keine SPA in v1.0.

Designanspruch und Style sind in `UI_STYLE_GUIDE_v0_1.md` verbindlich geregelt.

## 10. Operator-Aktionen

v1.0: ausschließlich CLI. Refresh, Replay, Quarantäne-Override, Backfill werden über `python -m new_nfl.cli …` gesteuert.
v1.1: dieselben Aktionen zusätzlich als UI-Buttons.

## 11. Auth

VPS-Phase: Cloudflare Access vor der Web-UI ist ausreichend. Kein zusätzliches Basic-Auth / Passkey in v1.0.
Lokale Phase (vor v1.0): kein Auth, lokal gebunden.

## 12. Backup

VPS-Phase: tägliche Provider-Snapshots des Contabo-VPS sind die Backup-Strategie. Kein zusätzliches externes Backup in v1.0.
Lokale Phase: Verantwortung des Operators (Git-Repo + manueller Export der DuckDB).

## 13. Phase-2 Vorbehalte (nicht in v1.0)

- Prediction / Simulation (UC-18) — Architektur lässt es zu (`forecast.*`-Layer), Implementierung später.
- Bet-Tracking (UC-19) — später.
- UI-Buttons für Operator-Aktionen — v1.1.
- Vergleich, Verletzungs-League, Wetter-Vorschau, Gossip-Feed, Quarantäne-UI, Suche — v1.1+.

## 14. Nicht-Ziele (bestätigt)

- Multi-User / kommerzielles Produkt
- Bilder / Videos / Audio / Highlights
- Echtzeit-Push / Live-Ticker
- Microservice-Zerlegung
- Mobile-App
- Vollständige Social-Media-Archivierung
- Wetten-Plattform mit Geldfluss

## 15. Verweise

- `USE_CASE_VALIDATION_v0_1.md` — abgenommene Use Cases (Grundlage für v0.3)
- `ENGINEERING_MANIFEST.md` — Engineering-Regeln (v1.3 begleitend zu v0.3)
- `UI_STYLE_GUIDE_v0_1.md` — Design- und Typografie-Regeln
- `T2_3_PLAN.md` — Tranche-Plan zum v1.0-Ziel
- `concepts/NEW_NFL_SYSTEM_CONCEPT_v0_2.md` — vorheriger Stand
- `adr/ADR-002[5–9]*` — neue ADRs zu Job-Modell, Ontologie-Runtime, Dedupe, Quarantäne, Read-Modell-Trennung, UI-Tech-Stack
