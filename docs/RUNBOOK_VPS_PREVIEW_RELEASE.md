# RUNBOOK_VPS_PREVIEW_RELEASE

## Purpose

This runbook defines the first **preview release** workflow for NEW NFL on the VPS.

The goal is intentionally narrow:
- deploy the current preview-capable repo state
- prepare the Python environment
- replay the existing local preview path on the VPS
- expose a first preview server locally on the VPS
- smoke-test `/healthz` and `/`

This runbook is **not** yet the first production-grade deployment process.
It is the first controlled VPS preview-release procedure.

## Scope

Included:
- repo sync
- venv setup / dependency install
- local-on-VPS preview data path replay
- preview server start
- smoke test
- stop / restart notes

Not included:
- systemd service hardening
- reverse proxy / TLS
- scheduler / cron
- public internet exposure
- additional data assets beyond the current dictionary-based preview slice

## Preconditions

Before running this runbook, the following must already be true:

1. A VPS user account exists with shell access.
2. The NEW NFL repo is already present on the VPS.
3. Python 3.12 is available on the VPS.
4. Git is available on the VPS.
5. The local tranche state to release has already been committed and pushed.
6. The operator knows the actual repo path on the VPS.

## Variables to set once per VPS

Replace these values with the real ones for the VPS:

```bash
export NEW_NFL_REPO_ROOT="$HOME/new_nfl"
export NEW_NFL_HOST="127.0.0.1"
export NEW_NFL_PORT="8787"
```

The runbook uses a loopback bind intentionally for the first preview release.

## Release cut

The release cut for the first VPS preview must contain at least these capabilities:

- remote fetch for `nflverse_bulk`
- source-file discovery
- `stage-load` with optional `--source-file-id`
- canonical core load for the dictionary slice
- `browse-core`
- `describe-core-field`
- `summarize-core`
- `render-web-preview`
- `serve-web-preview`

## VPS-USER — Prepare environment

```bash
cd "$NEW_NFL_REPO_ROOT"
git status --short
git pull --ff-only

python3.12 -m venv .venv
. .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

python -c "import new_nfl.cli; print('cli import ok')"
python -m pytest tests/test_stage_load.py tests/test_cli_adapter.py tests/test_source_files.py tests/test_source_files_cli.py tests/test_core_load.py tests/test_core_load_cli.py tests/test_core_browse.py tests/test_core_browse_cli.py tests/test_core_lookup.py tests/test_core_lookup_cli.py tests/test_core_summary.py tests/test_core_summary_cli.py tests/test_web_preview.py tests/test_web_preview_cli.py tests/test_web_server.py tests/test_web_server_cli.py -q
```

Expected result:
- repo clean or only known local runtime artifacts
- `cli import ok`
- targeted test pack green

## VPS-USER — Replay preview data path

```bash
cd "$NEW_NFL_REPO_ROOT"
. .venv/bin/activate

python -m new_nfl.cli bootstrap
python -m new_nfl.cli seed-sources
python -m new_nfl.cli fetch-remote --adapter-id nflverse_bulk --execute
python -m new_nfl.cli list-source-files --adapter-id nflverse_bulk --limit 1
python -m new_nfl.cli stage-load --adapter-id nflverse_bulk --execute
python -m new_nfl.cli core-load --adapter-id nflverse_bulk --execute
python -m new_nfl.cli summarize-core --adapter-id nflverse_bulk
python -m new_nfl.cli render-web-preview --adapter-id nflverse_bulk --output data/exports/core_dictionary_preview.html
```

Expected result:
- the first source file is landed and listed
- stage table is rebuilt
- core dictionary table is rebuilt
- summary output is visible
- `data/exports/core_dictionary_preview.html` exists

## VPS-USER — Start preview server

Use a dedicated terminal session for the first preview release:

```bash
cd "$NEW_NFL_REPO_ROOT"
. .venv/bin/activate

python -m new_nfl.cli serve-web-preview --adapter-id nflverse_bulk --host "$NEW_NFL_HOST" --port "$NEW_NFL_PORT" --limit 20
```

Expected result:
- process stays attached
- the server listens on `${NEW_NFL_HOST}:${NEW_NFL_PORT}`

## VPS-USER — Smoke test

Open a second terminal on the VPS:

```bash
cd "$NEW_NFL_REPO_ROOT"
curl -fsS "http://${NEW_NFL_HOST}:${NEW_NFL_PORT}/healthz"
curl -I "http://${NEW_NFL_HOST}:${NEW_NFL_PORT}/"
```

Expected result:
- `/healthz` returns `ok`
- `/` returns `HTTP/1.0 200 OK` or equivalent `200` response

## Stop / restart note

To stop the first preview server:
- interrupt the attached process with `Ctrl+C`
- or terminate the responsible shell / session

For a manual restart:
1. ensure no stale process is still bound to the configured port
2. rerun the preview server command from the start section
3. rerun the smoke-test section

## Rollback note

If the preview replay or smoke test fails:
1. stop the server if it started
2. do not continue with exposure or proxy work
3. keep the failure output
4. cut a small repair bolt
5. replay the last green local path first
6. rerun this VPS runbook only after the repair is green

## Preferred next step

T2.2B — VPS preview release execution and smoke test evidence capture
