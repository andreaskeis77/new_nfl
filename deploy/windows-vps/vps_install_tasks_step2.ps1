# NEW NFL -- Scheduled Tasks Installation (iterativ, Step 2)
#
# Step 2 erweitert die Step-1-Belegung (Backup 04:00 + Teams 05:00) um die
# restlichen 6 Fetch-Tasks. Trigger gestaffelt im 15-Minuten-Raster, damit
# kein zwei Slices gleichzeitig gegen die nflverse-Releases ziehen
# (Rate-Limit-Vorsicht):
#   05:15  Schedule
#   05:30  Games
#   05:45  Players
#   06:00  Rosters         (per-season -- default_nfl_season im Python-Pfad)
#   06:15  TeamStats       (per-season -- default_nfl_season im Python-Pfad)
#   06:30  PlayerStats     (per-season -- default_nfl_season im Python-Pfad)
#
# Per-season-Argument: per-season-Slices laufen ohne -Season-Parameter im
# Task. Im Python-Pfad greift dann SliceSpec.remote_url_template +
# resolve_remote_url(spec, season=None) auf default_nfl_season(today)
# zurueck (siehe src/new_nfl/adapters/slices.py). Das vermeidet, dass das
# Jahr in PowerShell und Python doppelt gepflegt werden muss.
#
# Idempotent: bestehende NewNFL-* Tasks gleichen Namens werden vorher
# entfernt und neu angelegt. Andere Tasks (z. B. Capsule-*, Step-1-Tasks)
# sind tabu und werden nicht angefasst.
#
# Aufruf:
#   VPS-ADMIN PS> powershell -ExecutionPolicy Bypass -File C:\newNFL\deploy\windows-vps\vps_install_tasks_step2.ps1

$ErrorActionPreference = "Stop"

$RepoPath   = "C:\newNFL"
$User       = "srv-ops-admin"
$PsExe      = "powershell.exe"
$NewNflExe  = "$RepoPath\.venv\Scripts\new-nfl.exe"
$RunSlice   = "$RepoPath\deploy\windows-vps\run_slice.ps1"

# --- Sanity ----------------------------------------------------------------

if (-not (Test-Path $NewNflExe)) {
    throw "CLI-Entrypoint $NewNflExe fehlt. Bootstrap zuerst laufen lassen."
}
if (-not (Test-Path $RunSlice)) {
    throw "Wrapper $RunSlice fehlt. git pull auf $RepoPath laufen lassen."
}

# --- Helper ----------------------------------------------------------------

function Install-NewNflTask {
    param(
        [string]$TaskName,
        [string]$Description,
        [datetime]$TriggerTime,
        [string]$ActionExe,
        [string]$ActionArgs
    )
    Write-Host "==> $TaskName"
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  existiert bereits - loesche und lege neu an"
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }

    $actionObj = New-ScheduledTaskAction -Execute $ActionExe -Argument $ActionArgs -WorkingDirectory $RepoPath
    $trigger   = New-ScheduledTaskTrigger -Daily -At $TriggerTime
    $principal = New-ScheduledTaskPrincipal -UserId $User -RunLevel Highest
    $settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

    Register-ScheduledTask `
        -TaskName    $TaskName `
        -Description $Description `
        -Action      $actionObj `
        -Trigger     $trigger `
        -Principal   $principal `
        -Settings    $settings | Out-Null
    Write-Host "  OK -> naechster Tick: $($TriggerTime.ToString('HH:mm'))"
}

