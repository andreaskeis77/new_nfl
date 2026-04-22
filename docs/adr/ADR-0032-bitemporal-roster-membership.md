# ADR-0032: Bitemporale Modellierung von Roster-Mitgliedschaften

## Status
Proposed (2026-04-22, Treiber: T2.5D — erste bitemporale Domain im Projekt)

## Kontext

Bis einschließlich T2.5C sind alle `core.*`-Tabellen (`core.schedule_field_dictionary`, `core.team`, `core.game`, `core.player`) **punktuell-kanonisch**: Eine Zeile pro Business-Key, Last-Write-Wins pro `_loaded_at`, keine Zeitintervalle. Das reicht für Stammdaten wie Franchise-Metadaten oder unveränderliche Spielregeln, versagt aber bei Roster-Mitgliedschaften: Ein Spieler kann im Laufe einer Saison **wiederholt** zwischen Teams wechseln (Trade, Release, Practice-Squad-Signing, Re-Signing), und wir brauchen die vollständige Historie, nicht nur den aktuellen Stand.

Die nflverse-Quellen liefern Rosters **wochenweise als Snapshots** (`rosters_YYYY.csv` bzw. `weekly_rosters_YYYY.csv`): pro Saison × Woche × Team eine Liste aktiver Spieler. Aus dieser Snapshot-Sequenz müssen wir Intervalle (`valid_from`, `valid_to`) ableiten und Trades / Releases / Signings als abgeleitete Events ausweisen.

Gleichzeitig gilt weiter das System-Time-Prinzip (ADR-0008): Wir müssen rekonstruieren können, was zu einem bestimmten `_loaded_at` als wahr galt, auch wenn wir heute eine korrigierte Version bekommen (späte Tier-B-Korrektur, Operator-Override). Das ist die klassische **bitemporale** Konstellation — System-Time (wann wurde es uns geliefert) vs. Business-Time (wann war es in der realen NFL-Welt gültig).

Punkt-in-Zeit-Stammdaten (`core.team`, `core.player`) bleiben von dieser ADR **unberührt** — sie behalten die Last-Write-Wins-Semantik aus ADR-0007/0009. Nur die Mitgliedschaftsdomain (`core.roster_membership`) wird bitemporal.

## Entscheidung

Wir führen in T2.5D genau eine bitemporale Tabelle ein, mit klar getrennter System-Time und Business-Time:

### Tabelle `core.roster_membership`

| Spalte | Bedeutung | Zeitdimension |
|---|---|---|
| `player_id` | Business-Key Spieler (FK nach `core.player`) | — |
| `team_id` | Business-Key Team (FK nach `core.team`) | — |
| `season` | Saison-Jahr (INTEGER) | Business |
| `valid_from_week` | Erste Woche des Intervalls (1..22) | Business |
| `valid_to_week` | Letzte Woche des Intervalls (inkl.) oder `NULL` = offen / aktuell | Business |
| `position` | Positionsangabe zur Zeit des Snapshots | Business |
| `jersey_number` | Trikotnummer zur Zeit des Snapshots | Business |
| `status` | `active` / `practice_squad` / `injured_reserve` / ... | Business |
| `_first_loaded_at` | Erster Snapshot, in dem dieses Intervall gesehen wurde | System |
| `_last_loaded_at` | Letzter Snapshot, der das Intervall bestätigt hat | System |
| `_source_file_id`, `_adapter_id`, `_canonicalized_at` | Provenance-Standard | System |

**Primärschlüssel (logisch, nicht physisch erzwungen):** `(player_id, team_id, season, valid_from_week)`.

### Regeln

1. **Ein Intervall pro (Player, Team, Season, zusammenhängender Wochenbereich).** Wenn ein Spieler die Wochen 1–4 bei Team A ist, in Woche 5 abwesend, dann Wochen 6–8 bei Team B und 9–17 wieder bei Team A, entstehen **drei** Zeilen (`A: 1..4`, `B: 6..8`, `A: 9..17`), nicht eine aggregierte.

