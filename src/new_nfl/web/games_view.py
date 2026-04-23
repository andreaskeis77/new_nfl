"""Read service for the T2.6C Season/Week/Game drilldown (ADR-0029).

Three stages of a read-only drilldown over ``mart.game_overview_v1``:

* ``list_seasons`` — distinct seasons with total / completed counts.
* ``list_weeks`` — weeks of a season with total / completed counts.
* ``list_games`` — individual game rows for a season + week.

The service reads only from ``mart.*``; if the mart is missing it returns
empty tuples so the view can render an empty-state instead of raising.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import duckdb

from new_nfl.settings import Settings

_MART_TABLE = "mart.game_overview_v1"


@dataclass(frozen=True)
class SeasonSummary:
    season: int
    game_count: int
    completed_count: int
    min_week: int | None
    max_week: int | None

    @property
    def is_complete(self) -> bool:
        return self.game_count > 0 and self.game_count == self.completed_count


@dataclass(frozen=True)
class WeekSummary:
    season: int
    week: int
    game_count: int
    completed_count: int
    earliest_gameday: date | None

    @property
    def is_complete(self) -> bool:
        return self.game_count > 0 and self.game_count == self.completed_count


@dataclass(frozen=True)
class GameRow:
    game_id: str
    season: int
    week: int
    gameday: date | None
    weekday: str | None
    gametime: str | None
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    is_completed: bool
    winner_team: str | None
    stadium: str | None
    roof: str | None
    surface: str | None

    @property
    def label(self) -> str:
        return f"{self.away_team} @ {self.home_team}"

    @property
    def score_label(self) -> str:
        if self.home_score is None or self.away_score is None:
            return "—"
        return f"{self.away_score} – {self.home_score}"

    @property
    def status(self) -> str:
        if self.is_completed:
            return "final"
        return "scheduled"


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


def _connect_read_only(settings: Settings) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(settings.db_path))


def list_seasons(settings: Settings) -> tuple[SeasonSummary, ...]:
    con = _connect_read_only(settings)
    try:
        try:
            rows = con.execute(
                f"""
                SELECT
                    season,
                    COUNT(*) AS game_count,
                    SUM(CASE WHEN is_completed THEN 1 ELSE 0 END) AS completed_count,
                    MIN(week) AS min_week,
                    MAX(week) AS max_week
                FROM {_MART_TABLE}
                WHERE season IS NOT NULL
                GROUP BY season
                ORDER BY season DESC
                """
            ).fetchall()
        except duckdb.Error:
            return ()
    finally:
        con.close()
    return tuple(
        SeasonSummary(
            season=int(r[0]),
            game_count=int(r[1]),
            completed_count=int(r[2] or 0),
            min_week=_coerce_int(r[3]),
            max_week=_coerce_int(r[4]),
        )
        for r in rows
    )


def list_weeks(settings: Settings, season: int) -> tuple[WeekSummary, ...]:
    con = _connect_read_only(settings)
    try:
        try:
            rows = con.execute(
                f"""
                SELECT
                    season,
                    week,
                    COUNT(*) AS game_count,
                    SUM(CASE WHEN is_completed THEN 1 ELSE 0 END) AS completed_count,
                    MIN(gameday) AS earliest_gameday
                FROM {_MART_TABLE}
                WHERE season = ? AND week IS NOT NULL
                GROUP BY season, week
                ORDER BY week
                """,
                [season],
            ).fetchall()
        except duckdb.Error:
            return ()
    finally:
        con.close()
    return tuple(
        WeekSummary(
            season=int(r[0]),
            week=int(r[1]),
            game_count=int(r[2]),
            completed_count=int(r[3] or 0),
            earliest_gameday=_coerce_date(r[4]),
        )
        for r in rows
    )


def list_games(settings: Settings, season: int, week: int) -> tuple[GameRow, ...]:
    con = _connect_read_only(settings)
    try:
        try:
            rows = con.execute(
                f"""
                SELECT
                    game_id,
                    season,
                    week,
                    gameday,
                    weekday,
                    gametime,
                    home_team,
                    away_team,
                    home_score,
                    away_score,
                    is_completed,
                    winner_team,
                    stadium,
                    roof,
                    surface
                FROM {_MART_TABLE}
                WHERE season = ? AND week = ?
                ORDER BY
                    gameday NULLS LAST,
                    gametime NULLS LAST,
                    home_team
                """,
                [season, week],
            ).fetchall()
        except duckdb.Error:
            return ()
    finally:
        con.close()
    return tuple(
        GameRow(
            game_id=str(r[0]),
            season=int(r[1]),
            week=int(r[2]),
            gameday=_coerce_date(r[3]),
            weekday=r[4],
            gametime=r[5],
            home_team=str(r[6]),
            away_team=str(r[7]),
            home_score=_coerce_int(r[8]),
            away_score=_coerce_int(r[9]),
            is_completed=bool(r[10]),
            winner_team=r[11],
            stadium=r[12],
            roof=r[13],
            surface=r[14],
        )
        for r in rows
    )


__all__ = [
    "GameRow",
    "SeasonSummary",
    "WeekSummary",
    "list_games",
    "list_seasons",
    "list_weeks",
]
