# NEW NFL — Use-Case-Validierung v0.1

**Datum:** 2026-04-13
**Zweck:** Strukturierte Abnahme der fachlichen Use Cases, des Deployment-Modells, der Architektur-Leitplanken und der UI-Ambition.
**Bedienung:** Trage unter jedem Punkt eines ein:

- `OK` — bestätigt
- `Nein` — abgelehnt / nicht gewünscht
- `Kommentar: …` — Anpassung, Frage, Priorität, Zeithorizont

Dieses Dokument ersetzt keine ADRs. Was hier abgenommen wird, fließt anschließend in ADR-Updates, das System Concept und das Engineering Manifest ein.

---

## 0. Lese-Reihenfolge

1. Abschnitt 1 — Produktziel und Leitsätze
2. Abschnitt 2 — Deployment-Modell (Laptop → VPS)
3. Abschnitt 3 — Datendomänen und Quellen
4. Abschnitt 4 — Use Cases (fachlich)
5. Abschnitt 5 — UI / GUI Ambition
6. Abschnitt 6 — Architektur- und Resilienz-Leitplanken
7. Abschnitt 7 — Ontologie und Dedupe
8. Abschnitt 8 — Engineering-Manifest-Erweiterungen
9. Abschnitt 9 — Nicht-Ziele
10. Abschnitt 10 — Offene Fragen

---

## 1. Produktziel und Leitsätze

### 1.1 Produktziel
NEW NFL ist eine private, langfristig betriebene NFL-Daten- und Analyseplattform für einen primären Operator. Sie sammelt, konsolidiert und visualisiert NFL-Daten aus mehreren Quellen mit maximaler Zuverlässigkeit, Redundanz und Nachvollziehbarkeit.

**Abnahme:**OK

### 1.2 Leitsatz „lieber dreifach als vergessen"
Daten werden bewusst aus mehreren Quellen redundant gesammelt. Konsolidierung erfolgt erst im kanonischen Kern (1 Fakt = 1 Eintrag), Rohdaten und Quellbezug bleiben dauerhaft erhalten.

**Abnahme:**OK

### 1.3 Leitsatz „Zahlen, Daten, Fakten + Kontext"
Sammelfokus liegt auf strukturierten Daten (Spielstände, Stats, Aufstellungen, Verletzungen, Wetter). Bilder / Videos werden **nicht** archiviert. Unstrukturierter Kontext (Gossip, off-field news, Verletzungs-Hintergrund) wird gezielt erhoben und mit dem Spieler/Spiel verknüpft.

**Abnahme:**OK

### 1.4 Leitsatz „Autonomie im Sammeln"
Das System soll im Zielzustand selbstständig nach Zeitplan sammeln, Quellenausfälle tolerieren und Lücken später automatisch nachholen (Backfill, Replay).

**Abnahme:**OK

---

## 2. Deployment-Modell

### 2.1 Phase „bis v1.0" — DEV-LAPTOP only
Bis zum Erreichen einer stabilen v1.0 läuft alles auf dem Entwicklungslaptop:
- Code, DuckDB-Warehouse, Raw-Landing, Mini-Webserver, Scheduler.
- Kein VPS-Deployment in dieser Phase.
- VPS-Runbook (`RUNBOOK_VPS_PREVIEW_RELEASE.md`) bleibt vorbereitet, wird aber nicht ausgeführt.

**Abnahme:**OK

### 2.2 Migration nach v1.0 → Windows-VPS
Mit v1.0 erfolgt die kontrollierte Migration auf den Contabo Windows-VPS gemäß VPS-Dossier (Tailscale-RDP, Cloudflare Tunnel, lokaler Bind 127.0.0.1, Defender Firewall aktiv, kein öffentliches RDP).

**Abnahme:**OK

### 2.3 Definition v1.0 (Vorschlag)
v1.0 gilt als erreicht, wenn:
- alle Phase-1-Datendomänen (Abschnitt 3.1) regelmäßig gefüllt werden,
- Web-UI alle Phase-1-Browse-Views liefert,
- Scheduler autonom mit Retry/Quarantäne läuft,
- Run-Evidence + Provenance vollständig vorhanden,
- Backup/Restore und Replay einmal real getestet wurden.

