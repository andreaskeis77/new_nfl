param()

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m new_nfl.cli seed-sources
.\.venv\Scripts\python.exe -m new_nfl.cli list-sources
