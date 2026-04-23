"""Read service for the T2.6E Player-Profil (ADR-0029).

Exposes two read flows over ``mart.*``:

* ``list_players`` — paginated player-index rows with stammdaten + current
  roster assignment.
* ``get_player_profile`` — full detail bundle (stammdaten, career totals,
  season history, roster timeline) for a single player.

All queries read exclusively from ``mart.player_overview_v1``,
``mart.player_stats_career_v1``, ``mart.player_stats_season_v1`` and
``mart.roster_history_v1``. When any mart is missing the corresponding
slice returns empty tuples / ``None`` so pages can render an empty-state
instead of raising.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import duckdb

from new_nfl.settings import Settings

_MART_PLAYER = "mart.player_overview_v1"
_MART_ROSTER_HISTORY = "mart.roster_history_v1"
_MART_CAREER = "mart.player_stats_career_v1"
_MART_SEASON = "mart.player_stats_season_v1"
_MART_TEAM = "mart.team_overview_v1"


@dataclass(frozen=True)
class PlayerCard:
    player_id: str
    display_name: str | None
    full_name: str | None
    position: str | None
    current_team_id: str | None
    current_team_abbr: str | None
    jersey_number: int | None
    rookie_season: int | None
    last_season: int | None
    is_active: bool

    @property
    def display_label(self) -> str:
        return self.display_name or self.full_name or self.player_id

    @property
    def jersey_label(self) -> str:
        if self.jersey_number is None:
            return "—"
        return f"#{self.jersey_number}"

    @property
    def status_label(self) -> str:
        return "aktiv" if self.is_active else "inaktiv"

    @property
    def seasons_label(self) -> str:
        if self.rookie_season is None and self.last_season is None:
            return "—"
        start = str(self.rookie_season) if self.rookie_season is not None else "?"
        if self.is_active or self.last_season is None:
            return f"{start}–heute"
        return f"{start}–{self.last_season}"


@dataclass(frozen=True)
class PlayerMeta:
    player_id: str
    display_name: str | None
    full_name: str | None
    first_name: str | None
    last_name: str | None
    birth_date: date | None
    position: str | None
    height: int | None
    weight: int | None
    college_name: str | None
    rookie_season: int | None
    last_season: int | None
    current_team_id: str | None
    current_team_abbr: str | None
    current_team_name: str | None
    jersey_number: int | None
    draft_club: str | None
    draft_year: int | None
    draft_round: int | None
    draft_pick: int | None
    status: str | None
    is_active: bool

    @property
    def display_label(self) -> str:
        return self.display_name or self.full_name or self.player_id

    @property
    def status_label(self) -> str:
        return "aktiv" if self.is_active else "inaktiv"

    @property
    def jersey_label(self) -> str:
        if self.jersey_number is None:
            return "—"
        return f"#{self.jersey_number}"

    @property
    def draft_label(self) -> str:
        if self.draft_year is None:
            return "—"
        parts: list[str] = [str(self.draft_year)]
        if self.draft_round is not None and self.draft_pick is not None:
            parts.append(f"R{self.draft_round}·P{self.draft_pick}")
        elif self.draft_round is not None:
            parts.append(f"R{self.draft_round}")
        if self.draft_club:
            parts.append(self.draft_club)
        return " · ".join(parts)

    @property
    def height_label(self) -> str:
        if self.height is None:
            return "—"
        feet, inches = divmod(int(self.height), 12)
        return f"{feet}'{inches}\""

    @property
    def weight_label(self) -> str:
        if self.weight is None:
            return "—"
        return f"{int(self.weight)} lbs"

    @property
    def birth_label(self) -> str:
        if self.birth_date is None:
            return "—"
        return self.birth_date.isoformat()

    @property
    def seasons_label(self) -> str:
        if self.rookie_season is None and self.last_season is None:
            return "—"
        start = str(self.rookie_season) if self.rookie_season is not None else "?"
        if self.is_active or self.last_season is None:
            return f"{start}–heute"
        return f"{start}–{self.last_season}"


@dataclass(frozen=True)
class PlayerCareerSnapshot:
    first_season: int | None
    last_season: int | None
    seasons_played: int | None
    games_played: int | None
    passing_yards: int | None
    passing_tds: int | None
    interceptions: int | None
    rushing_yards: int | None
    rushing_tds: int | None
    receptions: int | None
    receiving_yards: int | None
    receiving_tds: int | None
    total_yards: int | None
    total_touchdowns: int | None
    fumbles_lost: int | None
    current_position: str | None

    @property
    def span_label(self) -> str:
        if self.first_season is None and self.last_season is None:
            return "—"
        start = str(self.first_season) if self.first_season is not None else "?"
        end = str(self.last_season) if self.last_season is not None else "?"
        if start == end:
            return start
        return f"{start}–{end}"


@dataclass(frozen=True)
class PlayerSeasonStatsRow:
    season: int
    primary_position: str | None
    games_played: int | None
    passing_yards: int | None
    passing_tds: int | None
    interceptions: int | None
    rushing_yards: int | None
    rushing_tds: int | None
    receptions: int | None
    receiving_yards: int | None
    receiving_tds: int | None
    total_yards: int | None
    total_touchdowns: int | None
    fumbles_lost: int | None


@dataclass(frozen=True)
class PlayerRosterInterval:
    season: int
    team_id: str
    team_abbr: str | None
    team_name: str | None
    position: str | None
    jersey_number: int | None
    status: str | None
    valid_from_week: int | None
    valid_to_week: int | None
    is_open: bool

    @property
    def team_label(self) -> str:
        return self.team_abbr or self.team_id

    @property
    def jersey_label(self) -> str:
        if self.jersey_number is None:
            return "—"
        return f"#{self.jersey_number}"

    @property
    def week_range_label(self) -> str:
        start = (
            str(self.valid_from_week) if self.valid_from_week is not None else "?"
        )
        if self.is_open or self.valid_to_week is None:
            return f"W{start}–offen"
        return f"W{start}–W{self.valid_to_week}"


@dataclass(frozen=True)
class PlayerProfile:
    meta: PlayerMeta
    career: PlayerCareerSnapshot | None
    season_stats: tuple[PlayerSeasonStatsRow, ...]
    roster_history: tuple[PlayerRosterInterval, ...]

    @property
    def season_count(self) -> int:
        return len(self.season_stats)

    @property
    def team_count(self) -> int:
        return len({r.team_id for r in self.roster_history})


@dataclass(frozen=True)
class PlayerListPage:
    players: tuple[PlayerCard, ...]
    offset: int
    limit: int
    total: int

    @property
    def has_prev(self) -> bool:
        return self.offset > 0

    @property
    def has_next(self) -> bool:
        return (self.offset + len(self.players)) < self.total

    @property
    def prev_offset(self) -> int:
        return max(0, self.offset - self.limit)

    @property
    def next_offset(self) -> int:
        return self.offset + self.limit

    @property
    def page_range_label(self) -> str:
        if self.total == 0:
            return "0 von 0"
        first = self.offset + 1
        last = self.offset + len(self.players)
        return f"{first}–{last} von {self.total}"


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


def _list_players_fallback(
    con: duckdb.DuckDBPyConnection, offset: int, limit: int
) -> PlayerListPage:
    try:
        total_row = con.execute(f"SELECT COUNT(*) FROM {_MART_PLAYER}").fetchone()
        rows = con.execute(
            f"""
            SELECT
                player_id,
                display_name,
                full_name,
                position,
                current_team_id,
                jersey_number,
                rookie_season,
                last_season,
                is_active
            FROM {_MART_PLAYER}
            ORDER BY
                is_active DESC,
                last_season DESC NULLS LAST,
                display_name NULLS LAST,
                player_id
            LIMIT ? OFFSET ?
            """,
            [limit, offset],
        ).fetchall()
    except duckdb.Error:
        return PlayerListPage(players=(), offset=offset, limit=limit, total=0)
    total = int(total_row[0]) if total_row else 0
    cards = tuple(
        PlayerCard(
            player_id=str(r[0]),
            display_name=r[1],
            full_name=r[2],
            position=r[3],
            current_team_id=r[4],
            current_team_abbr=None,
            jersey_number=_coerce_int(r[5]),
            rookie_season=_coerce_int(r[6]),
            last_season=_coerce_int(r[7]),
            is_active=bool(r[8]) if r[8] is not None else False,
        )
        for r in rows
    )
    return PlayerListPage(players=cards, offset=offset, limit=limit, total=total)


def list_players(
    settings: Settings, *, offset: int = 0, limit: int = 50
) -> PlayerListPage:
    offset = max(0, int(offset))
    limit = max(1, min(500, int(limit)))
    con = _connect(settings)
    try:
        if not _table_exists(con, _MART_PLAYER):
            return PlayerListPage(players=(), offset=offset, limit=limit, total=0)
        if not _table_exists(con, _MART_TEAM):
            return _list_players_fallback(con, offset, limit)
        try:
            total_row = con.execute(
                f"SELECT COUNT(*) FROM {_MART_PLAYER}"
            ).fetchone()
            rows = con.execute(
                f"""
                SELECT
                    p.player_id,
                    p.display_name,
                    p.full_name,
                    p.position,
                    p.current_team_id,
                    t.team_abbr AS current_team_abbr,
                    p.jersey_number,
                    p.rookie_season,
                    p.last_season,
                    p.is_active
                FROM {_MART_PLAYER} p
                LEFT JOIN {_MART_TEAM} t
                  ON t.team_id_lower = p.current_team_id_lower
                ORDER BY
                    p.is_active DESC,
                    p.last_season DESC NULLS LAST,
                    p.display_name NULLS LAST,
                    p.player_id
                LIMIT ? OFFSET ?
                """,
                [limit, offset],
            ).fetchall()
        except duckdb.Error:
            return _list_players_fallback(con, offset, limit)
    finally:
        con.close()
    total = int(total_row[0]) if total_row else 0
    cards = tuple(
        PlayerCard(
            player_id=str(r[0]),
            display_name=r[1],
            full_name=r[2],
            position=r[3],
            current_team_id=r[4],
            current_team_abbr=r[5],
            jersey_number=_coerce_int(r[6]),
            rookie_season=_coerce_int(r[7]),
            last_season=_coerce_int(r[8]),
            is_active=bool(r[9]) if r[9] is not None else False,
        )
        for r in rows
    )
    return PlayerListPage(players=cards, offset=offset, limit=limit, total=total)


def _load_meta(
    con: duckdb.DuckDBPyConnection, player_id: str
) -> PlayerMeta | None:
    has_team = _table_exists(con, _MART_TEAM)
    team_abbr_sql = "t.team_abbr" if has_team else "NULL"
    team_name_sql = "t.team_name" if has_team else "NULL"
    team_join_sql = (
        f"LEFT JOIN {_MART_TEAM} t ON t.team_id_lower = p.current_team_id_lower"
        if has_team
        else ""
    )
    try:
        row = con.execute(
            f"""
            SELECT
                p.player_id,
                p.display_name,
                p.full_name,
                p.first_name,
                p.last_name,
                p.birth_date,
                p.position,
                p.height,
                p.weight,
                p.college_name,
                p.rookie_season,
                p.last_season,
                p.current_team_id,
                {team_abbr_sql} AS current_team_abbr,
                {team_name_sql} AS current_team_name,
                p.jersey_number,
                p.draft_club,
                p.draft_year,
                p.draft_round,
                p.draft_pick,
                p.status,
                p.is_active
            FROM {_MART_PLAYER} p
            {team_join_sql}
            WHERE p.player_id_lower = LOWER(?)
            LIMIT 1
            """,
            [player_id],
        ).fetchone()
    except duckdb.Error:
        return None
    if row is None:
        return None
    return PlayerMeta(
        player_id=str(row[0]),
        display_name=row[1],
        full_name=row[2],
        first_name=row[3],
        last_name=row[4],
        birth_date=_coerce_date(row[5]),
        position=row[6],
        height=_coerce_int(row[7]),
        weight=_coerce_int(row[8]),
        college_name=row[9],
        rookie_season=_coerce_int(row[10]),
        last_season=_coerce_int(row[11]),
        current_team_id=row[12],
        current_team_abbr=row[13],
        current_team_name=row[14],
        jersey_number=_coerce_int(row[15]),
        draft_club=row[16],
        draft_year=_coerce_int(row[17]),
        draft_round=_coerce_int(row[18]),
        draft_pick=_coerce_int(row[19]),
        status=row[20],
        is_active=bool(row[21]) if row[21] is not None else False,
    )


def _load_career(
    con: duckdb.DuckDBPyConnection, player_id: str
) -> PlayerCareerSnapshot | None:
    try:
        row = con.execute(
            f"""
            SELECT
                first_season,
                last_season,
                seasons_played,
                games_played,
                passing_yards,
                passing_tds,
                interceptions,
                rushing_yards,
                rushing_tds,
                receptions,
                receiving_yards,
                receiving_tds,
                total_yards,
                total_touchdowns,
                fumbles_lost,
                current_position
            FROM {_MART_CAREER}
            WHERE player_id = ?
            LIMIT 1
            """,
            [player_id],
        ).fetchone()
    except duckdb.Error:
        return None
    if row is None:
        return None
    return PlayerCareerSnapshot(
        first_season=_coerce_int(row[0]),
        last_season=_coerce_int(row[1]),
        seasons_played=_coerce_int(row[2]),
        games_played=_coerce_int(row[3]),
        passing_yards=_coerce_int(row[4]),
        passing_tds=_coerce_int(row[5]),
        interceptions=_coerce_int(row[6]),
        rushing_yards=_coerce_int(row[7]),
        rushing_tds=_coerce_int(row[8]),
        receptions=_coerce_int(row[9]),
        receiving_yards=_coerce_int(row[10]),
        receiving_tds=_coerce_int(row[11]),
        total_yards=_coerce_int(row[12]),
        total_touchdowns=_coerce_int(row[13]),
        fumbles_lost=_coerce_int(row[14]),
        current_position=row[15],
    )


def _load_season_stats(
    con: duckdb.DuckDBPyConnection, player_id: str
) -> tuple[PlayerSeasonStatsRow, ...]:
    try:
        rows = con.execute(
            f"""
            SELECT
                season,
                primary_position,
                games_played,
                passing_yards,
                passing_tds,
                interceptions,
                rushing_yards,
                rushing_tds,
                receptions,
                receiving_yards,
                receiving_tds,
                total_yards,
                total_touchdowns,
                fumbles_lost
            FROM {_MART_SEASON}
            WHERE player_id = ?
            ORDER BY season DESC
            """,
            [player_id],
        ).fetchall()
    except duckdb.Error:
        return ()
    return tuple(
        PlayerSeasonStatsRow(
            season=int(r[0]),
            primary_position=r[1],
            games_played=_coerce_int(r[2]),
            passing_yards=_coerce_int(r[3]),
            passing_tds=_coerce_int(r[4]),
            interceptions=_coerce_int(r[5]),
            rushing_yards=_coerce_int(r[6]),
            rushing_tds=_coerce_int(r[7]),
            receptions=_coerce_int(r[8]),
            receiving_yards=_coerce_int(r[9]),
            receiving_tds=_coerce_int(r[10]),
            total_yards=_coerce_int(r[11]),
            total_touchdowns=_coerce_int(r[12]),
            fumbles_lost=_coerce_int(r[13]),
        )
        for r in rows
    )


def _load_roster_history(
    con: duckdb.DuckDBPyConnection, player_id: str
) -> tuple[PlayerRosterInterval, ...]:
    try:
        rows = con.execute(
            f"""
            SELECT
                season,
                team_id,
                team_abbr,
                team_name,
                position,
                jersey_number,
                status,
                valid_from_week,
                valid_to_week,
                is_open
            FROM {_MART_ROSTER_HISTORY}
            WHERE player_id_lower = LOWER(?)
            ORDER BY season DESC, valid_from_week, team_id
            """,
            [player_id],
        ).fetchall()
    except duckdb.Error:
        return ()
    return tuple(
        PlayerRosterInterval(
            season=int(r[0]),
            team_id=str(r[1]),
            team_abbr=r[2],
            team_name=r[3],
            position=r[4],
            jersey_number=_coerce_int(r[5]),
            status=r[6],
            valid_from_week=_coerce_int(r[7]),
            valid_to_week=_coerce_int(r[8]),
            is_open=bool(r[9]) if r[9] is not None else False,
        )
        for r in rows
    )


def get_player_profile(
    settings: Settings, player_id: str
) -> PlayerProfile | None:
    con = _connect(settings)
    try:
        meta = _load_meta(con, player_id)
        if meta is None:
            return None
        career = _load_career(con, meta.player_id)
        season_stats = _load_season_stats(con, meta.player_id)
        roster_history = _load_roster_history(con, meta.player_id)
    finally:
        con.close()
    return PlayerProfile(
        meta=meta,
        career=career,
        season_stats=season_stats,
        roster_history=roster_history,
    )


__all__ = [
    "PlayerCard",
    "PlayerCareerSnapshot",
    "PlayerListPage",
    "PlayerMeta",
    "PlayerProfile",
    "PlayerRosterInterval",
    "PlayerSeasonStatsRow",
    "get_player_profile",
    "list_players",
]
