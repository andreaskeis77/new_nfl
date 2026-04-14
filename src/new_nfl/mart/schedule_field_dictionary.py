"""Mart builder for ``mart.schedule_field_dictionary_v1`` (ADR-0029).

The table is a denormalized read projection of ``core.schedule_field_dictionary``
with pre-lowercased filter columns plus build provenance. It is fully
rebuildable from core via ``CREATE OR REPLACE TABLE``. Readers (CLI browse /
lookup / summary, web preview) target exclusively this projection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import duckdb

from new_nfl.settings import Settings

MART_SCHEDULE_FIELD_DICTIONARY_V1 = "mart.schedule_field_dictionary_v1"
_SOURCE_TABLE = "core.schedule_field_dictionary"


@dataclass(frozen=True)
class MartBuildResult:
    qualified_table: str
    source_table: str
    source_row_count: int
    row_count: int
    built_at: datetime


def _source_columns(con: duckdb.DuckDBPyConnection) -> set[str]:
    try:
        rows = con.execute(f"DESCRIBE {_SOURCE_TABLE}").fetchall()
    except duckdb.Error as exc:
        raise ValueError(
            f"{_SOURCE_TABLE} does not exist; run core-load --adapter-id "
            "nflverse_bulk --execute first"
        ) from exc
    return {str(r[0]).strip().lower() for r in rows}


def _opt_col(name: str, present: set[str], cast: str = "") -> str:
    if name in present:
        return f"{name}{cast}"
    return f"NULL{cast}"


def build_schedule_field_dictionary_v1(settings: Settings) -> MartBuildResult:
    """Rebuild ``mart.schedule_field_dictionary_v1`` from ``core.*``.

    Full rebuild — the mart layer is a pure projection, no incremental state.
    """
    con = duckdb.connect(str(settings.db_path))
    try:
        cols = _source_columns(con)
        required = {"field", "data_type", "description"}
        missing = sorted(required - cols)
        if missing:
            raise ValueError(
                f"{_SOURCE_TABLE} is missing required columns: {', '.join(missing)}"
            )
        source_row_count = int(
            con.execute(f"SELECT COUNT(*) FROM {_SOURCE_TABLE}").fetchone()[0]
        )
        provenance_at = (
            "_canonicalized_at" if "_canonicalized_at" in cols
            else ("_loaded_at" if "_loaded_at" in cols else "NULL")
        )
        source_file_col = _opt_col("_source_file_id", cols)
        source_adapter_col = _opt_col("_adapter_id", cols)
        con.execute("CREATE SCHEMA IF NOT EXISTS mart")
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {MART_SCHEDULE_FIELD_DICTIONARY_V1} AS
            SELECT
                field,
                data_type,
                description,
                LOWER(TRIM(field)) AS field_lower,
                LOWER(COALESCE(data_type, '')) AS data_type_lower,
                {source_file_col} AS source_file_id,
                {source_adapter_col} AS source_adapter_id,
                {provenance_at} AS source_canonicalized_at,
                CURRENT_TIMESTAMP AS built_at
            FROM {_SOURCE_TABLE}
            """
        )
        row_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM {MART_SCHEDULE_FIELD_DICTIONARY_V1}"
            ).fetchone()[0]
        )
    finally:
        con.close()

    built_at = datetime.now()
    return MartBuildResult(
        qualified_table=MART_SCHEDULE_FIELD_DICTIONARY_V1,
        source_table=_SOURCE_TABLE,
        source_row_count=source_row_count,
        row_count=row_count,
        built_at=built_at,
    )