**Abnahme:**OK

### 2.4 OS-Neutralität bewahren
Anwendungslogik bleibt OS-neutral (Python). Nur die Service-Supervisor-Schicht (Windows-Service / Task Scheduler) ist Windows-spezifisch. Damit bleibt späterer Wechsel auf Linux-VPS offen, ohne Zwang.

**Abnahme:**OK

---

## 3. Datendomänen und Quellen

### 3.1 Phase-1-Domänen (must-have bis v1.0)
- Seasons / Weeks
- Teams
- Games / Schedules / Results
- Players (Stammdaten)
- Rosters (zeitbezogene Team-Player-Zugehörigkeit)
- Team-Level Aggregated Stats
- Player-Level Aggregated Stats

**Abnahme:**OK

### 3.2 Phase-1.5-Domänen (kurz nach v1.0)
- Injuries (Verletzungen, Status, Historie)
- Depth Charts
- Snap Counts
- Betting Lines (Odds)
- Wetter / Venue-Enrichment

**Abnahme:**OK

### 3.3 Wetter-Sonderbehandlung
- **Pflicht** für alle zukünftigen Spiele (Forecast + Ist-Wetter am Spieltag).
- **Nice-to-have** für historische Spiele, mindestens letzte 2 Saisons rückwirkend, falls technisch beschaffbar. Ältere Backfills nur opportunistisch.

**Abnahme:**OK

### 3.4 Gossip / Off-Field-Domäne
Strukturierte Erfassung von off-field Ereignissen mit potenziellem Leistungseinfluss:
- Polizei / juristische Vorfälle
- Suspensions / Disziplinarmaßnahmen
- öffentlich gemachte private Konflikte / Familienereignisse
- Trade-Gerüchte, Vertragskonflikte
- Coaching-/Front-Office-Wechsel

Pro Eintrag: Spieler-/Team-Bezug, Datum, Quelle(n), Confidence-Level (gesichert / berichtet / Gerücht), Kurztext.
**Bilder / Videos: nein.** Nur Text + Metadaten + Quell-URL.

**Abnahme:**OK

### 3.5 Quellen-Tiering (gemäß ADR-0007)
Quellen werden in Tiers eingeteilt (z. B. Tier-A offizielle/nflverse, Tier-B etablierte Stat-Sites, Tier-C Aggregatoren, Tier-D Gossip/News). Konflikte werden gemäß Tier-Priorität und Zeitstempel aufgelöst.

**Abnahme:**OK

### 3.6 Redundanz pro Faktum
Wo möglich, jedes Faktum aus **≥ 2 unabhängigen Quellen**. Single-Source-Fakten bleiben erlaubt, werden aber als solche im UI markiert.

**Abnahme:**OK

### 3.7 Explizit ausgeschlossen
- Bilder, Logos, Videos, Audio, Highlights
- Fan-Foren-Volltexte (zu rauschig)
- Social-Media-Volltext-Archivierung (nur kuratierte Auszüge im Gossip-Modul)

**Abnahme:**OK

---

## 4. Use Cases (fachlich)

> Jeder Use Case ist als „User Story" formuliert. Pro UC: OK / Nein / Kommentar.

### UC-01 — Saison & Woche browsen
Als Operator möchte ich alle Saisons und Wochen sehen und in eine Woche eintauchen, um Spiele dieser Woche zu sehen.

**Abnahme:**OK

### UC-02 — Team-Profil ansehen
Als Operator möchte ich ein Team auswählen und Stammdaten, aktuelle Roster, Saisonstatistiken und Spielhistorie sehen.

**Abnahme:**OK

### UC-03 — Spieler-Profil ansehen
Als Operator möchte ich einen Spieler auswählen und Stammdaten, aktuelle Team-Zugehörigkeit, Karriere-Stats, Verletzungshistorie und Gossip-Einträge sehen.

**Abnahme:**OK

### UC-04 — Spiel-Detail (Pre-Game)
Als Operator möchte ich vor einem Spiel sehen: Teams, voraussichtliche Aufstellung, Verletzungsstatus, aktuelle Form (letzte N Spiele), Wetterprognose, Betting Lines, relevanter Off-Field-Kontext.