function New-SliceArgs {
    param([string]$Slice)
    return "-ExecutionPolicy Bypass -NoProfile -File `"$RunSlice`" -Slice $Slice"
}

# --- Task 1: Fetch Schedule (statisch) -------------------------------------

Install-NewNflTask `
    -TaskName    "NewNFL-Fetch-Schedule" `
    -Description "NEW NFL daily fetch+stage+core fuer Slice schedule_field_dictionary (T3.1 Step 2)" `
    -TriggerTime (Get-Date "05:15") `
    -ActionExe   $PsExe `
    -ActionArgs  (New-SliceArgs -Slice "schedule_field_dictionary")

# --- Task 2: Fetch Games (statisch) ----------------------------------------

Install-NewNflTask `
    -TaskName    "NewNFL-Fetch-Games" `
    -Description "NEW NFL daily fetch+stage+core fuer Slice games (T3.1 Step 2)" `
    -TriggerTime (Get-Date "05:30") `
    -ActionExe   $PsExe `
    -ActionArgs  (New-SliceArgs -Slice "games")

# --- Task 3: Fetch Players (statisch) --------------------------------------

Install-NewNflTask `
    -TaskName    "NewNFL-Fetch-Players" `
    -Description "NEW NFL daily fetch+stage+core fuer Slice players (T3.1 Step 2)" `
    -TriggerTime (Get-Date "05:45") `
    -ActionExe   $PsExe `
    -ActionArgs  (New-SliceArgs -Slice "players")

# --- Task 4: Fetch Rosters (per-season) ------------------------------------

Install-NewNflTask `
    -TaskName    "NewNFL-Fetch-Rosters" `
    -Description "NEW NFL daily fetch+stage+core fuer Slice rosters (per-season, T3.1 Step 2)" `
    -TriggerTime (Get-Date "06:00") `
    -ActionExe   $PsExe `
    -ActionArgs  (New-SliceArgs -Slice "rosters")

# --- Task 5: Fetch TeamStats (per-season) ----------------------------------

Install-NewNflTask `
    -TaskName    "NewNFL-Fetch-TeamStats" `
    -Description "NEW NFL daily fetch+stage+core fuer Slice team_stats_weekly (per-season, T3.1 Step 2)" `
    -TriggerTime (Get-Date "06:15") `
    -ActionExe   $PsExe `
    -ActionArgs  (New-SliceArgs -Slice "team_stats_weekly")

# --- Task 6: Fetch PlayerStats (per-season) --------------------------------

Install-NewNflTask `
    -TaskName    "NewNFL-Fetch-PlayerStats" `
    -Description "NEW NFL daily fetch+stage+core fuer Slice player_stats_weekly (per-season, T3.1 Step 2)" `
    -TriggerTime (Get-Date "06:30") `
    -ActionExe   $PsExe `
    -ActionArgs  (New-SliceArgs -Slice "player_stats_weekly")

# --- Abschluss -------------------------------------------------------------

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Scheduled Tasks (iterativ Step 2) installiert" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Tasks Step 2:"
Write-Host "  NewNFL-Fetch-Schedule     @ 05:15  ->  run_slice.ps1 -Slice schedule_field_dictionary"
Write-Host "  NewNFL-Fetch-Games        @ 05:30  ->  run_slice.ps1 -Slice games"
Write-Host "  NewNFL-Fetch-Players      @ 05:45  ->  run_slice.ps1 -Slice players"
Write-Host "  NewNFL-Fetch-Rosters      @ 06:00  ->  run_slice.ps1 -Slice rosters         (per-season)"
Write-Host "  NewNFL-Fetch-TeamStats    @ 06:15  ->  run_slice.ps1 -Slice team_stats_weekly (per-season)"
Write-Host "  NewNFL-Fetch-PlayerStats  @ 06:30  ->  run_slice.ps1 -Slice player_stats_weekly (per-season)"
Write-Host ""
Write-Host "Erwartete Gesamt-Belegung (Step 1 + Step 2):" -ForegroundColor Cyan
Write-Host "  04:00 NewNFL-Backup-Daily"
Write-Host "  05:00 NewNFL-Fetch-Teams"
Write-Host "  05:15 NewNFL-Fetch-Schedule"
Write-Host "  05:30 NewNFL-Fetch-Games"
Write-Host "  05:45 NewNFL-Fetch-Players"
Write-Host "  06:00 NewNFL-Fetch-Rosters"
Write-Host "  06:15 NewNFL-Fetch-TeamStats"
Write-Host "  06:30 NewNFL-Fetch-PlayerStats"
Write-Host ""
Write-Host "Manuelle Smoke-Trigger (Tasks sofort starten):" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName NewNFL-Fetch-Schedule"
Write-Host "  Start-ScheduledTask -TaskName NewNFL-Fetch-Games"
Write-Host "  Start-ScheduledTask -TaskName NewNFL-Fetch-Players"
Write-Host "  Start-ScheduledTask -TaskName NewNFL-Fetch-Rosters"
Write-Host "  Start-ScheduledTask -TaskName NewNFL-Fetch-TeamStats"
Write-Host "  Start-ScheduledTask -TaskName NewNFL-Fetch-PlayerStats"
Write-Host ""
Write-Host "Status nach Lauf pruefen:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName NewNFL-* | Get-ScheduledTaskInfo |"
Write-Host "    Select-Object TaskName, LastRunTime, LastTaskResult, NextRunTime"
