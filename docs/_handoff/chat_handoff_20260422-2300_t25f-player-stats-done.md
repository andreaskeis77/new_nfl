# Chat-Handoff 2026-04-22 23:00 — T2.5F Player-Stats-Aggregate abgeschlossen

## Trigger

§2.1 „Tranche-Abschluss + thematischer Wechsel zwischen Substreams": **T2.5F ist vollständig abgeschlossen** (Player-Stats-Slice, `core.player_stats_weekly`, drei Marts `mart.player_stats_weekly_v1` + `mart.player_stats_season_v1` + `mart.player_stats_career_v1`, Multi-Position-Tolerance). Damit ist **Phase T2.5 (domänen-kanonische Core-Loads) vollständig** — alle sechs Domänen (Teams, Games, Players, Rosters, Team-Stats, Player-Stats) haben jetzt kanonische `core.*`-Tabellen mit Tier-A/B-Cross-Check-Semantik und versionierten Read-Modellen. Der nächste Bolzen **T2.6A — UI-Fundament** ist qualitativ anders: **erster UI-Tranche**, ADR-0030 wird `Accepted`, Tailwind-Build-Chain, Jinja-Templates, htmx, Observable Plot — ein dedizierter Substream-Wechsel, der eine eigene Chat-Session verdient.

Zusätzlich §2.1 „Kontext-Druck": Diese Session hat T2.5D → T2.5E → T2.5F in einem Zug ausgeführt (autonomer Modus). Drei Domänen-Tranchen, sechs Commits, +24 Testcases (159 → 183), zwei aggregierende Domänen neu, bitemporale Modellierung etabliert, drei-Mart-Rebuild-Pattern eingeführt. Vor der UI-Tranche ist ein sauberer Cut sinnvoll.

## Was wurde in dieser Session erreicht

### T2.5D — Rosters-Domäne (erste bitemporale Domäne) (Commits `7ff2116`, `57badae`)
- Slices `(nflverse_bulk, rosters)` primär + `(official_context_web, rosters)` Cross-Check.
- `core.roster_membership` mit bitemporalen Intervall-Spalten `valid_from_week`/`valid_to_week` (Business-Time) neben System-Time `_loaded_at`.
- Interval-Bau über CTE-Kaskade mit `week - ROW_NUMBER()`-Gap-Trick; `valid_to_week IS NULL` gdw. offene Mitgliedschaft.
- `meta.roster_event`-Stream mit `signed`/`released`/`trade`/`promoted`/`demoted`; konservative Trade-Heuristik (lücken-frei → `trade`, Lücke → `released`+`signed`).
- Tier-B-Diskrepanzen auf `position`/`jersey_number`/`status` öffnen `meta.quarantine_case` mit `scope_ref=PLAYER:TEAM:SEASON:Wxx`.
- Zwei Read-Modelle: `mart.roster_current_v1` (nur offene Intervalle) + `mart.roster_history_v1` (volle Timeline + `is_open`).
- ADR-0032 → `Proposed`.

### T2.5E — Team-Stats-Aggregate (erste aggregierende Domäne) (Commits `791b828`, `78ccccd`)
- Slices `(nflverse_bulk, team_stats_weekly)` + `(official_context_web, team_stats_weekly)`.
- `core.team_stats_weekly` im Grain `(season, week, team_id)` mit Dedupe per `_loaded_at DESC` (letzter Load gewinnt).
- Tier-B-Cross-Check auf `points_for`/`points_against`/`yards_for`/`turnovers`; Quarantäne-Scope `{team_id}:{season}:W{week:02d}`.
- Zwei Read-Modelle: `mart.team_stats_weekly_v1` (Passthrough + abgeleitete Differenzen) + `mart.team_stats_season_v1` (bye-week-tolerant via `COUNT(points_for)`).
- `CoreTeamStatsLoadResult` erfüllt `CoreLoadResultLike`.

