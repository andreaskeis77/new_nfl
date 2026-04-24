# NEW NFL -- Scheduled Tasks Installation (iterativ, Step 1)
#
# Legt nur die zwei Tasks an, die wir als Smoke testen wollen:
#   - NewNFL-Backup-Daily   (04:00 taeglich)
#   - NewNFL-Fetch-Teams    (05:00 taeglich)
#
# Die restlichen 6 Fetch-Tasks (Games/Players/Rosters/TeamStats/
# PlayerStats/Schedule) folgen nach erfolgreichem ersten Scheduler-Tag.
#
# Idempotent: bestehende NewNFL-* Tasks gleichen Namens werden vorher
# entfernt und neu angelegt. Andere Tasks (z. B. Capsule-*) sind tabu
# und werden nicht angefasst.
#
# Aufruf:
#   VPS-ADMIN PS> powershell -ExecutionPolicy Bypass -File C:\newNFL\deploy\windows-vps\vps_install_tasks.ps1

$ErrorActionPreference = "Stop"

$RepoPath   = "C:\newNFL"
$BackupPath = "C:\newNFL-Backups"
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
if (-not (Test-Path $BackupPath)) {
    New-Item -ItemType Directory -Force -Path $BackupPath | Out-Null
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

# --- Task 1: Backup --------------------------------------------------------

Install-NewNflTask `
    -TaskName    "NewNFL-Backup-Daily" `
    -Description "NEW NFL daily backup-snapshot (T3.0A iterativ Step 1)" `
    -TriggerTime (Get-Date "04:00") `
    -ActionExe   $NewNflExe `
    -ActionArgs  "backup-snapshot --target `"$BackupPath`""

# --- Task 2: Fetch Teams (Pipeline-Wrapper) --------------------------------

Install-NewNflTask `
    -TaskName    "NewNFL-Fetch-Teams" `
    -Description "NEW NFL daily fetch+stage+core fuer Slice teams (T3.0A iterativ Step 1)" `
    -TriggerTime (Get-Date "05:00") `
    -ActionExe   $PsExe `
    -ActionArgs  "-ExecutionPolicy Bypass -NoProfile -File `"$RunSlice`" -Slice teams"

# --- Abschluss -------------------------------------------------------------

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Scheduled Tasks (iterativ Step 1) installiert" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host "Tasks:"
Write-Host "  NewNFL-Backup-Daily  @ 04:00  ->  $NewNflExe backup-snapshot --target $BackupPath"
Write-Host "  NewNFL-Fetch-Teams   @ 05:00  ->  run_slice.ps1 -Slice teams"
Write-Host ""
Write-Host "Manuelle Smoke-Trigger (Task sofort starten):" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName NewNFL-Backup-Daily"
Write-Host "  Start-ScheduledTask -TaskName NewNFL-Fetch-Teams"
Write-Host ""
Write-Host "Status nach Lauf pruefen:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName NewNFL-* | Get-ScheduledTaskInfo"
