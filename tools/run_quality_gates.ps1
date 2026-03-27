param()

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest
