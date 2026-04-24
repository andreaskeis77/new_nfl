# VPS-Deployment-Runbook — NEW NFL

**Status:** Aktionsanleitung, gültig ab T3.1-Start
**Letzte Aktualisierung:** 2026-04-24 (im Rahmen von [ADR-0034](../../adr/ADR-0034-vps-first-before-testphase.md))
**Konvention:** siehe [VPS_DOSSIER.md](VPS_DOSSIER.md) für alle Pfade, Ports, Task-Namen.

---

## 0. Wie dieses Runbook zu lesen ist

**Konventionen:**

- **`DEV-LAPTOP $`** — Befehl läuft auf deinem Entwicklungs-Laptop, bash in VS Code.
- **`VPS-ADMIN PS>`** — Befehl läuft auf dem Contabo-VPS über RDP-Session, **PowerShell als Administrator**. Wenn du PowerShell öffnest: rechtsklick → „Als Administrator ausführen". Titelleiste muss „Administrator: Windows PowerShell" zeigen.
- **`VPS-USER PS>`** — Befehl läuft auf dem VPS in einer **normalen** User-PowerShell. In diesem Runbook aktuell nicht genutzt, wird erst relevant wenn Least-Privilege-Pattern für Runtime-Tasks eingeführt wird.

**Struktur pro Schritt:**

1. **Ziel:** was dieser Schritt erreicht.
2. **Befehl:** exakt kopierbar in einem Codeblock, keine Platzhalter außer klar benannten Variablen oben im Abschnitt.
3. **Erwartete Ausgabe:** so sieht eine erfolgreiche Ausgabe aus.
4. **Bei Fehler:** typische Fehlerbilder und Reparaturpfade.

**Abbruch-Punkte:** dieses Runbook hat mehrere explizite STOP-Punkte zwischen Phasen. An jedem STOP: Output zurück an Claude, erst weiter nach OK.

---

## 1. RDP-Verbindung zum VPS aufbauen

### 1.1 Voraussetzung

Tailscale ist auf DEV-LAPTOP installiert und verbunden (das nutzt du schon für capsule).

### 1.2 Tailscale-IP des VPS ermitteln

**`DEV-LAPTOP $`**
```bash
tailscale status | grep -i vps
```

oder ohne `grep`:

**`DEV-LAPTOP $`**
```bash
tailscale status
```

**Erwartete Ausgabe (Beispiel):**
```
100.xxx.xxx.xxx    dev-laptop           andreas      windows   -
100.yyy.yyy.yyy    contabo-vps          andreas      windows   active
...
```

Notiere die Tailscale-IP des VPS (im Beispiel `100.yyy.yyy.yyy`). Im Rest dieses Runbooks wird sie als **`<VPS-TAILSCALE-IP>`** referenziert.

**Bei Fehler:**
- „Tailscale is stopped" → auf DEV-LAPTOP Tailscale-Client starten (Tray-Icon → Log in).
- VPS nicht in der Liste → auf dem VPS selbst (per Contabo-Webkonsole) `tailscale status` prüfen; ggf. Tailscale dort neu starten.

### 1.3 RDP öffnen

**`DEV-LAPTOP $`**
```bash
mstsc.exe /v:<VPS-TAILSCALE-IP>
```

Du wirst nach Admin-Credentials gefragt — die gleichen wie für das capsule-Setup.

**Erwartete Ausgabe:** RDP-Fenster öffnet sich, Windows-Desktop des VPS erscheint.

**Bei Fehler:**
- Timeout → Tailscale-Verbindung beider Seiten prüfen.
- „Die Anmeldeinformationen können nicht überprüft werden" → Anmeldename als `<VPS-HOSTNAME>\Administrator` eingeben statt nur `Administrator`.

---

## 2. Phase 3 — VPS-Inventarisierung

**Ziel:** festhalten, welche Python-Version, Git-Version, Disk/RAM, bestehende Tasks und belegte Ports auf dem VPS vorhanden sind. Danach weißt du und ich exakt, ob und was in Phase 4 (Bootstrap) installiert oder konfiguriert werden muss.

**STOP-Punkt am Ende:** du schickst mir die gesamten Ausgaben, ich schreibe daraus das Bootstrap-Script.

### 2.1 PowerShell als Administrator öffnen

Im RDP-Fenster:
1. Windows-Taste drücken.
2. „PowerShell" tippen.
3. Rechtsklick auf „Windows PowerShell" → **„Als Administrator ausführen"**.
4. Bestätigung „Ja" bei UAC-Prompt.
5. Titelleiste prüfen: muss **„Administrator: Windows PowerShell"** lesen.

### 2.2 Inventarisierungs-Block ausführen

**`VPS-ADMIN PS>`**
```powershell
Write-Host "=== PYTHON ===" -ForegroundColor Cyan
python --version
py -0p
Write-Host "`n=== GIT ===" -ForegroundColor Cyan
git --version
Write-Host "`n=== DISK (Laufwerk C:) ===" -ForegroundColor Cyan
Get-PSDrive C | Format-Table Name,Used,Free -AutoSize
Write-Host "`n=== MEMORY ===" -ForegroundColor Cyan
Get-CimInstance Win32_OperatingSystem | Select-Object @{N='TotalGB';E={[math]::Round($_.TotalVisibleMemorySize/1MB,2)}}, @{N='FreeGB';E={[math]::Round($_.FreePhysicalMemory/1MB,2)}}
Write-Host "`n=== SCHEDULED TASKS (nur Capsule- und NewNFL-Praefixe) ===" -ForegroundColor Cyan
Get-ScheduledTask | Where-Object { $_.TaskName -like "Capsule-*" -or $_.TaskName -like "NewNFL-*" } | Format-Table TaskName,State -AutoSize
Write-Host "`n=== LISTENING PORTS 8000-8010 ===" -ForegroundColor Cyan
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -ge 8000 -and $_.LocalPort -le 8010 } | Format-Table LocalAddress,LocalPort,OwningProcess -AutoSize
Write-Host "`n=== TAILSCALE STATUS ===" -ForegroundColor Cyan
tailscale status
Write-Host "`n=== CLOUDFLARED SERVICE ===" -ForegroundColor Cyan
Get-Service cloudflared | Format-Table Name,Status,StartType -AutoSize
Write-Host "`n=== EXISTIERENDE NEWNFL-ORDNER ===" -ForegroundColor Cyan
Get-Item C:\newNFL -ErrorAction SilentlyContinue
Get-Item "C:\newNFL-Backups" -ErrorAction SilentlyContinue
Write-Host "`n=== CAPSULE-ORDNER (nur Existenz-Check) ===" -ForegroundColor Cyan
Test-Path C:\CapsuleWardrobeRAG
Write-Host "`n=== FERTIG ===" -ForegroundColor Green
```

Das ist **ein einziger Kopier-Block**. Markiere den ganzen Block (Umschalt+Ende in VS Code), Strg+C, in die VPS-PowerShell Strg+V (oder rechtsklick), Enter.

### 2.3 Ausgabe sichern und zurückschicken

**Sichern:** markiere den gesamten Output im PowerShell-Fenster (rechtsklick → „Alles auswählen" → Enter zum Kopieren), paste in eine Textdatei oder direkt in den Chat zu mir.

### 2.4 Was ich aus der Ausgabe herauslesen werde

| Block | Was ich prüfe |
|---|---|
| PYTHON | Ist Python ≥ 3.11 installiert? Wenn ja: welche Version. Wenn nein: Bootstrap-Script muss Python-Installer enthalten oder du installierst manuell. |
| GIT | Git vorhanden? Sonst im Bootstrap installieren (`winget install Git.Git`). |
| DISK | Mindestens 10 GB frei? DuckDB + Raw-Landings können bei 15 Saisons Backfill deutlich wachsen. |
| MEMORY | Mind. 4 GB frei erwartet für Mart-Rebuild ohne Swap-Thrashing. |
| SCHEDULED TASKS | Zeigt, ob `Capsule-*`-Tasks laufen (erwartet: ja). Und ob schon `NewNFL-*`-Reste von früheren Versuchen existieren (erwartet: nein). |
| LISTENING PORTS | Port 8000 sollte von capsule belegt sein (erwartet). Port 8001 muss frei sein (darf in der Liste nicht erscheinen). |
| TAILSCALE | VPS-Hostname + Tailscale-IP bestätigen. Status `active`. |
| CLOUDFLARED | Service „Running" erwartet — wir fassen ihn nicht an, aber sein Zustand ist Kontext. |
| EXISTIERENDE NEWNFL-ORDNER | Darf nicht existieren (sonst Rest aus altem Versuch → mit mir klären). |
| CAPSULE-ORDNER | Sollte `True` zurückgeben. |

### 2.5 STOP — Output an Claude

**Schicke mir** den kompletten Output aus 2.2 (inkl. aller Abschnitt-Header). Ich antworte mit dem konkreten Phase-4-Bootstrap-Script (`vps_bootstrap.ps1`), das exakt zu deinem VPS-Zustand passt.

---

## 3. Phase 4 — Bootstrap

**Artefakt:** [deploy\windows-vps\vps_bootstrap.ps1](../../../deploy/windows-vps/vps_bootstrap.ps1) im Repo (committed 2026-04-24).

**Was das Skript tut:**
- prüft Python 3.12 via `py -3.12` (Python 3.14 auf VPS passt nicht zu pyproject.toml-Constraint `<3.14`)
- prüft git und die Existenz von `C:\newNFL` mit `.git`- und `pyproject.toml`-Datei
- legt Verzeichnisse an: `C:\newNFL\data\`, `C:\newNFL\data\db\`, `C:\newNFL\data\logs\`, `C:\newNFL-Backups\`
- erstellt Venv `C:\newNFL\.venv` mit Python 3.12
- installiert NEW NFL editable (`pip install -e .`) in der Venv
- ruft `new-nfl bootstrap` → DuckDB-Schema wird angelegt, Ontologie wird aktiviert
- Smoke-Check: `new-nfl registry-list` zeigt die 16 Mart-Keys
- wirft bei jedem Fehler eine Exception und bricht ab — kein halb-fertiger Zustand

### 3.1 Repo auf VPS klonen

Der Clone-Schritt ist absichtlich **nicht** im Bootstrap-Skript, damit der Operator sehen kann, was gezogen wird, bevor das Skript startet.

**`VPS-ADMIN PS>`**
```powershell
Set-Location C:\
git clone https://github.com/andreaskeis77/new_nfl.git C:\newNFL
```

**Erwartete Ausgabe:**
```
Cloning into 'C:\newNFL'...
remote: Enumerating objects: ...
remote: Counting objects: ...
Receiving objects: 100% (...)
Resolving deltas: 100% (...)
```

**Bei Fehler:**
- `C:\newNFL exists and is not empty` → Pfad existiert schon. Nicht löschen, Operator fragen.
- SSL-/Proxy-Fehler → `git --version` prüfen, ggf. `git config --global http.sslBackend schannel`.

### 3.2 Bootstrap-Skript starten

**`VPS-ADMIN PS>`**
```powershell
powershell -ExecutionPolicy Bypass -File C:\newNFL\deploy\windows-vps\vps_bootstrap.ps1
```

**Erwartete Ausgabe:** Block-für-Block `==> …`-Zeilen in Cyan, am Ende:
```
================================================================
NEW NFL Bootstrap abgeschlossen
================================================================
Repo:         C:\newNFL
Venv:         C:\newNFL\.venv (Python 3.12)
...
```

**Dauer:** 2–4 Minuten (meiste Zeit ist `pip install -e .` für Abhängigkeiten).

**Bei Fehler:** Skript wirft Exception mit klarem Context-String (z. B. `"Schritt 'pip install -e .' fehlgeschlagen (ExitCode=1)"`) und bricht ab. Output vollständig an mich schicken, ich analysiere.

### 3.3 Nach-Bootstrap-Check

**`VPS-ADMIN PS>`**
```powershell
Set-Location C:\newNFL
.\.venv\Scripts\pytest.exe -v --tb=short 2>&1 | Tee-Object -FilePath $env:TEMP\newnfl-bootstrap-pytest.log
```

**Erwartete Ausgabe:** `445 passed` am Ende. Laufzeit auf VPS darf länger sein als auf DEV-LAPTOP (dort 9:11), z. B. 15 Minuten — keine Regression, nur CPU-Unterschied.

**Bei Fehler:** Testliste mit `FAILED`-Zeilen isolieren, an mich schicken. Log liegt unter `%TEMP%\newnfl-bootstrap-pytest.log`.

### 3.4 STOP — Output an Claude

Zurück an mich:
1. Ob das Bootstrap-Skript **sauber durchgelaufen** ist (letzte grüne Ausgabe vorhanden).
2. Ob die Full-Suite **grün** ist (`445 passed`).
3. Bei Abweichung: den kompletten Fehler-Output.

Erst dann starte ich Phase 5 (Scheduled Tasks).

---

## 4. Phase 5 — Scheduled Tasks anlegen (iterativ)

**Artefakte:**
- [deploy\windows-vps\run_slice.ps1](../../../deploy/windows-vps/run_slice.ps1) — Pipeline-Wrapper pro Slice (fetch → stage → core mit impliziter mart-rebuild).
- [deploy\windows-vps\vps_install_tasks.ps1](../../../deploy/windows-vps/vps_install_tasks.ps1) — **Step 1** legt nur `NewNFL-Backup-Daily` und `NewNFL-Fetch-Teams` an. Die restlichen 6 Fetch-Tasks folgen nach erfolgreichem ersten Scheduler-Tag (Step 2 kommt mit einem späteren Skript-Commit).

**Grund für iterativen Rollout:** statt 8 Tasks gleichzeitig loszulassen und bei einem morgendlichen Fehler nicht zu wissen, welche Stelle schuld ist, testen wir erst **Backup** (einfach, kein externer HTTP-Call) und **Teams** (der konservativste Slice, kleine CSV). Wenn diese zwei grün sind, haben wir Vertrauen in Scheduler-Mechanik und Wrapper-Skript.

### 4.1 Update-Pull auf dem VPS

**`VPS-ADMIN PS>`**
```powershell
Set-Location C:\newNFL
git pull origin main
```

Erwartet: pulls `run_slice.ps1` und `vps_install_tasks.ps1` in den bestehenden Clone.

### 4.2 Manual-Smoke Backup

Wrapper-Skript `run_backup.ps1` erzeugt einen Zeitstempel-basierten ZIP-Namen und ruft `backup-snapshot` mit explizitem `--target`-Pfad auf (die CLI erwartet einen Datei-Pfad, nicht ein Verzeichnis).

**`VPS-ADMIN PS>`**
```powershell
powershell -ExecutionPolicy Bypass -File C:\newNFL\deploy\windows-vps\run_backup.ps1
```

**Erwartete Ausgabe:** Zeilen `TARGET_ZIP=…`, `PAYLOAD_HASH=…`, `MART_TABLE_COUNT=…`, letzte Zeile `=== DONE: C:\newNFL-Backups\snapshot_YYYYMMDD_HHMMSS.zip ===` in Grün.

**Verifikation:**
```powershell
Get-ChildItem C:\newNFL-Backups\ | Format-Table Name,Length,LastWriteTime
```
Erwartet: eine frische `snapshot_*.zip` mit wenigen KB Größe (leere Fresh-DB).

### 4.3 Manual-Smoke Teams-Slice

**`VPS-ADMIN PS>`**
```powershell
powershell -ExecutionPolicy Bypass -File C:\newNFL\deploy\windows-vps\run_slice.ps1 -Slice teams
```

**Erwartete Ausgabe:**
```
=== run_slice: Adapter=nflverse_bulk Slice=teams ===
Log-Destination: file:C:\newNFL\data\logs

>> fetch-remote
ADAPTER_ID=nflverse_bulk
...
STATUS=success

>> stage-load
...
ROW_COUNT=<>0

>> core-load (triggert mart-rebuild implizit)
...
CORE_ROW_COUNT=<>0
MART_ROW_COUNT=<>0

=== DONE: Adapter=nflverse_bulk Slice=teams ===
```

**Dauer:** 10–30 Sekunden je nach nflverse-Antwortzeit.

**Bei Fehler:** Skript bricht mit Exception ab und zeigt welcher Schritt fehlgeschlagen ist. Output komplett an Claude.

### 4.4 Install-Tasks (nur wenn 4.2 und 4.3 grün)

**`VPS-ADMIN PS>`**
```powershell
powershell -ExecutionPolicy Bypass -File C:\newNFL\deploy\windows-vps\vps_install_tasks.ps1
```

**Erwartete Ausgabe:**
```
==> NewNFL-Backup-Daily
  OK -> naechster Tick: 04:00
==> NewNFL-Fetch-Teams
  OK -> naechster Tick: 05:00
================================================================
Scheduled Tasks (iterativ Step 1) installiert
================================================================
```

### 4.5 Verifikation in der Task-Scheduler-GUI

1. Windows-Taste + „Aufgabenplanung" tippen, Enter.
2. Links „Aufgabenplanungsbibliothek" → Root-Ebene.
3. In der Mitte-Liste `NewNFL-Backup-Daily` und `NewNFL-Fetch-Teams` suchen.
4. Beide müssen Status „Bereit" zeigen, nächste Laufzeit morgen 04:00/05:00.

Oder via PowerShell:

**`VPS-ADMIN PS>`**
```powershell
Get-ScheduledTask -TaskName "NewNFL-*" | Format-Table TaskName,State,@{N='NextRun';E={(Get-ScheduledTaskInfo $_).NextRunTime}} -AutoSize
```

### 4.6 Optional: Heute noch einen Task-Lauf erzwingen

Wenn du noch heute sehen willst, dass der **Task-Mechanismus** funktioniert (nicht nur der Manual-Lauf aus 4.2/4.3), kannst du die Tasks sofort manuell triggern:

**`VPS-ADMIN PS>`**
```powershell
Start-ScheduledTask -TaskName "NewNFL-Backup-Daily"
Start-Sleep -Seconds 20
Start-ScheduledTask -TaskName "NewNFL-Fetch-Teams"
Start-Sleep -Seconds 60
Get-ScheduledTask -TaskName "NewNFL-*" | Get-ScheduledTaskInfo | Format-Table TaskName,LastRunTime,LastTaskResult -AutoSize
```

`LastTaskResult=0` ist der Erfolg. Jede andere Zahl ist Fehler — Details aus dem Task-Scheduler-Historien-Tab oder im JSONL-Log unter `C:\newNFL\data\logs\`.

### 4.7 STOP — Bericht an Claude

Zurück an mich:
1. Output von 4.2 (Backup-Smoke) und 4.3 (Teams-Smoke).
2. Output von 4.4 (Task-Install).
3. Optional: Output von 4.6 (erzwungener Task-Lauf).

Morgen nach den echten Triggern (04:00 + 05:00): `Get-ScheduledTaskInfo`-Output aus 4.5 mit `LastRunTime` und `LastTaskResult` an mich. Wenn beide grün sind, schreibe ich das Folge-Skript für die restlichen 6 Fetch-Tasks.

---

## 5. Phase 6 — Smoke-Test (T3.1-DoD)

**In dieser Phase erzeugt:** `deploy\windows-vps\vps_smoke_test.ps1`.

**Durch das Script abgedeckt:**
- Full-Suite `pytest -v` auf VPS einmal laufen lassen (muss grün sein, 445/445).
- Manueller Lauf einer Slice (`fetch-remote` → `stage-load` → `core-load` → `mart-rebuild`) für z. B. Teams-Slice.
- `backup-snapshot` + `verify-snapshot` + `restore-snapshot` End-to-End.
- Web-UI-Check: `Invoke-WebRequest http://127.0.0.1:8001/` vom VPS selbst **und** `curl http://<VPS-TAILSCALE-IP>:8001/` vom DEV-LAPTOP.