2. **`valid_to_week = NULL` heißt „Intervall endet in der aktuellsten verfügbaren Woche oder später".** Sobald ein Folgesnapshot zeigt, dass der Spieler nicht mehr zu diesem Team gehört, wird `valid_to_week` auf die letzte bestätigende Woche gesetzt. Solange der letzte gesehene Snapshot weiter bestätigt, bleibt `NULL` (Right-Open-Intervall).

3. **Grace-Period:** Fehlt eine Woche vollständig im Feed (Bye-Week, Datenlücke), wird das Intervall **nicht** automatisch geschlossen; erst wenn ein Folgesnapshot aktiv den Spieler ohne dieses Team zeigt, schließt `valid_to_week`. Eine Woche Lücke ohne Folgebeweis reicht nicht.

4. **System-Time-Rekonstruktion:** Aus `_first_loaded_at` / `_last_loaded_at` lässt sich „was wussten wir zu Zeitpunkt T?" nicht vollständig rekonstruieren — das ist explizit **außerhalb** dieser ADR. Für vollständige System-Time-Historie verweisen wir auf `meta.load_event` + `raw/` landing dirs (ADR-0008). `roster_membership` ist **Business-Time-primär**; System-Time-Spalten sind Provenance, nicht Zeitreise.

### Tabelle `meta.roster_event`

Abgeleitete Ereignisse aus dem Intervall-Diff:

| Spalte | Bedeutung |
|---|---|
| `roster_event_id` | UUID |
| `event_kind` | `signed` / `released` / `trade` / `promoted` / `demoted` (siehe Heuristik unten) |
| `season` | Saison |
| `week` | Business-Woche des Ereignisses |
| `player_id` | betroffener Spieler |
| `from_team_id` | Vorher-Team (NULL bei `signed`) |
| `to_team_id` | Nachher-Team (NULL bei `released`) |
| `evidence_json` | JSON mit den beteiligten `(player_id, team_id, valid_from_week, valid_to_week)`-Tupeln |
| `ingest_run_id` | Run, der das Event erzeugt hat |
| `detected_at` | `CURRENT_TIMESTAMP` zur Erzeugung |

### Trade-Heuristik (bewusst konservativ)

Ein `event_kind='trade'` wird nur gesetzt, wenn **beide** Bedingungen gelten:

- Spieler hat ein Intervall `(team_A, ..week_N)` und direkt anschließend `(team_B, week_N+1..)`.
- Dazwischen **keine** Lücke in der Snapshot-Kadenz (also Woche `N` und `N+1` sind beide im Feed).

Alle anderen Team-Wechsel (mit Lücke ≥ 1 Woche dazwischen) werden als `event_kind='released'` + `event_kind='signed'` in zwei Events modelliert — wir können ohne offiziellen Transaction-Feed nicht unterscheiden, ob das ein Waiver-Claim, ein Practice-Squad-Upgrade oder ein echter Trade war. Diese Begrenzung wird in den Lessons Learned als bekannte Limitation dokumentiert.

Ein `event_kind='promoted'` / `demoted` greift, wenn `from_team_id == to_team_id` und `status` zwischen `active` und `practice_squad` wechselt — das ist die einzige Intra-Team-Transition, die wir heuristisch detektieren können.

### Snapshot-vs-Historie-Trennung in `mart.*`

- **`mart.roster_current_v1`** — nur Zeilen mit `valid_to_week IS NULL`. Eine Zeile pro aktuell aktiver (Player, Team)-Paarung. Haupt-Read-Model für das Team-Profil / Player-Profil (T2.6D / T2.6E).
- **`mart.roster_history_v1`** — vollständige Intervallhistorie. Alle Zeilen aus `core.roster_membership`, angereichert mit `display_name`, `team_abbr`, `team_name` via Join gegen `core.player` / `core.team`. Basis für Roster-Timeline-Views (T2.6E erweitert, ggf. T2.7).

Beide Marts sind vollständige Rebuilds (`CREATE OR REPLACE TABLE`); Rebuild-Zeit ist unkritisch (Größenordnung 20k Rows pro Saison).

## Alternativen

1. **Punktuelle Tabelle + Audit-Trail**
   Einzeilig „aktueller Roster-Eintrag pro Spieler" + Audit-Log aller Änderungen. Vorteil: trivial zu lesen, bekannte Semantik. Nachteil: Historische Queries („wer spielte Woche 8 für die Raiders?") brauchen Log-Reconstruction — das ist genau die Komplexität, die bitemporale Modellierung vermeidet. Abgelehnt.