**Abnahme:**OK

### UC-05 — Spiel-Detail (Post-Game)
Als Operator möchte ich nach einem Spiel sehen: Endstand, Box-Score, Snap Counts, Wetter-Ist, Verletzungen aus dem Spiel.

**Abnahme:**OK

### UC-06 — Vergleich Spieler ↔ Spieler
Als Operator möchte ich zwei oder mehr Spieler in ausgewählten Stat-Kategorien nebeneinander vergleichen (Saison oder Karriere).

**Abnahme:**OK

### UC-07 — Vergleich Team ↔ Team
Analog für Teams (Saisonebene, optional Head-to-Head Historie).

**Abnahme:**OK

### UC-08 — Verletzungs-Übersicht (League-wide)
Als Operator möchte ich eine wochengenaue league-weite Verletzungsliste mit Status (out / questionable / probable / IR) und Verlaufsdaten sehen.

**Abnahme:**OK

### UC-09 — Wetter-Übersicht für anstehende Spiele
Als Operator möchte ich für die kommende Woche eine Wetter-Vorschau pro Spielort sehen, mit Update-Zeitstempel.

**Abnahme:**OK

### UC-10 — Off-Field / Gossip Feed
Als Operator möchte ich pro Team und pro Spieler einen chronologischen Feed mit eingestuften Off-Field-Ereignissen sehen.

**Abnahme:**OK

### UC-11 — Provenance-Drilldown
Als Operator möchte ich zu jedem angezeigten Wert sehen: Quelle(n), Abrufzeitpunkt, Run-ID, Konfliktstatus.

**Abnahme:**OK

### UC-12 — Freshness-Dashboard
Als Operator möchte ich auf einer Startseite sehen: welche Datendomäne wann zuletzt erfolgreich aktualisiert wurde, welche im Rückstand sind, wo Quarantäne-Fälle liegen.

**Abnahme:**OK

### UC-13 — Run-Evidence einsehen
Als Operator möchte ich vergangene Runs (Fetch, Stage-Load, Promotion) mit Status, Dauer, Row Counts und Fehlern einsehen.

**Abnahme:**OK

### UC-14 — Manueller Refresh / Replay (Operator-Aktion)
Als Operator möchte ich einzelne Quellen-Refreshes oder Replays vom Raw-Artefakt auslösen, ohne in die CLI zu wechseln.

**Abnahme:**OK

### UC-15 — Quarantäne-Review
Als Operator möchte ich Quarantäne-Fälle einsehen, eine Entscheidung treffen (Replay, Override, Suppress) und das mit Notiz dokumentieren.

**Abnahme:**OK

### UC-16 — Export für externe Analyse
Als Operator möchte ich gefilterte Read-Modelle als CSV/Parquet exportieren, um sie extern (Notebook, Excel) weiter zu nutzen.

**Abnahme:**OK

### UC-17 — Suche
Als Operator möchte ich eine schnelle globale Suche über Spieler, Teams, Spiele.

**Abnahme:**OK - allgemeiner Kommentar: wichtig ist das wir die Spielernamen und Teamnamen so darstellen in der Oberfläche wie sie in der Realität heißen also Travis Kelce und nicht T Kel oder anser abgekürzt - wir nutzten die offiziellen Namen der TEams und Spieler - das ist ein allegemeiner Kommentar und dient der besseren UX

### UC-18 — (Phase 2) Prediction / Simulation
Als Operator möchte ich später Spielausgang-Wahrscheinlichkeiten und Playoff-Szenarien sehen — **nicht in Phase 1**, aber Architektur muss es zulassen, ohne den kanonischen Faktenkern zu verschmutzen.

**Abnahme:** OK

### UC-19 — (Phase 2) Bet-Tracking
Als Operator möchte ich Wetten / Picks tracken und gegen Outcomes evaluieren — **nicht in Phase 1**.

**Abnahme:** OK

### UC-20 — Weitere Use Cases (frei)
Tragen Sie hier zusätzliche Use Cases ein, die Ihnen wichtig sind:

**Kommentar / Ergänzung:** falls unser weitere DAten oder datenquellen einfallen müssen wir diese integreieren können - das muss dann nicht unbedingt für die komplette vergangeheit sein, aber die archirtekurt muss das erlauben das wie neue DAten anlegen können also neue statistiken