**Operator-Schritt:**

**`VPS-ADMIN PS>`**
```powershell
# wird in Phase 6 konkretisiert
Set-Location C:\newNFL
powershell -ExecutionPolicy Bypass -File .\deploy\windows-vps\vps_smoke_test.ps1
```

**Weiterer Check vom Laptop:**

**`DEV-LAPTOP $`**
```bash
curl -sS http://<VPS-TAILSCALE-IP>:8001/ | head -20
```

Erwartet: HTML-Output mit `<title>…</title>` und Home-Dashboard-Inhalt.

**24-Stunden-Beobachtung (T3.1-DoD):** nach erfolgreichem Smoke lässt du den `NewNFL-Worker` 24 Stunden laufen. Ein Daily-Trigger feuert mindestens einmal (nächstens 04:00 und 05:00–05:30). Am nächsten Tag:

**`DEV-LAPTOP $`**
```bash
# per Browser öffnen
start http://<VPS-TAILSCALE-IP>:8001/
```

Home-Freshness-Dashboard muss `last_event_at`-Ticks pro Slice zeigen, die vom vergangenen Nacht-Trigger stammen.

**STOP-Punkt:** T3.1-DoD-Check an Claude. Ab hier startet T3.0 (Testphase).

---

## 6. Update-Pfad (für spätere Änderungen nach T3.1)

