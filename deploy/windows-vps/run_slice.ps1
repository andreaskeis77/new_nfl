# NEW NFL -- Slice-Pipeline-Wrapper
#
# Faehrt fuer einen Slice die Pipeline fetch-remote -> stage-load -> core-load
# durch. core-load triggert mart-rebuild implizit am Ende. Jeder CLI-Aufruf
# geht intern durch den internen Runner und erzeugt eigene meta.job_run-
# Evidence (ADR-0025); kein dauerhafter Worker noetig.
#
# Aufruf (interaktiv oder als Scheduled-Task-Action):
#   run_slice.ps1 -Slice teams
#   run_slice.ps1 -Slice schedule_field_dictionary
#   run_slice.ps1 -Slice players -Adapter nflverse_bulk
#
# Scheduled-Task-Integration: vps_install_tasks.ps1 ruft diesen Wrapper
# ueber 'powershell.exe -File run_slice.ps1 -Slice <slice>'.

param(
    [Parameter(Mandatory=$true)][string]$Slice,
    [string]$Adapter = "nflverse_bulk",
    [Nullable[int]]$Season = $null
)

$ErrorActionPreference = "Stop"

$RepoPath  = "C:\newNFL"
$LogPath   = "$RepoPath\data\logs"
$NewNflExe = "$RepoPath\.venv\Scripts\new-nfl.exe"

if (-not (Test-Path $NewNflExe)) {
    throw "CLI-Entrypoint $NewNflExe fehlt. Bootstrap zuerst laufen lassen."
}
if (-not (Test-Path $LogPath)) {
    New-Item -ItemType Directory -Force -Path $LogPath | Out-Null
}

# JSONL-Logging aus T2.7B aktivieren (Default waere stdout, was im Task
# verloren ginge). NEW_NFL_LOG_DESTINATION 'file:<pfad>' rotiert taeglich.
$env:NEW_NFL_LOG_DESTINATION = "file:$LogPath"

function Assert-ExitCode {
    param([string]$Context)
    if ($LASTEXITCODE -ne 0) {
        throw "Slice=$Slice Step='$Context' fehlgeschlagen (ExitCode=$LASTEXITCODE)."
    }
}

$seasonDisplay = if ($Season -ne $null) { $Season } else { "(default)" }
Write-Host "=== run_slice: Adapter=$Adapter Slice=$Slice Season=$seasonDisplay ==="
Write-Host "Log-Destination: $env:NEW_NFL_LOG_DESTINATION"

$fetchArgs = @("fetch-remote", "--adapter-id", $Adapter, "--slice", $Slice, "--execute")
if ($Season -ne $null) {
    $fetchArgs += @("--season", [string]$Season)
}

Write-Host ""
Write-Host ">> fetch-remote" -ForegroundColor Cyan
& $NewNflExe @fetchArgs
Assert-ExitCode "fetch-remote"

Write-Host ""
Write-Host ">> stage-load" -ForegroundColor Cyan
& $NewNflExe stage-load --adapter-id $Adapter --slice $Slice --execute
Assert-ExitCode "stage-load"

Write-Host ""
Write-Host ">> core-load (triggert mart-rebuild implizit)" -ForegroundColor Cyan
& $NewNflExe core-load --adapter-id $Adapter --slice $Slice --execute
Assert-ExitCode "core-load"

Write-Host ""
Write-Host "=== DONE: Adapter=$Adapter Slice=$Slice ===" -ForegroundColor Green