---

## 5. UI / GUI Ambition

### 5.1 Designanspruch
Das UI soll **grafisch ansprechend, modern und klar lesbar** sein — kein „Behörden-Dashboard". Anspruch entspricht eher modernen Sport-Analytics-Sites (FiveThirtyEight-Klasse, The Athletic-Klasse), nicht Excel-Optik.

**Abnahme:**ok

### 5.2 Designprinzipien (Vorschlag)
- **Typografie:** eine Sans-Serif für UI (Inter / Geist / IBM Plex Sans), eine Tabellen-Mono (JetBrains Mono / IBM Plex Mono) für Zahlenkolonnen mit `font-feature-settings: "tnum"` (tabular numerals).
- **Farbsystem:** neutrale Basis (Slate/Zinc), ein Akzent, Status-Farben (success / warn / danger) konsistent.
- **Dark-Mode** als Standard, Light-Mode optional.
- **Layout:** großzügige Whitespace, klare Hierarchie, max. 3 Schriftgrade pro View, konsistentes 4/8-px-Spacing-Raster.
- **Datendarstellung:** Sparklines, kleine Multiples, klare Tabellen mit Sticky-Header, dezente Charts (kein Chart-Junk).
- **Interaktion:** Tastatur-Shortcuts (Suche, Navigation), schnelle Filter, „command palette" (Cmd/Ctrl-K).
- **Accessibility:** WCAG-AA Kontraste, sichtbarer Fokusring, semantisches HTML.

**Abnahme:**ok

### 5.3 Tech-Stack-Vorschlag UI
- Phase 1 bleibt **server-rendered** (Python-first, Jinja-Templates) — schnell, robust, geringe Komplexität.
- Styling: **Tailwind CSS** + ein kleines Komponenten-Set (z. B. shadcn-Style-Patterns, manuell adaptiert).
- Charts: **Observable Plot** oder **ECharts** (deklarativ, leichtgewichtig).
- Optional `htmx` für gezielte Interaktivität ohne SPA-Komplexität.
- Eine spätere SPA-Variante (React/Svelte) ist **nicht** Teil von Phase 1.

**Abnahme:**ok

### 5.4 UI-Pflicht-Views für v1.0
- Home / Freshness-Dashboard (UC-12)
- Season → Week → Game-Liste (UC-01)
- Team-Profil (UC-02)
- Player-Profil (UC-03)
- Game-Detail Pre/Post (UC-04, UC-05)
- Provenance-Drilldown (UC-11)
- Run-Evidence (UC-13)

**Abnahme:**ok

### 5.5 UI-Erweiterungen nach v1.0
- Vergleichs-Views (UC-06, UC-07)
- Verletzungsliga-View (UC-08)
- Wetter-Vorschau (UC-09)
- Gossip-Feed (UC-10)
- Quarantäne-Review (UC-15)
- Suche / Command Palette (UC-17)

**Abnahme:**ok

---

## 6. Architektur- und Resilienz-Leitplanken

### 6.1 Beibehaltung des aktuellen Kerns
Bestätigt bleibt der Kurs aus `NEW_NFL_SYSTEM_CONCEPT_v0_2.md`:
- Python 3.12, modularer Monolith
- DuckDB als analytisches Zentrum
- Parquet als persistiertes Austausch-/Evidenzformat
- Filesystem-Raw-Landing
- Server-rendered Web-UI + HTTP-API
- Scheduler / Run-Evidence im System selbst

**Abnahme:**ok

### 6.2 Architekturpräzisierungen (neu vs. v0.2)
Vorgeschlagene Schärfungen für die nächste System-Concept-Version (v0.3):

a) **Internes Job-/Run-Modell explizit machen**: `job_definition`, `schedule`, `queue`, `run`, `attempt`, `retry_policy`, `quarantine_case`, `recovery_action` als eigene Tabellen in `meta.*`.
**Abnahme:**ok

b) **Ontologie-as-Code**: Begriffe, Aliases, Mappings, Value Sets, Constraints liegen versioniert im Repo, werden zur Laufzeit in DuckDB-Tabellen projiziert.
**Abnahme:**ok