**Nach jedem Code-Change auf DEV-LAPTOP:**

### 6.1 Auf DEV-LAPTOP

**`DEV-LAPTOP $`**
```bash
cd c:/projekte/newnfl
# Arbeitsflow: ändern, testen, committen
git -C c:/projekte/newnfl status
git -C c:/projekte/newnfl push origin main
```

### 6.2 Auf VPS update einspielen

**`VPS-ADMIN PS>`**
```powershell
# wird in Phase 4 als Teil von vps_update_from_git.ps1 konkretisiert
Set-Location C:\newNFL
powershell -ExecutionPolicy Bypass -File .\deploy\windows-vps\vps_update_from_git.ps1
```

**Was das Script tut (wird in Phase 4 geschrieben):**
- `git fetch origin main`
- `git log HEAD..origin/main --oneline` — zeigt was neu käme, vor dem Pull
- `git pull --ff-only origin main` — strict fast-forward, keine Merges auf VPS
- `pip install -e .` (falls `pyproject.toml` geändert)
- optional `pytest -v` als Post-Update-Smoke
- Worker-Task neu starten: `Restart-ScheduledTask -TaskName NewNFL-Worker`

**Bei Fehler:**
- `git pull` weigert sich → Working-Tree auf VPS nicht clean. **Nicht** überschreiben, zuerst Operator fragen (kann Evidence von manuellem Debug-Eingriff sein).
- `pytest` rot nach Update → Rollback auf vorherigen Commit: `git reset --hard HEAD~1` nach Rücksprache.

