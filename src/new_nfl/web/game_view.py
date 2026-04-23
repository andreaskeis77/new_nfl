"""Read service for the T2.6F Game-Detail Pre/Post view (ADR-0029).

Exposes one bundle call ``get_game_detail(settings, game_id)`` that merges
four mart slices into a single ``GameDetail`` dataclass:

* ``mart.game_overview_v1`` — game meta (teams, kickoff, venue, score,
  ``is_completed``, ``winner_team``, ``overtime``). Drives the Pre vs.
  Post rendering path.
* ``mart.team_stats_weekly_v1`` — per-team weekly line for this exact
  ``(season, week, team_id)`` (post-game) plus the running form entering
  the game (``season = ?, week < ?`` aggregated to W–L and averages).
* ``mart.player_stats_weekly_v1`` — top-N boxscore per team ranked by
  ``total_yards``.

Missing marts degrade gracefully: each slice returns ``None`` or an
empty tuple so the template can switch between Pre-Game (no final
score), Post-Game (score + boxscore) and partially-seeded snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import duckdb

from new_nfl.settings import Settings

_MART_GAME = "mart.game_overview_v1"
_MART_TEAM_WEEK = "mart.team_stats_weekly_v1"
_MART_PLAYER_WEEK = "mart.player_stats_weekly_v1"
_MART_TEAM = "mart.team_overview_v1"

_BOXSCORE_LIMIT = 10


@dataclass(frozen=True)
class GameMeta:
    game_id: str
    season: int
    week: int
    game_type: str | None
    gameday: date | None
    weekday: str | None
    gametime: str | None
    home_team: str
    away_team: str
    home_team_name: str | None
    away_team_name: str | None
    home_score: int | None
    away_score: int | None
    is_completed: bool
    winner_team: str | None
    overtime: int | None
    stadium: str | None
    roof: str | None
    surface: str | None

    @property
    def score_label(self) -> str:
        if self.home_score is None or self.away_score is None:
            return "—"
        return f"{self.home_score} – {self.away_score}"

    @property
    def status_label(self) -> str:
        if not self.is_completed:
            return "geplant"
        if self.overtime and self.overtime > 0:
            return "Final (OT)"
        return "Final"

    @property
    def kickoff_label(self) -> str:
        day = self.gameday.isoformat() if self.gameday is not None else "—"
        time = self.gametime or "—"
        if self.gameday is None and self.gametime is None:
            return "—"
        return f"{day} · {time}"

    @property
    def venue_label(self) -> str:
        parts = [p for p in (self.stadium, self.roof, self.surface) if p]
        return " · ".join(parts) if parts else "—"

    @property
    def matchup_label(self) -> str:
        return f"{self.away_team} @ {self.home_team}"

    @property
    def home_label(self) -> str:
        return self.home_team_name or self.home_team

    @property
    def away_label(self) -> str:
        return self.away_team_name or self.away_team

    @property
    def winner_label(self) -> str:
        if not self.is_completed:
            return "—"
        if self.winner_team is None:
            return "—"
        if self.winner_team == "TIE":
            return "Unentschieden"
        if self.winner_team == self.home_team:
            return self.home_label
        if self.winner_team == self.away_team:
            return self.away_label
        return self.winner_team


@dataclass(frozen=True)
class TeamSideForm:
    team_abbr: str
    games_played: int
    wins: int
    losses: int
    ties: int
    points_for: int | None
    points_against: int | None

    @property
    def record_label(self) -> str:
        if self.ties:
            return f"{self.wins}–{self.losses}–{self.ties}"
        return f"{self.wins}–{self.losses}"

    @property
    def avg_points_for(self) -> float | None:
        if not self.games_played or self.points_for is None:
            return None
        return self.points_for / self.games_played

    @property
    def avg_points_against(self) -> float | None:
        if not self.games_played or self.points_against is None:
            return None
        return self.points_against / self.games_played


@dataclass(frozen=True)
class TeamSideWeek:
    team_abbr: str
    points_for: int | None
    points_against: int | None
    yards_for: int | None
    yards_against: int | None
    turnovers: int | None
    penalties_for: int | None
    point_diff: int | None
    yard_diff: int | None


@dataclass(frozen=True)
class BoxscorePlayer:
    player_id: str
    display_name: str | None
    position: str | None
    passing_yards: int | None
    passing_tds: int | None
    rushing_yards: int | None
    rushing_tds: int | None
    receptions: int | None
    receiving_yards: int | None
    receiving_tds: int | None
    total_yards: int | None
    total_touchdowns: int | None

    @property
    def display_label(self) -> str:
        return self.display_name or self.player_id


@dataclass(frozen=True)
class GameDetail:
    meta: GameMeta
    home_form: TeamSideForm | None
    away_form: TeamSideForm | None
    home_week: TeamSideWeek | None
    away_week: TeamSideWeek | None
    home_boxscore: tuple[BoxscorePlayer, ...]
    away_boxscore: tuple[BoxscorePlayer, ...]

    @property
    def is_pre_game(self) -> bool:
        return not self.meta.is_completed


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


def _table_exists(con: duckdb.DuckDBPyConnection, qualified_table: str) -> bool:
    try:
        con.execute(f"DESCRIBE {qualified_table}").fetchall()
    except duckdb.Error:
        return False
    return True


def _load_meta(
    con: duckdb.DuckDBPyConnection, game_id: str
) -> GameMeta | None:
    has_team = _table_exists(con, _MART_TEAM)
    home_name_sql = "ht.team_name" if has_team else "NULL"
    away_name_sql = "at_.team_name" if has_team else "NULL"
    joins_sql = (
        f"LEFT JOIN {_MART_TEAM} ht ON ht.team_id_lower = g.home_team_lower\n"
        f"            LEFT JOIN {_MART_TEAM} at_ ON at_.team_id_lower = g.away_team_lower"
        if has_team
        else ""
    )
    try:
        row = con.execute(
            f"""
            SELECT
                g.game_id,
                g.season,
                g.week,
                g.game_type,
                g.gameday,
                g.weekday,
                g.gametime,
                g.home_team,
                g.away_team,
                {home_name_sql} AS home_team_name,
                {away_name_sql} AS away_team_name,
                g.home_score,
                g.away_score,
                g.is_completed,
                g.winner_team,
                g.overtime,
                g.stadium,
                g.roof,
                g.surface
            FROM {_MART_GAME} g
            {joins_sql}
            WHERE g.game_id_lower = LOWER(?)
            LIMIT 1
            """,
            [game_id],
        ).fetchone()
    except duckdb.Error:
        return None
    if row is None:
        return None
    return GameMeta(
        game_id=str(row[0]),
        season=int(row[1]),
        week=int(row[2]),
        game_type=row[3],
        gameday=_coerce_date(row[4]),
        weekday=row[5],
        gametime=row[6],
        home_team=str(row[7]),
        away_team=str(row[8]),
        home_team_name=row[9],
        away_team_name=row[10],
        home_score=_coerce_int(row[11]),
        away_score=_coerce_int(row[12]),
        is_completed=bool(row[13]) if row[13] is not None else False,
        winner_team=row[14],
        overtime=_coerce_int(row[15]),
        stadium=row[16],
        roof=row[17],
        surface=row[18],
    )


def _load_team_form(
    con: duckdb.DuckDBPyConnection,
    season: int,
    week: int,
    team_abbr: str,
) -> TeamSideForm | None:
    if not _table_exists(con, _MART_TEAM_WEEK):
        return None
    try:
        row = con.execute(
            f"""
            SELECT
                COUNT(*) AS games_played,
                SUM(CASE WHEN point_diff > 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN point_diff < 0 THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN point_diff = 0 THEN 1 ELSE 0 END) AS ties,
                SUM(points_for) AS points_for,
                SUM(points_against) AS points_against
            FROM {_MART_TEAM_WEEK}
            WHERE season = ?
              AND week < ?
              AND LOWER(team_id) = LOWER(?)
              AND point_diff IS NOT NULL
            """,
            [season, week, team_abbr],
        ).fetchone()
    except duckdb.Error:
        return None
    if row is None:
        return None
    games_played = _coerce_int(row[0]) or 0
    return TeamSideForm(
        team_abbr=team_abbr,
        games_played=games_played,
        wins=_coerce_int(row[1]) or 0,
        losses=_coerce_int(row[2]) or 0,
        ties=_coerce_int(row[3]) or 0,
        points_for=_coerce_int(row[4]),
        points_against=_coerce_int(row[5]),
    )


def _load_team_week(
    con: duckdb.DuckDBPyConnection,
    season: int,
    week: int,
    team_abbr: str,
) -> TeamSideWeek | None:
    if not _table_exists(con, _MART_TEAM_WEEK):
        return None
    try:
        row = con.execute(
            f"""
            SELECT
                points_for,
                points_against,
                yards_for,
                yards_against,
                turnovers,
                penalties_for,
                point_diff,
                yard_diff
            FROM {_MART_TEAM_WEEK}
            WHERE season = ?
              AND week = ?
              AND LOWER(team_id) = LOWER(?)
            LIMIT 1
            """,
            [season, week, team_abbr],
        ).fetchone()
    except duckdb.Error:
        return None
    if row is None:
        return None
    return TeamSideWeek(
        team_abbr=team_abbr,
        points_for=_coerce_int(row[0]),
        points_against=_coerce_int(row[1]),
        yards_for=_coerce_int(row[2]),
        yards_against=_coerce_int(row[3]),
        turnovers=_coerce_int(row[4]),
        penalties_for=_coerce_int(row[5]),
        point_diff=_coerce_int(row[6]),
        yard_diff=_coerce_int(row[7]),
    )


def _load_boxscore(
    con: duckdb.DuckDBPyConnection,
    season: int,
    week: int,
    team_abbr: str,
) -> tuple[BoxscorePlayer, ...]:
    if not _table_exists(con, _MART_PLAYER_WEEK):
        return ()
    try:
        rows = con.execute(
            f"""
            SELECT
                player_id,
                display_name,
                position,
                passing_yards,
                passing_tds,
                rushing_yards,
                rushing_tds,
                receptions,
                receiving_yards,
                receiving_tds,
                total_yards,
                total_touchdowns
            FROM {_MART_PLAYER_WEEK}
            WHERE season = ?
              AND week = ?
              AND LOWER(team_id) = LOWER(?)
            ORDER BY total_yards DESC NULLS LAST,
                     total_touchdowns DESC NULLS LAST,
                     display_name NULLS LAST
            LIMIT ?
            """,
            [season, week, team_abbr, _BOXSCORE_LIMIT],
        ).fetchall()
    except duckdb.Error:
        return ()
    return tuple(
        BoxscorePlayer(
            player_id=str(r[0]),
            display_name=r[1],
            position=r[2],
            passing_yards=_coerce_int(r[3]),
            passing_tds=_coerce_int(r[4]),
            rushing_yards=_coerce_int(r[5]),
            rushing_tds=_coerce_int(r[6]),
            receptions=_coerce_int(r[7]),
            receiving_yards=_coerce_int(r[8]),
            receiving_tds=_coerce_int(r[9]),
            total_yards=_coerce_int(r[10]),
            total_touchdowns=_coerce_int(r[11]),
        )
        for r in rows
    )


def get_game_detail(
    settings: Settings, game_id: str
) -> GameDetail | None:
    con = _connect(settings)
    try:
        meta = _load_meta(con, game_id)
        if meta is None:
            return None
        home_form = _load_team_form(con, meta.season, meta.week, meta.home_team)
        away_form = _load_team_form(con, meta.season, meta.week, meta.away_team)
        home_week: TeamSideWeek | None = None
        away_week: TeamSideWeek | None = None
        home_box: tuple[BoxscorePlayer, ...] = ()
        away_box: tuple[BoxscorePlayer, ...] = ()
        if meta.is_completed:
            home_week = _load_team_week(
                con, meta.season, meta.week, meta.home_team
            )
            away_week = _load_team_week(
                con, meta.season, meta.week, meta.away_team
            )
            home_box = _load_boxscore(
                con, meta.season, meta.week, meta.home_team
            )
            away_box = _load_boxscore(
                con, meta.season, meta.week, meta.away_team
            )
    finally:
        con.close()
    return GameDetail(
        meta=meta,
        home_form=home_form,
        away_form=away_form,
        home_week=home_week,
        away_week=away_week,
        home_boxscore=home_box,
        away_boxscore=away_box,
    )


__all__ = [
    "BoxscorePlayer",
    "GameDetail",
    "GameMeta",
    "TeamSideForm",
    "TeamSideWeek",
    "get_game_detail",
]
