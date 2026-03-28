from __future__ import annotations

import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from new_nfl.bootstrap import bootstrap_local_environment
from new_nfl.metadata import seed_default_sources
from new_nfl.settings import load_settings


def _serve_directory(directory: Path) -> tuple[ThreadingHTTPServer, str]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_cli_fetch_remote_execute(capsys, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEW_NFL_REPO_ROOT", str(tmp_path))
    settings = load_settings()
    bootstrap_local_environment(settings)
    seed_default_sources(settings)

    payload_dir = tmp_path / "payload"
    payload_dir.mkdir()
    payload = payload_dir / "mini.csv"
    payload.write_text("a,b\n1,2\n", encoding="utf-8")

    server, base_url = _serve_directory(payload_dir)
    try:
        from new_nfl.cli import main

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "new-nfl",
                "fetch-remote",
                "--adapter-id",
                "nflverse_bulk",
                "--execute",
                "--remote-url",
                f"{base_url}/mini.csv",
            ],
        )
        rc = main()
    finally:
        server.shutdown()
        server.server_close()

    out = capsys.readouterr().out
    assert rc == 0
    assert "RUN_STATUS=remote_fetched" in out
    assert "DOWNLOADED_BYTES=" in out
