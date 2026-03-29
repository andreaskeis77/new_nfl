from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from new_nfl.core_browse import browse_core_dictionary
from new_nfl.core_summary import summarize_core_dictionary
from new_nfl.settings import Settings


@dataclass(frozen=True)
class WebPreviewResult:
    adapter_id: str
    output_path: str
    qualified_table: str
    total_row_count: int
    match_row_count: int
    returned_row_count: int
    distinct_data_type_count: int
    limit: int
    data_type_filter: str


def _render_html(
    *,
    adapter_id: str,
    qualified_table: str,
    total_row_count: int,
    match_row_count: int,
    returned_row_count: int,
    distinct_data_type_count: int,
    limit: int,
    data_type_filter: str,
    summary_rows: tuple[tuple[str, int], ...],
    browse_rows: tuple[tuple[str, str, str], ...],
) -> str:
    summary_html = ''.join(
        f'<tr><td>{escape(data_type)}</td><td>{count}</td></tr>'
        for data_type, count in summary_rows
    )
    rows_html = ''.join(
        (
            '<tr>'
            f'<td>{escape(field)}</td>'
            f'<td>{escape(data_type)}</td>'
            f'<td>{escape(description)}</td>'
            '</tr>'
        )
        for field, data_type, description in browse_rows
    )
    filter_label = escape(data_type_filter or '(none)')
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>NEW NFL Core Dictionary Preview</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    .meta {{ margin: 1rem 0 1.5rem 0; }}
    .meta dt {{ font-weight: bold; }}
    .meta dd {{ margin: 0 0 0.5rem 0; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 2rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f4f4f4; }}
    code {{ background: #f7f7f7; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>NEW NFL Core Dictionary Preview</h1>
  <p>Adapter: <code>{escape(adapter_id)}</code></p>

  <dl class="meta">
    <dt>Qualified table</dt><dd>{escape(qualified_table)}</dd>
    <dt>Total row count</dt><dd>{total_row_count}</dd>
    <dt>Match row count</dt><dd>{match_row_count}</dd>
    <dt>Returned row count</dt><dd>{returned_row_count}</dd>
    <dt>Distinct data type count</dt><dd>{distinct_data_type_count}</dd>
    <dt>Limit</dt><dd>{limit}</dd>
    <dt>Data type filter</dt><dd>{filter_label}</dd>
  </dl>

  <h2>Summary by data type</h2>
  <table>
    <thead>
      <tr><th>data_type</th><th>count</th></tr>
    </thead>
    <tbody>
      {summary_html}
    </tbody>
  </table>

  <h2>Preview rows</h2>
  <table>
    <thead>
      <tr><th>field</th><th>data_type</th><th>description</th></tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>
'''


def render_core_dictionary_preview(
    settings: Settings,
    *,
    adapter_id: str,
    output_path: str,
    limit: int = 20,
    data_type_filter: str = '',
) -> WebPreviewResult:
    summary = summarize_core_dictionary(settings, adapter_id=adapter_id)
    browse = browse_core_dictionary(
        settings,
        adapter_id=adapter_id,
        field_prefix='',
        limit=limit,
        data_type_filter=data_type_filter,
    )

    html = _render_html(
        adapter_id=adapter_id,
        qualified_table=browse.qualified_table,
        total_row_count=browse.total_row_count,
        match_row_count=browse.match_row_count,
        returned_row_count=browse.returned_row_count,
        distinct_data_type_count=summary.distinct_data_type_count,
        limit=browse.limit,
        data_type_filter=browse.data_type_filter,
        summary_rows=summary.data_type_rows,
        browse_rows=browse.rows,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8')

    return WebPreviewResult(
        adapter_id=adapter_id,
        output_path=str(output),
        qualified_table=browse.qualified_table,
        total_row_count=browse.total_row_count,
        match_row_count=browse.match_row_count,
        returned_row_count=browse.returned_row_count,
        distinct_data_type_count=summary.distinct_data_type_count,
        limit=browse.limit,
        data_type_filter=browse.data_type_filter,
    )