c) **Dedupe-Pipeline** explizit als eigener Schritt: deterministische Normalisierung → Match-Kandidaten → Score → Cluster → Review-Queue.
**Abnahme:**ok

d) **Quarantäne als First-Class-Domäne**: Fehler werden nie still verworfen, immer in Quarantäne sichtbar mit Recovery-Pfad.
**Abnahme:**ok

e) **Read-Modell-Trennung**: Web-UI und API lesen ausschließlich aus publizierten Read-Modellen (`mart.*`), nie direkt aus `stg.*` oder `raw.*`.
**Abnahme:**ok

f) **Replay-fähigkeit**: Jeder Run muss aus dem unveränderten Raw-Artefakt reproduzierbar sein. Raw-Artefakte sind immutable.
**Abnahme:**ok

### 6.3 Resilienz-Anforderungen
- Ein Quellausfall darf den restlichen Betrieb nicht stoppen (Designed Degradation).
- Retries mit Backoff für transiente Fehler, Quarantäne für strukturelle/fachliche Fehler.
- Health-Endpunkte: `/livez`, `/readyz`, `/health/deps`, `/health/freshness`.
- Scheduler-Heartbeat in der UI sichtbar.
- Backup des DuckDB-Warehouses und der Raw-Landing als geübter Vorgang.

**Abnahme:**ok

### 6.4 Observability-Minimum
Strukturierte Logs mit `run_id`, `job_name`, `source_id`, `outcome`, `duration_ms`, `error_code`. Basis-Metriken: `runs_started_total`, `runs_failed_total`, `freshness_seconds{dataset=*}`, `queue_depth`.

**Abnahme:**ok

### 6.5 OS- und Runtime-Disziplin
- App-Code OS-neutral.
- Service-Wrapping / Scheduling über Windows-Mittel (Task Scheduler / Windows-Service) auf dem VPS, lokal als Foreground-Prozess.
- Secrets ausschließlich in `.env` / OS-Keystore, nie im Repo.

**Abnahme:**ok

---

## 7. Ontologie und Dedupe

### 7.1 Kanonische Identitäten
Stabile interne Keys für: Season, Week, Team, Game, Player, Roster-Membership, Venue, InjuryEvent, OffFieldEvent. Externe IDs werden als Referenzen mitgeführt, nicht als Wahrheit.

**Abnahme:**ok

### 7.2 Spieler-Dedupe-Härtefälle
Beispiel: gleiche Namen, Jr./Sr., Suffixe, Trade innerhalb Saison, Namensänderungen. Strategie: deterministische Normalisierung + probabilistisches Matching + Review-Queue für Grenzfälle.

**Abnahme:**ok

### 7.3 Konfliktauflösung Stat-Werte
Beispiel: passing_yards aus zwei Quellen weichen ab. Regel-Skizze: Tier-A schlägt Tier-B; bei Gleichstand: jüngerer Run wins; Konflikt wird gespeichert + im UI sichtbar.

**Abnahme:**ok

### 7.4 Ontologie-Versionierung
Jede Promotion in den kanonischen Kern referenziert eine Ontologie-Version. Änderungen an der Ontologie sind ADR-pflichtig, wenn sie kanonische Felder betreffen.

**Abnahme:**ok

---

## 8. Engineering-Manifest-Erweiterungen (Vorschlag v1.3)

Vorschläge für neue / geschärfte Prinzipien im Manifest:

### 8.1 „Redundanz vor Sparsamkeit beim Sammeln"
Es wird bewusst mehrfach gesammelt. Konsolidierung erfolgt erst im Kanon. Diese Redundanz ist Feature, nicht Verschwendung.
**Abnahme:**ok

### 8.2 „Replay-Fähigkeit ist Pflicht"
Kein Pipeline-Schritt darf Raw-Artefakte konsumieren ohne Replay-Möglichkeit zu erhalten.
**Abnahme:**ok

### 8.3 „UI-Qualität ist Systemqualität"
Eine schlechte UI ist kein kosmetischer Mangel, sondern ein Systemmangel — sie verhindert Operator-Verständnis und damit Datenintegrität.
**Abnahme:**ok