2. **Weekly-Snapshot-Tabelle (eine Zeile pro Player × Week)**
   Einfach zu laden, aber 53 Spieler × 18 Wochen × 32 Teams × 25 Saisons ≈ 760k Rows, die keine Intervallstruktur tragen. Intervall-Queries werden zu Laufzeit-Group-By-Artistik. Abgelehnt — die CSV-Input-Form ist Snapshot-weekly, die Core-Form muss Intervall sein.

3. **SCD Type 2 auf `core.player` direkt**
   Mitgliedschaft als Slowly-Changing-Attribute von `core.player`. Vorteil: weniger Tabellen. Nachteil: Vermischt Identität (Spieler-Stammdaten) mit Zugehörigkeit (variable Mitgliedschaft); bricht die klare Zuständigkeitslinie aus ADR-0009 und macht `core.player` entweder aufgebläht oder verlustbehaftet. Abgelehnt.

4. **Separate System-Time-Spalten (`sys_valid_from`, `sys_valid_to`)**
   Volle bitemporale Tabelle mit Systemintervallen pro Row. Vorteil: echte Zeitreise. Nachteil: jeder Snapshot führt zu Row-Vervielfachung; schwer zu testen; braucht Rebuild-Strategie, die wir aktuell nicht haben. **Verschoben** bis echter Bedarf entsteht (frühestens v1.1); `_first_loaded_at` / `_last_loaded_at` als „soft system-time" reichen für v1.0.

## Konsequenzen

**Positiv:**
- Roster-Historie ist abfragbar („wer war Woche N im Team X?") ohne Event-Reconstruction.
- Trades/Signings/Releases werden explizit in `meta.roster_event` materialisiert; UI kann diese Events listen (Team-Profil Transaction-Feed in T2.6D).
- Bitemporale Struktur ist ab T2.5D als Muster etabliert und für zukünftige Domains (`core.contract_tenure`, `core.coaching_stint`) wiederverwendbar.

**Negativ:**
- Höhere Lade-Komplexität: Intervall-Ableitung aus Snapshot-Sequenzen via `LAG`/`LEAD`/Window-Function-Choreographie.
- Trade-Heuristik ist unvollständig — ohne offiziellen Transaction-Feed unterscheiden wir Waiver-Claim und Trade nicht zuverlässig. Wird als Limitation dokumentiert.
- `valid_to_week IS NULL` als „offenes Intervall" muss in jeder konsumierenden Query bewusst behandelt werden (Falle: `WHERE valid_to_week >= X` schließt offene Intervalle fälschlich aus).

## Rollout

- **T2.5D (diese Tranche):** `core.roster_membership` + `meta.roster_event` + `mart.roster_current_v1` + `mart.roster_history_v1` + `execute_core_roster_load`. Tier-A: `(nflverse_bulk, rosters)`. Tier-B Cross-Check: `(official_context_web, rosters)` — fixture-driven analog zu Teams/Games/Players.
- **T2.6E:** Player-Profil konsumiert `mart.roster_history_v1` als Timeline.
- **T2.7 (optional):** Erweiterung um echte System-Time-Spalten, falls sich im Betrieb Lücken in der Rekonstruktion zeigen.

## Offene Punkte

- **Jersey-Number-Stabilität:** Wenn ein Spieler innerhalb eines Intervalls die Trikotnummer wechselt (selten, aber real), legen wir aktuell ein neues Intervall an oder akzeptieren wir Drift im `jersey_number`-Feld? Entscheidung: **neues Intervall**, weil Jersey-Number im Betrieb als Identitätsattribut wahrgenommen wird und in Play-by-Play-Daten joint.
- **Position-Wechsel innerhalb eines Intervalls:** gleiche Logik wie Jersey-Number — Position-Wechsel bricht das Intervall.
- **Fremde Ligen (XFL, CFL, IFAF):** außer Scope bis v1.0; `core.roster_membership` hat keinen Liga-Diskriminator. Falls später benötigt, wird `league_id` zusätzlich zum Primärschlüssel — kein Breaking Change für NFL-only-Konsumenten.
