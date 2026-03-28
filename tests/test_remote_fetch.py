from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from new_nfl.adapters.remote_fetch import execute_remote_fetch
from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import list_ingest_runs, seed_default_sources
from new_nfl.settings import load_settings


def _serve_directory(directory: Path) -> tuple[ThreadingHTTPServer, str]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_execute_remote_fetch_dry_run_is_side_effect_free(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    result = execute_remote_fetch(
        settings,
        adapter_id="nflverse_bulk",
        execute=False,
        remote_url_override="https://example.invalid/test.csv",
    )

    assert result.run_mode == "dry_run"
    assert result.run_status == "planned_remote_fetch"
    assert result.ingest_run_id == ""
    assert result.landed_file_count == 0


def test_execute_remote_fetch_execute_downloads_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()
    payload = payload_dir / "dictionary_schedules.csv"
    payload.write_text("season,week\n2025,1\n", encoding="utf-8")

    server, base_url = _serve_directory(payload_dir)
    try:
        result = execute_remote_fetch(
            settings,
            adapter_id="nflverse_bulk",
            execute=True,
            remote_url_override=f"{base_url}/dictionary_schedules.csv",
        )
    finally:
        server.shutdown()
        server.server_close()

    landing_dir = Path(result.landing_dir)
    assert result.run_status == "remote_fetched"
    assert result.ingest_run_id
    assert result.downloaded_bytes > 0
    assert result.sha256_hex
    assert landing_dir.exists()
    assert Path(result.manifest_path).exists()
    assert Path(result.receipt_path).exists()
    assert Path(result.downloaded_file_path).exists()

    runs = list_ingest_runs(settings, "adapter.nflverse_bulk.remote_fetch")
    assert len(runs) == 1
    assert runs[0]["run_status"] == "remote_fetched"