### 8.4 „Read-Modell-Disziplin"
UI/API lesen niemals direkt aus Raw oder Staging. Verstöße sind Architekturfehler.
**Abnahme:**ok

### 8.5 „Quarantäne ist ein Lebenszustand, kein Fehler"
Quarantäne-Fälle werden nicht versteckt, sondern sind sichtbar, zählbar, bearbeitbar.
**Abnahme:**ok

### 8.6 „Autonomie mit Sichtbarkeit"
Autonome Sammlung ist Ziel — aber jeder autonome Lauf muss im Freshness-Dashboard und in Run-Evidence nachvollziehbar sein.
**Abnahme:**ok

---

## 9. Nicht-Ziele (explizit)

- Multi-User / kommerzielles Produkt
- Bilder / Videos / Audio
- Echtzeit-Push / Live-Ticker auf Sekundenebene
- Microservice-Zerlegung
- Eigene Mobile-App
- Vollständige Social-Media-Archivierung
- Wetten-Plattform mit Geldfluss

**Abnahme insgesamt:**ok

---

## 10. Offene Fragen an den Operator

1. **Saison-Tiefe historischer Daten**: Konzept v0.2 nennt „letzte ~15 Jahre". Bestätigen oder anpassen?
   **Antwort:**OK

2. **Gossip-Quellen**: Gibt es bevorzugte Quellen (ESPN, ProFootballTalk, lokale Beat-Reporter, Reddit-Curated, X/Twitter-Listen)?
   **Antwort:**keine bevorzugten quellen

3. **Wetterquelle**: Open-Meteo / NOAA / kommerziell? Historische Tiefe wirklich nur 2 Saisons reichend?
   **Antwort:**historische tiefe von 2 seasons reicht hier - aber das ist wichtig für die jeweils aktuelle saisson - es sollen die größten us anbieter abgefragt werden

4. **Betting-Lines**: aus welcher Quelle? (The Odds API / scraping / nflverse-Lines)
   **Antwort:** große bekannte us anbieter - da die wahrscheinlich die beste basis haben

5. **Aktualisierungs-Kadenz in-season**: täglich genug, oder mehrfach täglich an Spieltagen?
   **Antwort:**täglich ist ausreichend

6. **Operator-Aktionen aus dem UI**: Sollen Refresh / Replay / Quarantäne-Override wirklich aus dem Web-UI auslösbar sein, oder bleibt das CLI-only?
   **Antwort:**CLI only reicht

7. **Auth für VPS-UI**: Reicht Cloudflare Access (interaktive Seite) ohne weiteres Login, oder zusätzlich Basic-Auth / passkey?
   **Antwort:**ckloudfare access reicht

8. **Backup-Ziel**: Wohin sichern wir Warehouse + Raw? (zweite VPS-Disk, externe Cloud-Storage, lokales NAS)
   **Antwort:**nur auf dem VPS, da der VPS eine tägliche backup funktion hat

9. **v1.0-Termin**: Gibt es einen Zielzeitpunkt, oder „so lange es dauert, bis stabil"?
   **Antwort:**v1 muss bis ende april entwicklet sein, dann im Mai gestestet werden um ausreichend früh zur preseason verfügbar zu sein

10. **Priorisierung Phase-1.5-Domänen**: Reihenfolge Injuries / DepthCharts / Snaps / Lines / Wetter?
    **Antwort:** OK

---

## 11. Nächste Schritte nach Abnahme

Sobald dieses Dokument abgenommen ist, folgt:

1. Update `NEW_NFL_SYSTEM_CONCEPT` → v0.3 (mit den bestätigten Schärfungen aus Abschnitt 6).
2. Update `ENGINEERING_MANIFEST` → v1.3 (mit den bestätigten Prinzipien aus Abschnitt 8).
3. Neue ADRs für: Job-/Run-Modell, Ontologie-Runtime, Dedupe-Pipeline, Quarantäne-Domäne, Read-Modell-Trennung, UI-Tech-Stack.
4. Neuer Tranche-Plan T2.3+ ausgerichtet auf v1.0-Definition (Abschnitt 2.3).
5. UI-Style-Guide als eigenes Dokument (`UI_STYLE_GUIDE.md`) mit Typografie, Farben, Komponenten.