### T2.5F — Player-Stats-Aggregate (zweite aggregierende Domäne) (Commits `d402adb`, `f5b5f6d`)
- Slices `(nflverse_bulk, player_stats_weekly)` + `(official_context_web, player_stats_weekly)`.
- `core.player_stats_weekly` im Grain `(season, week, player_id)`, Dedupe per `_loaded_at DESC`.
- Tier-B-Cross-Check auf `passing_yards`/`rushing_yards`/`receiving_yards`/`touchdowns`; Quarantäne-Scope `{player_id}:{season}:W{week:02d}`.
- **Drei Read-Modelle** in einer Promoter-Transaktion:
  - `mart.player_stats_weekly_v1` — Passthrough + abgeleitetes `total_yards`/`total_touchdowns`.
  - `mart.player_stats_season_v1` — GROUP BY `(season, player_id)` mit `MODE(position) AS primary_position` (Multi-Position-tolerant), bye-tolerant via `COUNT(CASE WHEN <has-any-stat>)`.
  - `mart.player_stats_career_v1` — GROUP BY `player_id` über alle Saisons mit `MIN/MAX(season)` und `COUNT(DISTINCT CASE WHEN <has-any-stat> THEN season END) AS seasons_played`.
- **Multi-Position-Edge-Case Taysom Hill** (QB-W1/TE-W2/RB-W3 2023 + TE-W1 2024) im Test verankert: Season-Aggregat positions-agnostisch, Career-Aggregat über Saisons; `primary_position` via `MODE()`, `current_position` via LEFT-JOIN auf `core.player`.
- Best-effort LEFT-JOIN auf `core.player`/`core.team` via DESCRIBE-Fallback (NULL wenn Quelle fehlt) — jetzt einheitlich in allen Marts.
- `CorePlayerStatsLoadResult` erfüllt `CoreLoadResultLike`; Round-Trip-Test.

### Test-Suite
- **183 Tests grün** (von 159 am Session-Start der T2.5D-Fortsetzung).
- Neu: `tests/test_rosters.py` (8), `tests/test_team_stats.py` (8), `tests/test_player_stats.py` (8).

### Doku
- `PROJECT_STATE.md`, `T2_3_PLAN.md` §4, `LESSONS_LEARNED.md` nach jeder Tranche aktualisiert.
- ADR-0032 bleibt `Proposed` bis zur ersten Operator-Validierung realer Roster-Daten.
- Lessons-Learned-Drafts T2.5D/T2.5E/T2.5F liegen zur Operator-Freigabe.

## Aktueller Arbeitsstand

- **Phase:** T2.5 vollständig abgeschlossen, Übergang zu T2.6 (Web-UI v1.0).
- **Letzter erfolgreicher Pflichtpfad:** `pytest` 183/183 grün.
- **Letzter Commit:** `f5b5f6d docs: T2.5F closed + Lessons Learned + next bolt T2.6A` (HEAD `origin/main`).
- **Nächster konkreter Schritt:** **T2.6A — Tailwind-Setup und Komponenten-Skelett** gemäß `T2_3_PLAN.md` §5.
- **Git-Status:** sauber, alle Commits gepusht nach `origin/main`.

## Was ist offen / unklar / Risiko

### Direkt für T2.6A
- **ADR-0030 (UI Stack: Jinja + Tailwind + htmx + Observable Plot)** steht noch `Proposed`. Erste Aktion in T2.6A: final `Accepted` mit Implementierungs-Notizen.
- **Windows-kompatible Node-Toolchain-Wahl**: Tailwind v3 oder v4? Via `npx` ohne globale Installation? CSS-Output committet oder als Build-Artefakt gitignored?
- **`position_is_known`-Bootstrap-Gap aus T2.5C** ist immer noch offen — UI-Tranche muss entweder dreiwertige Logik rendern oder `bootstrap_local_environment` erweitert eine Default-Version der Ontologie zu aktivieren. Erste konkrete UI-Anwendung, die davon betroffen ist: T2.6E Player-Profil.

### Backlog aus T2.5D/E/F-Lessons
- **`meta.adapter_slice` als Runtime-Registry**: Slices leben nur im Code. Für T2.6G (Provenance-Drilldown) zu lösen.
- **Aggregierende Marts ohne expliziten Saison-Filter**: `team_stats_season_v1` und `player_stats_season_v1` vertrauen auf Stage-Filter; Playoff-Trennung muss entweder über `week <= 18` oder `season_type`-Spalte gelöst werden. Dokumentiert, aber nicht implementiert.
- **Schema-DESCRIBE-Fallback ohne Cache**: neun Marts rufen pro Rebuild DESCRIBE auf `core.team`/`core.player`. Skaliert nicht linear mit T2.6-UI-Requests — UI-Layer muss Schema-Cache auf Settings-Ebene einführen, nicht pro Request DESCRIBE machen.
- **`MODE(position)` bei ex-aequo-Häufigkeit nicht-deterministisch**: Season-Mart dokumentiert, UI muss Sortier-Regel via Ontologie lesen (Offensive vor Defensive), nicht via SQL-Tie-Breaking.
- **Defense-Stats-Grain vertagt**: Career-Mart-`seasons_played` würde für Defensive-Spieler immer 0 liefern. v1.0 akzeptabel, aber Signal für T2.5G (falls nötig) oder späteres Scope-Upgrade.
- **Trade-Heuristik konservativ**: `released+signed` bei Lücke statt `trade`. Fehldiagnose bei echten Trades während IR/Bye. Akzeptabel für v1.0, genauer ausschließen via Transaktionen-Quelle in späterer Tranche.

### Backlog aus T2.5C-Lessons (bleibt)
- **ADR-0030 final `Accepted`** in T2.6A.
- **Ontology-Auto-Aktivierung im Bootstrap** in T2.6A lösen oder dreiwertige UI-Logik begründen.

## Starter-Prompt für die nächste Session

> NEW NFL — Fortsetzung nach abgeschlossener Phase T2.5 (alle sechs Domänen kanonisch, drei Mart-Cluster + zwei Bitemporal-Marts + neun Marts insgesamt).
>
> **Kontext:** Stand `origin/main` bei Commit `f5b5f6d`, 183 Tests grün, alle sechs domänen-kanonischen Core-Loads implementiert (Teams, Games, Players, Rosters-bitemporal, Team-Stats-aggregiert, Player-Stats-aggregiert). Lessons Learned T2.5D/E/F liegen als Drafts vor, warten auf Operator-Freigabe.
>
> **Nächster Bolt:** T2.6A — UI-Fundament
> 1. ADR-0030 final `Accepted` mit Implementierungs-Notizen zur Stack-Wahl Jinja + Tailwind + htmx + Observable Plot.
> 2. Tailwind-Build-Chain in `ui/` oder `src/new_nfl/web/` — Windows-kompatibel, möglichst ohne globale Node-Installation.
> 3. Jinja-Layout `base.html` mit `<Card>`/`<StatTile>`/`<DataTable>`/`<FreshnessBadge>`/`<Breadcrumb>`/`<EmptyState>`-Komponenten.
> 4. Inter + JetBrains Mono self-hosted. Dark/Light-Toggle. Lucide-Icon-Sprite.
> 5. Der Lint-Test gegen `core.*`/`stg.*`/`raw/` bleibt aktiv — alle neuen UI-Module lesen ausschließlich aus `mart.*` (ADR-0029).
>
> **Pflichtlektüre vor Beginn:**
> - `docs/PROJECT_STATE.md`
> - `docs/T2_3_PLAN.md` §5
> - `docs/adr/0030-ui-stack.md` (Status: Proposed → Accepted in dieser Session)
> - `docs/UI_STYLE_GUIDE_v0_1.md`
> - `docs/LESSONS_LEARNED.md` (neueste drei Einträge: T2.5F, T2.5E, T2.5D)
>
> **Qualitätsgates:**
> - `pytest` grün zwischen Bolzen.
> - Keine neuen ruff-Warnungen auf UI-scoped Dateien.
> - AST-Lint-Test (`mart.*`-only in Read-Pfaden) bleibt grün und erweitert sich auf neue UI-Module.
> - Jeder UI-View liest ausschließlich aus einem explizit genannten Mart.
>
> **Arbeitsrhythmus:**
> - ADR-0030 Accepted voranstellen.
> - Build-Tool-Setup in eigenem Commit.
> - Komponenten-Skelett in zweitem Commit.
> - Doku-Updates (PROJECT_STATE/T2_3_PLAN/LESSONS_LEARNED) in drittem Commit.
> - Push nach jedem Commit.

## Referenzen

- Manifest §2.1 (Chat-Handoff-Trigger), §3.9 (Evidence-first), §3.13 (Evidence-as-Code), §3.7 (ADRs unter Implementierungs-Druck).
- System-Konzept §2 (VPS-Deploy vertagt), §6 (UI-Pfad).
- ADR-0029 (Read-Modell-Trennung), ADR-0030 (UI Stack — Proposed), ADR-0031 (Adapter-Slice-Strategy), ADR-0032 (Bitemporale Roster-Modellierung — Proposed).
- Letzter Handoff: `chat_handoff_20260422-1500_t25c-players-and-first-real-dedupe-done.md`.
