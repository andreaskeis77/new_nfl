from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Type
from urllib.parse import parse_qs, urlparse

from new_nfl.core_browse import browse_core_dictionary
from new_nfl.core_summary import summarize_core_dictionary
from new_nfl.settings import Settings
from new_nfl.web_preview import _render_html


@dataclass(frozen=True)
class WebServerConfig:
    adapter_id: str
    host: str
    port: int
    limit: int
    data_type_filter: str


@dataclass(frozen=True)
class WebServerStartResult:
    adapter_id: str
    host: str
    port: int
    limit: int
    data_type_filter: str
    url: str
    health_url: str


def build_web_preview_html(
    settings: Settings,
    *,
    adapter_id: str,
    limit: int = 20,
    data_type_filter: str = '',
) -> str:
    summary = summarize_core_dictionary(settings, adapter_id=adapter_id)
    browse = browse_core_dictionary(
        settings,
        adapter_id=adapter_id,
        field_prefix='',
        limit=limit,
        data_type_filter=data_type_filter,
    )
    return _render_html(
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


def build_preview_url(host: str, port: int) -> str:
    return f'http://{host}:{port}/'


def build_health_url(host: str, port: int) -> str:
    return f'http://{host}:{port}/healthz'


def _resolve_data_type_filter(path: str, default_data_type_filter: str) -> str:
    parsed = urlparse(path)
    query = parse_qs(parsed.query)
    values = query.get('data_type', [])
    if not values:
        return default_data_type_filter
    return values[0].strip()


def make_preview_handler(
    settings: Settings,
    *,
    adapter_id: str,
    limit: int,
    data_type_filter: str,
) -> Type[BaseHTTPRequestHandler]:
    class PreviewHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == '/healthz':
                payload = b'ok\n'
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if parsed.path not in ('/', '/index.html'):
                payload = b'not found\n'
                self.send_response(404)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            resolved_data_type = _resolve_data_type_filter(self.path, data_type_filter)
            html = build_web_preview_html(
                settings,
                adapter_id=adapter_id,
                limit=limit,
                data_type_filter=resolved_data_type,
            )
            payload = html.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    return PreviewHandler


def serve_web_preview(
    settings: Settings,
    *,
    adapter_id: str,
    host: str = '127.0.0.1',
    port: int = 8787,
    limit: int = 20,
    data_type_filter: str = '',
) -> WebServerStartResult:
    if port < 1 or port > 65535:
        raise ValueError('port must be between 1 and 65535')
    if limit < 1:
        raise ValueError('limit must be >= 1')

    handler = make_preview_handler(
        settings,
        adapter_id=adapter_id,
        limit=limit,
        data_type_filter=data_type_filter,
    )
    server = ThreadingHTTPServer((host, port), handler)
    try:
        result = WebServerStartResult(
            adapter_id=adapter_id,
            host=host,
            port=port,
            limit=limit,
            data_type_filter=data_type_filter,
            url=build_preview_url(host, port),
            health_url=build_health_url(host, port),
        )
        print(f'ADAPTER_ID={result.adapter_id}')
        print(f'HOST={result.host}')
        print(f'PORT={result.port}')
        print(f'LIMIT={result.limit}')
        print(f'DATA_TYPE_FILTER={result.data_type_filter}')
        print(f'URL={result.url}')
        print(f'HEALTH_URL={result.health_url}')
        server.serve_forever()
    finally:
        server.server_close()
