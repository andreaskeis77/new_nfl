from __future__ import annotations

from dataclasses import dataclass

import duckdb

from new_nfl.adapters.catalog import build_adapter_plan
from new_nfl.settings import Settings


@dataclass(frozen=True)
class CoreBrowseResult:
    adapter_id: str
    source_schema: str
    source_object: str
    qualified_table: str
    total_row_count: int
    match_row_count: int
    returned_row_count: int
    limit: int
    field_prefix: str
    data_type_filter: str
    stage_dataset: str
    source_status: str
    rows: tuple[tuple[str, str, str], ...]


def _target_table_for_adapter(adapter_id: str) -> tuple[str, str]:
    if adapter_id != 'nflverse_bulk':
        raise ValueError(
            'T2.0C only supports adapter_id=nflverse_bulk for the first browseable core slice'
        )
    return ('core', 'schedule_field_dictionary')


def _assert_required_columns(settings: Settings, qualified_table: str) -> None:
    con = duckdb.connect(str(settings.db_path))
    try:
        rows = con.execute(f'DESCRIBE {qualified_table}').fetchall()
    except duckdb.Error as exc:
        raise ValueError(
            f'{qualified_table} does not exist; run core-load --adapter-id nflverse_bulk --execute first'
        ) from exc
    finally:
        con.close()
    existing = {str(row[0]).strip().lower() for row in rows}
    required = {'field', 'data_type', 'description'}
    missing = sorted(required - existing)
    if missing:
        raise ValueError(
            f'{qualified_table} is missing required browse columns: {", ".join(missing)}'
        )


def browse_core_dictionary(
    settings: Settings,
    *,
    adapter_id: str,
    limit: int,
    field_prefix: str,
    data_type_filter: str,
) -> CoreBrowseResult:
    if limit <= 0:
        raise ValueError('limit must be >= 1')

    plan = build_adapter_plan(settings, adapter_id)
    source_schema, source_object = _target_table_for_adapter(adapter_id)
    qualified_table = f'{source_schema}.{source_object}'
    normalized_prefix = field_prefix.strip().lower()
    normalized_data_type = data_type_filter.strip().lower()

    _assert_required_columns(settings, qualified_table)

    where_parts: list[str] = []
    params: list[str | int] = []
    if normalized_prefix:
        where_parts.append('LOWER(field) LIKE ?')
        params.append(f'{normalized_prefix}%')
    if normalized_data_type:
        where_parts.append('LOWER(data_type) = ?')
        params.append(normalized_data_type)
    where_clause = '' if not where_parts else 'WHERE ' + ' AND '.join(where_parts)

    con = duckdb.connect(str(settings.db_path))
    try:
        total_row_count = int(con.execute(f'SELECT COUNT(*) FROM {qualified_table}').fetchone()[0])
        match_row_count = int(
            con.execute(f'SELECT COUNT(*) FROM {qualified_table} {where_clause}', params).fetchone()[0]
        )
        query = (
            'SELECT CAST(field AS VARCHAR), CAST(data_type AS VARCHAR), CAST(description AS VARCHAR) '
            f'FROM {qualified_table} {where_clause} ORDER BY field LIMIT ?'
        )
        rows = con.execute(query, [*params, limit]).fetchall()
    finally:
        con.close()

    normalized_rows = tuple(
        (
            '' if row[0] is None else str(row[0]),
            '' if row[1] is None else str(row[1]),
            '' if row[2] is None else str(row[2]),
        )
        for row in rows
    )
    return CoreBrowseResult(
        adapter_id=adapter_id,
        source_schema=source_schema,
        source_object=source_object,
        qualified_table=qualified_table,
        total_row_count=total_row_count,
        match_row_count=match_row_count,
        returned_row_count=len(normalized_rows),
        limit=limit,
        field_prefix=normalized_prefix,
        data_type_filter=normalized_data_type,
        stage_dataset=plan.stage_dataset,
        source_status=plan.source_status,
        rows=normalized_rows,
    )
