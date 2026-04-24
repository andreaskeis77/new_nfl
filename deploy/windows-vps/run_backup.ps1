# NEW NFL -- Backup-Snapshot-Wrapper
#
# Ruft new-nfl backup-snapshot mit einem zeitstempel-basierten Ziel-ZIP
# auf. --target erwartet einen File-Pfad, kein Verzeichnis.
#
# Aufruf (interaktiv oder als Scheduled-Task-Action):
#   run_backup.ps1
#   run_backup.ps1 -BackupDir C:\alternative-backups
#
# Scheduled-Task-Integration: vps_install_tasks.ps1 ruft diesen Wrapper
# ueber 'powershell.exe -File run_backup.ps1'.

param(
    [string]$BackupDir = "C:\newNFL-Backups"
)

$ErrorActionPreference = "Stop"

$RepoPath  = "C:\newNFL"
$LogPath   = "$RepoPath\data\logs"
$NewNflExe = "$RepoPath\.venv\Scripts\new-nfl.exe"

if (-not (Test-Path $NewNflExe)) {
    throw "CLI-Entrypoint $NewNflExe fehlt. Bootstrap zuerst laufen lassen."
}
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
}
if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Force -Path $LogPath | Out-Null
}

# JSONL-Logging aus T2.7B aktivieren, damit Task-Laeufe nicht im
# stdout-Nichts verschwinden.
$env:NEW_NFL_LOG_DESTINATION = "file:$LogPath"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$targetZip = Join-Path $BackupDir "snapshot_$timestamp.zip"

Write-Host "=== backup-snapshot ==="
Write-Host "Target: $targetZip"
Write-Host "Log-Destination: $env:NEW_NFL_LOG_DESTINATION"
Write-Host ""

& $NewNflExe backup-snapshot --target $targetZip
if ($LASTEXITCODE -ne 0) {
    throw "backup-snapshot fehlgeschlagen (ExitCode=$LASTEXITCODE)"
}

Write-Host ""
Write-Host "=== DONE: $targetZip ===" -ForegroundColor Green
