# NEW NFL -- VPS Bootstrap
#
# Zweck: einmaliger Erst-Deploy von NEW NFL auf den Contabo-Windows-VPS.
# Legt Venv, Daten- und Backup-Verzeichnisse an, installiert NEW NFL
# editable in der Venv und validiert mit `new-nfl bootstrap` und
# `new-nfl registry-list`.
#
# Vorbedingungen auf dem VPS:
#   - Python 3.12 via py-Launcher verfuegbar (py -3.12 --version)
#   - git installiert und im PATH
#   - Repo bereits geklont nach C:\newNFL (siehe Aufruf-Reihenfolge unten)
#
# Aufruf (Phase 4 des VPS_DEPLOYMENT_RUNBOOK):
#   VPS-ADMIN PS> git clone https://github.com/andreaskeis77/new_nfl.git C:\newNFL
#   VPS-ADMIN PS> powershell -ExecutionPolicy Bypass -File C:\newNFL\deploy\windows-vps\vps_bootstrap.ps1
#
# Referenz: docs/_ops/vps/VPS_DOSSIER.md (Konventionen)

$ErrorActionPreference = "Stop"

# --- Konstanten -------------------------------------------------------------

$RepoPath    = "C:\newNFL"
$BackupPath  = "C:\newNFL-Backups"
$PythonMajor = "3.12"

# --- Helper -----------------------------------------------------------------

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-ExitCode {
    param([string]$Context)
    if ($LASTEXITCODE -ne 0) {
        throw "Schritt '$Context' fehlgeschlagen (ExitCode=$LASTEXITCODE). Bootstrap abgebrochen."
    }
}

# --- Pruefungen -------------------------------------------------------------

Write-Step "Pruefe Python $PythonMajor via py-Launcher"
$pyOut = & py -$PythonMajor --version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "py -$PythonMajor nicht verfuegbar. 'py -0p' auflisten und ggf. Python $PythonMajor installieren."
}
if ($pyOut -notmatch "^Python\s+$PythonMajor") {
    throw "py -$PythonMajor gibt unerwartete Version zurueck: '$pyOut'"
}
Write-Host $pyOut

Write-Step "Pruefe git"
& git --version
Assert-ExitCode "git --version"

Write-Step "Pruefe Repo-Pfad $RepoPath"
if (-not (Test-Path $RepoPath)) {
    throw "$RepoPath existiert nicht. Bitte zuerst klonen: git clone https://github.com/andreaskeis77/new_nfl.git $RepoPath"
}
if (-not (Test-Path "$RepoPath\.git")) {
    throw "$RepoPath existiert, enthaelt aber kein .git-Verzeichnis. Kein sauberer Clone - manueller Check noetig."
}
if (-not (Test-Path "$RepoPath\pyproject.toml")) {
    throw "$RepoPath\pyproject.toml fehlt. Clone unvollstaendig oder falsches Repo."
}

Write-Step "Pruefe dass Venv noch nicht existiert"
if (Test-Path "$RepoPath\.venv") {
    throw "$RepoPath\.venv existiert bereits. Bootstrap erwartet frischen Zustand. Zum Neu-Bootstrappen: Venv-Verzeichnis manuell loeschen nach Sichtung."
}

# --- Verzeichnisse ----------------------------------------------------------

Write-Step "Lege Daten- und Backup-Verzeichnisse an"
New-Item -ItemType Directory -Force -Path "$RepoPath\data"      | Out-Null
New-Item -ItemType Directory -Force -Path "$RepoPath\data\db"   | Out-Null
New-Item -ItemType Directory -Force -Path "$RepoPath\data\logs" | Out-Null
New-Item -ItemType Directory -Force -Path $BackupPath           | Out-Null
Write-Host "  data/       -> $RepoPath\data"
Write-Host "  data/db/    -> $RepoPath\data\db"
Write-Host "  data/logs/  -> $RepoPath\data\logs"
Write-Host "  backups/    -> $BackupPath"

# --- Venv + Installation ----------------------------------------------------

Write-Step "Erstelle Venv mit Python $PythonMajor"
& py -$PythonMajor -m venv "$RepoPath\.venv"
Assert-ExitCode "py -$PythonMajor -m venv"

$PyExe     = "$RepoPath\.venv\Scripts\python.exe"
$PipExe    = "$RepoPath\.venv\Scripts\pip.exe"
$NewNflExe = "$RepoPath\.venv\Scripts\new-nfl.exe"

Write-Step "Update pip in Venv"
& $PyExe -m pip install --upgrade pip
Assert-ExitCode "pip upgrade"

Write-Step "Installiere NEW NFL editable mit dev-Extras (pytest, ruff)"
& $PipExe install -e "$RepoPath[dev]"
Assert-ExitCode "pip install -e .[dev]"

# --- Smoke ------------------------------------------------------------------

Write-Step "DuckDB-Bootstrap (new-nfl bootstrap)"
if (-not (Test-Path $NewNflExe)) {
    throw "Erwarteter CLI-Entrypoint $NewNflExe fehlt nach pip install -e . - Package-Metadata pruefen."
}
& $NewNflExe bootstrap
Assert-ExitCode "new-nfl bootstrap"

Write-Step "Seed source registry (new-nfl seed-sources)"
& $NewNflExe seed-sources
Assert-ExitCode "new-nfl seed-sources"

Write-Step "Smoke: registry-list"
& $NewNflExe registry-list
Assert-ExitCode "new-nfl registry-list"

# --- Abschluss --------------------------------------------------------------

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "NEW NFL Bootstrap abgeschlossen" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Repo:         $RepoPath"
Write-Host "Venv:         $RepoPath\.venv (Python $PythonMajor)"
Write-Host "Data-Root:    $RepoPath\data"
Write-Host "DB:           $RepoPath\data\db\new_nfl.duckdb"
Write-Host "Logs:         $RepoPath\data\logs"
Write-Host "Backup-Ziel:  $BackupPath"
Write-Host ""
Write-Host "Naechste Schritte:" -ForegroundColor Yellow
Write-Host "  1. Full-Suite laufen lassen:  cd $RepoPath; .\.venv\Scripts\pytest.exe -v"
Write-Host "  2. Smoke manuell:             .\.venv\Scripts\new-nfl.exe list-slices"
Write-Host "  3. Output an Claude schicken, dann Phase 5 (Scheduled Tasks)."
