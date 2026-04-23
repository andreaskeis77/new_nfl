"""Read service for the T2.6D Team-Profil (ADR-0029).

Exposes two read flows over ``mart.*``:

* ``list_teams`` — teams-index rows with stammdaten + latest-season summary.
* ``get_team_profile`` — full detail bundle (stammdaten, current roster,
  season-stats history, per-season game history) for a single team.

All queries read exclusively from ``mart.team_overview_v1``,
``mart.roster_current_v1``, ``mart.team_stats_season_v1`` and
``mart.game_overview_v1``. When any mart is missing the corresponding
slice returns empty tuples / ``None`` so pages can render an empty-state
instead of raising.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import duckdb

from new_nfl.settings import Settings

_MART_TEAM = "mart.team_overview_v1"
_MART_ROSTER = "mart.roster_current_v1"
_MART_TEAM_STATS = "mart.team_stats_season_v1"
_MART_GAME = "mart.game_overview_v1"


@dataclass(frozen=True)
class TeamCard:
    team_id: str
    team_abbr: str
    team_name: str
    team_nick: str | None
    team_conference: str | None
    team_division: str | None
    team_color: str | None
    is_active: bool
    first_season: int | None
    last_season: int | None
    latest_season: int | None
    latest_points_for: int | None
    latest_points_against: int | None
    latest_games_played: int | None

    @property
    def division_label(self) -> str:
        parts = [p for p in (self.team_conference, self.team_division) if p]
        return " ".join(parts) if parts else "—"


@dataclass(frozen=True)
class TeamMeta:
    team_id: str
    team_abbr: str
    team_name: str
    team_nick: str | None
    team_conference: str | None
    team_division: str | None
    team_color: str | None
    team_color2: str | None
    first_season: int | None
    last_season: int | None
    is_active: bool

    @property
    def division_label(self) -> str:
        parts = [p for p in (self.team_conference, self.team_division) if p]
        return " ".join(parts) if parts else "—"

    @property
    def status_label(self) -> str:
        return "aktiv" if self.is_active else "inaktiv"


@dataclass(frozen=True)
class RosterEntry:
    player_id: str
    display_name: str | None
    position: str | None
    jersey_number: int | None
    status: str | None
    season: int | None
    valid_from_week: int | None

    @property
    def display_label(self) -> str:
        return self.display_name or self.player_id

    @property
    def jersey_label(self) -> str:
        if self.jersey_number is None:
            return "—"
        return f"#{self.jersey_number}"


@dataclass(frozen=True)
class TeamSeasonStatsRow:
    season: int
    games_played: int | None
    points_for: int | None
    points_against: int | None
    yards_for: int | None
    yards_against: int | None
    turnovers: int | None
    penalties_for: int | None
    point_diff: int | None
    yard_diff: int | None

    @property
    def points_per_game(self) -> float | None:
        if not self.games_played or self.points_for is None:
            return None
        return self.points_for / self.games_played


@dataclass(frozen=True)
class TeamGameRow:
    game_id: str
    season: int
    week: int
    gameday: date | None
    gametime: str | None
    is_home: bool
    opponent: str
    score_for: int | None
    score_against: int | None
    is_completed: bool
    winner_team: str | None
    stadium: str | None

    @property
    def venue_label(self) -> str:
        return "Heim" if self.is_home else "Auswärts"

    @property
    def score_label(self) -> str:
        if self.score_for is None or self.score_against is None:
            return "—"
        return f"{self.score_for} – {self.score_against}"

    @property
    def outcome(self) -> str:
        if not self.is_completed or self.score_for is None or self.score_against is None:
            return "scheduled"
        if self.winner_team == "TIE":
            return "tie"
        if self.score_for > self.score_against:
            return "win"
        if self.score_for < self.score_against:
            return "loss"
        return "tie"


@dataclass(frozen=True)
class TeamProfile:
    meta: TeamMeta
    roster: tuple[RosterEntry, ...]
    season_stats: tuple[TeamSeasonStatsRow, ...]
    games: tuple[TeamGameRow, ...]
    selected_season: int | None
    available_seasons: tuple[int, ...]

    @property
    def roster_size(self) -> int:
        return len(self.roster)

    @property
    def record_label(self) -> str:
        wins = losses = ties = 0
        for g in self.games:
            if g.outcome == "win":
                wins += 1
            elif g.outcome == "loss":
                losses += 1
            elif g.outcome == "tie":
                ties += 1
        if ties:
            return f"{wins}–{losses}–{ties}"
        return f"{wins}–{losses}"


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _connect(settings: Settings) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(settings.db_path))


def _list_teams_fallback(
    con: duckdb.DuckDBPyConnection,
) -> tuple[TeamCard, ...]:
    try:
        rows = con.execute(
            f"""
            SELECT
                team_id,
                team_abbr,
                team_name,
                team_nick,
                team_conference,
                team_division,
                team_color,
                is_active,
                first_season,
                last_season
            FROM {_MART_TEAM}
            ORDER BY
                team_conference NULLS LAST,
                team_division NULLS LAST,
                team_name
            """
        ).fetchall()
    except duckdb.Error:
        return ()
    return tuple(
        TeamCard(
            team_id=str(r[0]),
            team_abbr=str(r[1]),
            team_name=str(r[2]),
            team_nick=r[3],
            team_conference=r[4],
            team_division=r[5],
            team_color=r[6],
            is_active=bool(r[7]) if r[7] is not None else True,
            first_season=_coerce_int(r[8]),
            last_season=_coerce_int(r[9]),
            latest_season=None,
            latest_points_for=None,
            latest_points_against=None,
            latest_games_played=None,
        )
        for r in rows
    )


def list_teams(settings: Settings) -> tuple[TeamCard, ...]:
    con = _connect(settings)
    try:
        try:
            rows = con.execute(
                f"""
                WITH latest AS (
                    SELECT
                        team_id,
                        season,
                        games_played,
                        points_for,
                        points_against,
                        ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY season DESC) AS rn
                    FROM {_MART_TEAM_STATS}
                )
                SELECT
                    t.team_id,
                    t.team_abbr,
                    t.team_name,
                    t.team_nick,
                    t.team_conference,
                    t.team_division,
                    t.team_color,
                    t.is_active,
                    t.first_season,
                    t.last_season,
                    l.season AS latest_season,
                    l.points_for AS latest_points_for,
                    l.points_against AS latest_points_against,
                    l.games_played AS latest_games_played
                FROM {_MART_TEAM} t
                LEFT JOIN latest l ON l.team_id = t.team_id AND l.rn = 1
                ORDER BY
                    t.team_conference NULLS LAST,
                    t.team_division NULLS LAST,
                    t.team_name
                """
            ).fetchall()
        except duckdb.Error:
            return _list_teams_fallback(con)
    finally:
        con.close()
    return tuple(
        TeamCard(
            team_id=str(r[0]),
            team_abbr=str(r[1]),
            team_name=str(r[2]),
            team_nick=r[3],
            team_conference=r[4],
            team_division=r[5],
            team_color=r[6],
            is_active=bool(r[7]) if r[7] is not None else True,
            first_season=_coerce_int(r[8]),
            last_season=_coerce_int(r[9]),
            latest_season=_coerce_int(r[10]),
            latest_points_for=_coerce_int(r[11]),
            latest_points_against=_coerce_int(r[12]),
            latest_games_played=_coerce_int(r[13]),
        )
        for r in rows
    )


def _load_meta(
    con: duckdb.DuckDBPyConnection, team_key: str
) -> TeamMeta | None:
    try:
        row = con.execute(
            f"""
            SELECT
                team_id,
                team_abbr,
                team_name,
                team_nick,
                team_conference,
                team_division,
                team_color,
                team_color2,
                first_season,
                last_season,
                is_active
            FROM {_MART_TEAM}
            WHERE team_id_lower = LOWER(?)
               OR team_abbr_lower = LOWER(?)
            ORDER BY
                CASE WHEN team_abbr_lower = LOWER(?) THEN 0 ELSE 1 END,
                team_name
            LIMIT 1
            """,
            [team_key, team_key, team_key],
        ).fetchone()
    except duckdb.Error:
        return None
    if row is None:
        return None
    return TeamMeta(
        team_id=str(row[0]),
        team_abbr=str(row[1]),
        team_name=str(row[2]),
        team_nick=row[3],
        team_conference=row[4],
        team_division=row[5],
        team_color=row[6],
        team_color2=row[7],
        first_season=_coerce_int(row[8]),
        last_season=_coerce_int(row[9]),
        is_active=bool(row[10]) if row[10] is not None else True,
    )


def _load_roster(
    con: duckdb.DuckDBPyConnection, team_id: str
) -> tuple[RosterEntry, ...]:
    try:
        rows = con.execute(
            f"""
            SELECT
                player_id,
                display_name,
                position,
                jersey_number,
                status,
                season,
                valid_from_week
            FROM {_MART_ROSTER}
            WHERE team_id_lower = LOWER(?)
            ORDER BY
                position NULLS LAST,
                jersey_number NULLS LAST,
                display_name NULLS LAST,
                player_id
            """,
            [team_id],
        ).fetchall()
    except duckdb.Error:
        return ()
    return tuple(
        RosterEntry(
            player_id=str(r[0]),
            display_name=r[1],
            position=r[2],
            jersey_number=_coerce_int(r[3]),
            status=r[4],
            season=_coerce_int(r[5]),
            valid_from_week=_coerce_int(r[6]),
        )
        for r in rows
    )


def _load_season_stats(
    con: duckdb.DuckDBPyConnection, team_id: str
) -> tuple[TeamSeasonStatsRow, ...]:
    try:
        rows = con.execute(
            f"""
            SELECT
                season,
                games_played,
                points_for,
                points_against,
                yards_for,
                yards_against,
                turnovers,
                penalties_for,
                point_diff,
                yard_diff
            FROM {_MART_TEAM_STATS}
            WHERE team_id = ?
            ORDER BY season DESC
            """,
            [team_id],
        ).fetchall()
    except duckdb.Error:
        return ()
    return tuple(
        TeamSeasonStatsRow(
            season=int(r[0]),
            games_played=_coerce_int(r[1]),
            points_for=_coerce_int(r[2]),
            points_against=_coerce_int(r[3]),
            yards_for=_coerce_int(r[4]),
            yards_against=_coerce_int(r[5]),
            turnovers=_coerce_int(r[6]),
            penalties_for=_coerce_int(r[7]),
            point_diff=_coerce_int(r[8]),
            yard_diff=_coerce_int(r[9]),
        )
        for r in rows
    )


def _load_game_seasons(
    con: duckdb.DuckDBPyConnection, team_abbr: str
) -> tuple[int, ...]:
    try:
        rows = con.execute(
            f"""
            SELECT DISTINCT season
            FROM {_MART_GAME}
            WHERE home_team_lower = LOWER(?) OR away_team_lower = LOWER(?)
            ORDER BY season DESC
            """,
            [team_abbr, team_abbr],
        ).fetchall()
    except duckdb.Error:
        return ()
    return tuple(int(r[0]) for r in rows if r[0] is not None)


def _load_games(
    con: duckdb.DuckDBPyConnection, team_abbr: str, season: int
) -> tuple[TeamGameRow, ...]:
    try:
        rows = con.execute(
            f"""
            SELECT
                game_id,
                season,
                week,
                gameday,
                gametime,
                home_team,
                away_team,
                home_score,
                away_score,
                is_completed,
                winner_team,
                stadium
            FROM {_MART_GAME}
            WHERE season = ?
              AND (home_team_lower = LOWER(?) OR away_team_lower = LOWER(?))
            ORDER BY week, gameday NULLS LAST, gametime NULLS LAST
            """,
            [season, team_abbr, team_abbr],
        ).fetchall()
    except duckdb.Error:
        return ()
    games: list[TeamGameRow] = []
    abbr_lower = team_abbr.lower()
    for r in rows:
        home_team = str(r[5])
        away_team = str(r[6])
        home_score = _coerce_int(r[7])
        away_score = _coerce_int(r[8])
        is_home = home_team.lower() == abbr_lower
        score_for = home_score if is_home else away_score
        score_against = away_score if is_home else home_score
        opponent = away_team if is_home else home_team
        games.append(
            TeamGameRow(
                game_id=str(r[0]),
                season=int(r[1]),
                week=int(r[2]),
                gameday=_coerce_date(r[3]),
                gametime=r[4],
                is_home=is_home,
                opponent=opponent,
                score_for=score_for,
                score_against=score_against,
                is_completed=bool(r[9]),
                winner_team=r[10],
                stadium=r[11],
            )
        )
    return tuple(games)


def get_team_profile(
    settings: Settings,
    team_key: str,
    *,
    season: int | None = None,
) -> TeamProfile | None:
    con = _connect(settings)
    try:
        meta = _load_meta(con, team_key)
        if meta is None:
            return None
        roster = _load_roster(con, meta.team_id)
        season_stats = _load_season_stats(con, meta.team_id)
        available = _load_game_seasons(con, meta.team_abbr)
        selected: int | None = None
        if season is not None and season in available:
            selected = season
        elif available:
            selected = available[0]
        games: tuple[TeamGameRow, ...] = ()
        if selected is not None:
            games = _load_games(con, meta.team_abbr, selected)
    finally:
        con.close()
    return TeamProfile(
        meta=meta,
        roster=roster,
        season_stats=season_stats,
        games=games,
        selected_season=selected,
        available_seasons=available,
    )


__all__ = [
    "RosterEntry",
    "TeamCard",
    "TeamGameRow",
    "TeamMeta",
    "TeamProfile",
    "TeamSeasonStatsRow",
    "get_team_profile",
    "list_teams",
]