---

## 7. Fehlerbilder und Reparaturpfade

### 7.1 Worker läuft nicht

**Symptom:** Home-Dashboard zeigt keine neuen `last_event_at`-Ticks, keine Queue-Bewegung.

**Prüfen:**

**`VPS-ADMIN PS>`**
```powershell
Get-ScheduledTask -TaskName NewNFL-Worker | Get-ScheduledTaskInfo
```

Erwartet: `LastRunTime` und `NextRunTime` beide gefüllt, `LastTaskResult` = 0.

**Fix:**

**`VPS-ADMIN PS>`**
```powershell
Stop-ScheduledTask -TaskName NewNFL-Worker
Start-ScheduledTask -TaskName NewNFL-Worker
```

### 7.2 Queue wächst, aber nichts wird abgearbeitet

**Prüfen:** Worker-Log in `C:\newNFL\data\logs\events_YYYYMMDD.jsonl`. Letzte 50 Zeilen:

**`VPS-ADMIN PS>`**
```powershell
Get-Content "C:\newNFL\data\logs\events_$(Get-Date -Format yyyyMMdd).jsonl" -Tail 50
```

**Typische Ursachen:**
- Exception beim Executor → Logs zeigen Stack-Trace, Root-Cause fixen auf DEV-LAPTOP.
- Quarantäne-Case offen → `new-nfl list-quarantine --status open` prüfen und resolven.

### 7.3 Port 8001 belegt von anderem Prozess

**Prüfen:**

**`VPS-ADMIN PS>`**
```powershell
Get-NetTCPConnection -LocalPort 8001 -State Listen | Format-Table LocalAddress,LocalPort,OwningProcess -AutoSize
Get-Process -Id <PID aus oben>
```

**Fix:** der blockierende Prozess ist wahrscheinlich ein hängender `new-nfl run-worker`-Prozess. `Stop-Process -Id <PID> -Force`.

### 7.4 Backup-Ordner läuft voll

**Prüfen:**

**`VPS-ADMIN PS>`**
```powershell
Get-ChildItem C:\newNFL-Backups\ | Sort-Object LastWriteTime -Descending | Select-Object -First 30 | Format-Table Name,Length,LastWriteTime
```

**Fix:** manuelle Löschung alter Snapshots (keine Auto-Retention in v1.0).

**`VPS-ADMIN PS>`**
```powershell
# Vorsicht: löscht Snapshots älter als 30 Tage
Get-ChildItem C:\newNFL-Backups\*.zip | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item
```

### 7.5 Tailscale-IP hat sich geändert

Unwahrscheinlich (Tailscale-IPs sind stabil), aber wenn doch:
- `tailscale status` auf beiden Seiten neu prüfen.
- Neue IP in Browser-Bookmarks und Monitoring-Scripten aktualisieren.

---

## 8. Referenzen

- [VPS_DOSSIER.md](VPS_DOSSIER.md) — Konventionen, Pfade, Ports, Task-Namen, Abgrenzung zu capsule.
- [ADR-0034](../../adr/ADR-0034-vps-first-before-testphase.md) — Entscheidung T3.1 vor T3.0.
- [T2_3_PLAN.md §10](../../T2_3_PLAN.md) — T3.1-Scope und DoD.
- [capsule-VPS-Deployment-Runbook](https://github.com/andreaskeis77/capsule/blob/main/docs/VPS_DEPLOYMENT_RUNBOOK.md) — Vorbild-Muster für die `vps_*.ps1`-Script-Familie.
