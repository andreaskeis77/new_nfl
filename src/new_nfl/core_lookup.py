from __future__ import annotations

from dataclasses import dataclass

import duckdb

from new_nfl.adapters.catalog import build_adapter_plan
from new_nfl.settings import Settings


@dataclass(frozen=True)
class CoreLookupResult:
    adapter_id: str
    source_schema: str
    source_object: str
    qualified_table: str
    requested_field: str
    normalized_field: str
    found: bool
    field: str
    data_type: str
    description: str
    stage_dataset: str
    source_status: str


def _target_table_for_adapter(adapter_id: str) -> tuple[str, str]:
    if adapter_id != 'nflverse_bulk':
        raise ValueError(
            'T2.0D only supports adapter_id=nflverse_bulk for the first exact core lookup slice'
        )
    return ('core', 'schedule_field_dictionary')


def lookup_core_dictionary_field(
    settings: Settings,
    *,
    adapter_id: str,
    field: str,
) -> CoreLookupResult:
    source_schema, source_object = _target_table_for_adapter(adapter_id)
    plan = build_adapter_plan(settings, adapter_id)
    qualified_table = f'{source_schema}.{source_object}'
    normalized_field = field.strip().lower()
    con = duckdb.connect(str(settings.db_path))
    try:
        row = con.execute(
            f"""
            SELECT field, data_type, description
            FROM {qualified_table}
            WHERE LOWER(TRIM(field)) = ?
            LIMIT 1
            """,
            [normalized_field],
        ).fetchone()
    finally:
        con.close()

    if row is None:
        return CoreLookupResult(
            adapter_id=adapter_id,
            source_schema=source_schema,
            source_object=source_object,
            qualified_table=qualified_table,
            requested_field=field,
            normalized_field=normalized_field,
            found=False,
            field='',
            data_type='',
            description='',
            stage_dataset=plan.stage_dataset,
            source_status=plan.source_status,
        )

    return CoreLookupResult(
        adapter_id=adapter_id,
        source_schema=source_schema,
        source_object=source_object,
        qualified_table=qualified_table,
        requested_field=field,
        normalized_field=normalized_field,
        found=True,
        field=str(row[0]),
        data_type=str(row[1]),
        description=str(row[2]),
        stage_dataset=plan.stage_dataset,
        source_status=plan.source_status,
    )
