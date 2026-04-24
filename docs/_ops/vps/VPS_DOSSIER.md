# VPS-Dossier — NEW NFL auf Contabo-Windows-VPS

**Status:** Referenz-Dokument, gültig ab T3.1-Start
**Letzte Aktualisierung:** 2026-04-24 (im Rahmen von [ADR-0034](../../adr/ADR-0034-vps-first-before-testphase.md))

## 1. Zweck und Scope

Dieses Dokument beschreibt die **verbindlichen Konventionen** für den NEW-NFL-Betrieb auf dem Contabo-Windows-VPS: Pfade, Ports, Task-Namen, Backup-Ablage, Abgrenzung zum koexistierenden `capsule`-Projekt.

**Nicht hier:** Schritt-für-Schritt-Anweisungen für Deployment. Die stehen im [VPS_DEPLOYMENT_RUNBOOK.md](VPS_DEPLOYMENT_RUNBOOK.md).

**Auch nicht hier:** VPS-Grundausbau (Tailscale-RDP, Windows-Hardening, `cloudflared`-Service). Das ist über das `capsule`-Projekt bereits auf dem VPS etabliert und wird aus dessen Doku referenziert statt dupliziert.

## 2. Zielumgebung

**Provider:** Contabo, Windows-VPS (gemeinsam genutzt mit dem `capsule`-Projekt).

**Hostname:** `vmd193069`
**Tailscale-IP:** `100.71.205.5` (stabil, aus Tailnet-Admin-Session ermittelt 2026-04-24)
**Admin-User:** `srv-ops-admin` (separater Operations-User, nicht der Standard-`Administrator`-Account)
**Gesamt-RAM:** ~12 GB, ausreichend Kopfluft für Mart-Rebuilds ohne Swap-Thrashing.
**Disk C:** ~200 GB, ~178 GB frei (Stand 2026-04-24).

**Zugang:** ausschließlich über Tailscale-RDP. Kein Public-RDP, kein offener 3389-Port im Internet. RDP-Aufruf vom DEV-LAPTOP: `mstsc.exe /v:100.71.205.5`.

**Koexistenz mit capsule:** der VPS hostet bereits das `capsule`-Projekt unter `C:\CapsuleWardrobeRAG` mit eigenem Port (`127.0.0.1:8000`, verifiziert belegt durch PID 4636 am 2026-04-24), eigenem Task-Namensraum (`Capsule-*` — `Capsule-API` ist `Ready`, `Capsule-ngrok` ist `Disabled` seit Cloudflare-Umstellung) und eigener Cloudflare-Tunnel-Einbindung (`Contabo-Wardrobe` → `capsule-studio.de` + `api.capsule-studio.de`, Service `cloudflared` läuft mit `Automatic`-Startup). NEW NFL darf die `capsule`-Infrastruktur **nicht** anfassen — weder den `cloudflared`-Service, noch die `Capsule-*`-Tasks, noch den `C:\CapsuleWardrobeRAG`-Pfad.

## 3. Öffentlichkeit / Erreichbarkeit — Tailscale-only

**Bewusste Architektur-Entscheidung:** NEW NFL wird **nicht** über Cloudflare Tunnel veröffentlicht. Siehe [ADR-0034](../../adr/ADR-0034-vps-first-before-testphase.md).

- Web-UI und CLI sind ausschließlich über das Tailnet des Operators erreichbar.
- Kein Cloudflare-Access, keine öffentliche Subdomain, kein DNS-Eintrag.
- Backend bindet auf `127.0.0.1:8001`, nicht auf `0.0.0.0`.
- Zugriff vom DEV-LAPTOP aus via `http://<VPS-TAILSCALE-IP>:8001/`.

**Falls später gewünscht** (z. B. Zugriff vom Smartphone): zusätzlicher `cloudflared`-Tunnel-Eintrag oder Route ist jederzeit nachrüstbar ohne Architektur-Änderung — aber in v1.0 bewusst weggelassen, weil jeder öffentliche Endpoint Wartungs- und Angriffsfläche ist.

## 4. Pfad-Konventionen

| Zweck | Pfad | Anmerkung |
|---|---|---|
| Repo-Checkout | `C:\newNFL` | Git-Clone von `main` |
| Python-Venv | `C:\newNFL\.venv` | eigene Venv pro Repo, keine Globals |
| Datenbank-Root | `C:\newNFL\data\` | `new_nfl.db` + Artefakte |
| Raw-/Stage-Landings | `C:\newNFL\data\raw\` und `C:\newNFL\data\stg\` | wie auf DEV-LAPTOP |
| Logs (JSONL, T2.7B) | `C:\newNFL\data\logs\` | `events_YYYYMMDD.jsonl` |
| Backup-Ablage | `C:\newNFL-Backups\` | **außerhalb** des Repo-Pfads — Repo-Update löscht keine Backups |
| Deploy-Scripts | `C:\newNFL\deploy\windows-vps\` | aus Repo, Git-getrackt |

**Wichtig:** Daten und Repo sind getrennt. `git pull` auf `C:\newNFL` berührt niemals `C:\newNFL-Backups\` und nur dann `C:\newNFL\data\`, wenn jemand das Data-Verzeichnis versehentlich im Repo landet (darf nicht passieren, ist in `.gitignore`).

## 5. Port und Binding

| Komponente | Bindung | Sichtbarkeit |
|---|---|---|
| NEW-NFL-Backend | `127.0.0.1:8001` | nur lokal, Tailscale routet auf die VPS-Tailnet-IP |
| capsule-Backend | `127.0.0.1:8000` | unberührt, weiterhin über Cloudflare Tunnel öffentlich |

Kein Konflikt, kein Firewall-Eintrag nötig — Tailscale-Verbindungen sind kein "öffentlicher" Traffic im Windows-Defender-Sinne.

## 6. Scheduled-Task-Konventionen

**Präfix:** alle NEW-NFL-Tasks beginnen mit `NewNFL-`. Vollständig reserviert für NEW NFL — capsule nutzt den Präfix `Capsule-`.

**Architektur-Entscheidung (geklärt 2026-04-24 bei der Phase-4-CLI-Analyse):** jeder `new-nfl`-CLI-Call geht intern bereits durch den Runner (`_invoke_via_runner` in [cli.py](../../../src/new_nfl/cli.py) macht `register_job` → `enqueue_job` → `run_worker_once` in einem Schuss und schreibt `meta.job_run`-Evidence gemäß ADR-0025). Deshalb ist **kein dauerhafter `NewNFL-Worker`-Service** nötig — jeder Scheduled-Task ist selbstständig und erzeugt eigene Runner-Evidence. Die ursprüngliche Idee, einen 24/7-Worker via Auto-Restart-Task zu betreiben, wurde verworfen.

**Pipeline pro Slice** (Wrapper [`run_slice.ps1`](../../../deploy/windows-vps/run_slice.ps1)):
1. `fetch-remote --adapter-id nflverse_bulk --slice <slice> --execute`
2. `stage-load --adapter-id nflverse_bulk --slice <slice> --execute`
3. `core-load --adapter-id nflverse_bulk --slice <slice> --execute` — triggert `mart-rebuild` implizit

Der Wrapper setzt außerdem `NEW_NFL_LOG_DESTINATION=file:C:\newNFL\data\logs` (T2.7B), damit JSONL-Events auch bei Task-Läufen persistiert werden (stdout geht sonst im Task-Scheduler verloren).

**Task-Liste (Voll-Ausbau, schrittweise durch iterativen Rollout umgesetzt):**

| Task-Name | Aktion | Trigger | Adapter/Slice |
|---|---|---|---|
| `NewNFL-Backup-Daily` | `new-nfl backup-snapshot --target C:\newNFL-Backups\` | täglich 04:00 | — |
| `NewNFL-Fetch-Teams` | `run_slice.ps1 -Slice teams` | täglich 05:00 | `nflverse_bulk`/`teams` |
| `NewNFL-Fetch-Games` | `run_slice.ps1 -Slice games` | täglich 05:05 | `nflverse_bulk`/`games` |
| `NewNFL-Fetch-Players` | `run_slice.ps1 -Slice players` | täglich 05:10 | `nflverse_bulk`/`players` |
| `NewNFL-Fetch-Rosters` | `run_slice.ps1 -Slice rosters` | täglich 05:15 | `nflverse_bulk`/`rosters` |
| `NewNFL-Fetch-TeamStats` | `run_slice.ps1 -Slice team_stats_weekly` | täglich 05:20 | `nflverse_bulk`/`team_stats_weekly` |
| `NewNFL-Fetch-PlayerStats` | `run_slice.ps1 -Slice player_stats_weekly` | täglich 05:25 | `nflverse_bulk`/`player_stats_weekly` |
| `NewNFL-Fetch-Schedule` | `run_slice.ps1 -Slice schedule_field_dictionary` | täglich 05:30 | `nflverse_bulk`/`schedule_field_dictionary` |

**Begründung der Uhrzeiten:**
- **04:00 Backup:** vor den Fetch-Jobs, damit der Backup einen konsistenten Vor-Tages-Stand sichert.
- **05:00–05:30 Fetch-Jobs gestaffelt in 5-Minuten-Schritten:** auch wenn die Jobs selbstständig laufen, entlastet die Staffelung die nflverse-Endpoints und macht Logs sauber lesbar.

**Iterativer Rollout (T3.1 Phase 5):** Erst nur `NewNFL-Backup-Daily` + `NewNFL-Fetch-Teams` anlegen und einen vollen Tages-Zyklus beobachten, dann die restlichen sechs Fetch-Tasks nachziehen. Siehe [VPS_DEPLOYMENT_RUNBOOK.md §4](VPS_DEPLOYMENT_RUNBOOK.md).

**Task-Principal:** alle Tasks laufen als `srv-ops-admin` mit `RunLevel Highest` (für Datei-Zugriff auf `C:\newNFL\` und `C:\newNFL-Backups\`). `StartWhenAvailable=True` fängt verpasste Trigger (z. B. Windows-Update-Reboot) nach; Batterie-Policies sind für den VPS irrelevant, werden aber explizit gesetzt für Portabilität zu Laptops.

## 7. Git-Konventionen auf dem VPS

- **Branch:** ausschließlich `main`. Kein Feature-Branch-Work auf dem VPS.
- **Updates:** über `deploy\windows-vps\vps_update_from_git.ps1` (kommt in Phase 4). Nie manuell `git pull`, weil das Hook-Gates umgehen kann.
- **Keine Commits auf VPS:** Entwicklung passiert ausschließlich auf DEV-LAPTOP. VPS zieht nur `git pull`. Hotfixes direkt auf dem VPS sind **verboten** — stattdessen auf DEV-LAPTOP fixen, pushen, dann VPS updaten.
- **Clean-State-Erwartung:** `git status` auf VPS muss jederzeit clean sein. Wenn nicht: Warnung, nicht blind überschreiben — erst Operator fragen.

## 8. Python und Toolchain

**Verbindlich:** Python **3.12** via `py -3.12`. Authoritative Quelle ist [pyproject.toml](../../../pyproject.toml) mit `requires-python = ">=3.12,<3.14"` — Python 3.14 ist explizit ausgeschlossen, Python 3.13 wäre erlaubt aber nicht empfohlen.

**VPS-Stand (2026-04-24):** Python 3.14.3 ist der default (`python --version`), Python 3.12 ist zusätzlich installiert unter `C:\Users\srv-ops-admin\AppData\Local\Programs\Python\Python312\python.exe`. Deshalb **nie** `python` direkt aufrufen, sondern immer `py -3.12` oder den expliziten Venv-Python `C:\newNFL\.venv\Scripts\python.exe`. DEV-LAPTOP läuft mit Python 3.12.0 — Parität zum VPS gewährleistet.

**Venv-Setup (wird durch `vps_bootstrap.ps1` automatisiert):**
```powershell
py -3.12 -m venv C:\newNFL\.venv
C:\newNFL\.venv\Scripts\pip.exe install --upgrade pip
C:\newNFL\.venv\Scripts\pip.exe install -e C:\newNFL
```

**Kein `pip install --user`, kein globales `pip install`.** Alle Abhängigkeiten landen in der Venv. Ruft man später `new-nfl` auf, geht das über `C:\newNFL\.venv\Scripts\new-nfl.exe` oder — mit aktivierter Venv — über den kurzen `new-nfl`-Namen.

## 9. Abgrenzung zum capsule-Projekt

| Aspekt | capsule | NEW NFL |
|---|---|---|
| Repo-Pfad | `C:\CapsuleWardrobeRAG` | `C:\newNFL` |
| Port | `127.0.0.1:8000` | `127.0.0.1:8001` |
| Task-Präfix | `Capsule-*` | `NewNFL-*` |
| Öffentliche Erreichbarkeit | Cloudflare Tunnel (`capsule-studio.de`, `api.capsule-studio.de`) | keine — Tailscale-only |
| Logs | `C:\CapsuleWardrobeRAG\logs\vps\` | `C:\newNFL\data\logs\` |
| Backup-Ablage | (nicht dokumentiert im capsule-Repo) | `C:\newNFL-Backups\` |

**Non-Interference-Regel:** NEW NFL ändert niemals Dateien oder Services, die zu capsule gehören. `cloudflared`-Service-Konfiguration ist tabu. `Capsule-*`-Tasks sind tabu. Bei Zweifel: nicht anfassen, Operator fragen.

## 10. Sicherheitsprinzipien

- **API bindet auf `127.0.0.1`**, nicht auf `0.0.0.0`. Kein Listen-auf-allen-Interfaces. Tailscale routet von außen auf die VPS-Tailnet-IP und erreicht das Backend über die Loopback-Bindung.
- **`.env` ist VPS-lokal.** Wird nicht ins Repo commitet (`.gitignore`), wird beim `vps_update_from_git.ps1` nicht überschrieben.
- **Keine Geheimnisse in Tasks.** Scheduled Tasks rufen CLI-Befehle auf, die `.env` aus der Venv laden. Keine Credentials in Task-Argumenten.
- **Admin-Privileg nur zum Task-Setup.** Der `NewNFL-Worker`-Task läuft als Admin (für `schtasks`-Trigger-Events), aber CLI-Aufrufe wechseln intern nicht den User.

## 11. Backup-Strategie

**Zwei-Linien-Ansatz:**

1. **Anwendungs-Backup (primär):** `new-nfl backup-snapshot` (CLI aus T2.7C) legt täglich um 04:00 einen deterministischen Snapshot-ZIP in `C:\newNFL-Backups\` ab. Inklusive `verify-snapshot`-Prüfung unmittelbar nach Schreib-Abschluss.
2. **Provider-Backup (sekundär):** Contabo-Snapshots des ganzen VPS, unabhängig vom Anwendungs-Backup. Schutz gegen katastrophalen Hardware-Verlust.

**In v1.0 weggelassen:**
- **Automatische Retention.** `C:\newNFL-Backups\` wächst unbegrenzt. Operator löscht alte Snapshots manuell. Auto-Retention ist v1.1-Kandidat (analog zu `trim-run-events` aus T2.7E-1).
- **Offsite-Sync auf DEV-LAPTOP** via Tailnet ist geplant, aber kein T3.1-Blocker. Folgearbeit nach T3.0.
- **Restore-Routine als Scheduled Task.** Restore ist CLI-only und bewusst manuell — niemals automatisch.

**Restore-Drill (T3.0F):** mindestens einmal während T3.0 auf dem VPS: Backup erstellen → DB löschen → Restore → alle 10 Pflicht-Views rendern → keine fehlende Daten. Dokumentation im Restore-Lauf-Protokoll.

## 12. Monitoring und Health

**In v1.0 minimal, explizit dokumentiert:**

- **CLI-Health-Probe** (T2.7A): `new-nfl health-probe --kind <name>` gibt Shell-Exit-Code 0 oder ≠0 zurück. Kann von externen Monitoring-Scripten gepollt werden.
- **HTTP-Health-Endpoint:** in v1.0 **nicht** exponiert (Restrisiko #5 aus v1.0.0-laptop.md). Wird mit T2.9 / T2.6I nachgezogen.
- **Dashboard:** Home-Freshness-View unter `http://<VPS-TAILSCALE-IP>:8001/` zeigt `last_event_at` pro Slice. Manueller Browser-Check durch Operator 2× pro Woche.

**Keine Alerts, keine Pager, kein 24/7-Monitoring in v1.0.** Das ist nicht Ziel eines Single-Operator-Systems.

## 13. Referenzen

- [ADR-0034 — VPS-Migration vor Testphase](../../adr/ADR-0034-vps-first-before-testphase.md)
- [T2_3_PLAN.md §10](../../T2_3_PLAN.md) — T3.1-Scope-Definition
- [v1.0.0-laptop Release-Evidence](../releases/v1.0.0-laptop.md) — offene Restrisiken, relevant für T3.0 auf VPS
- [VPS_DEPLOYMENT_RUNBOOK.md](VPS_DEPLOYMENT_RUNBOOK.md) — Schritt-für-Schritt für den Operator
- [capsule-VPS-Deployment-Runbook](https://github.com/andreaskeis77/capsule/blob/main/docs/VPS_DEPLOYMENT_RUNBOOK.md) — VPS-Grundausbau (Referenz, nicht hier dupliziert)
- [capsule-VPS-Access-Runbook](https://github.com/andreaskeis77/capsule/blob/main/docs/RUNBOOK_VPS_ACCESS_AND_CLOUDFLARE.md) — Tailscale-RDP-Setup (Referenz)
- [capsule-VPS-Hardening-Runbook](https://github.com/andreaskeis77/capsule/blob/main/docs/RUNBOOK_VPS_WINDOWS_HARDENING.md) — Windows-Hardening (Referenz)
- ADR-0005 — Scheduler and VPS runtime model frame
- ADR-0026 — Ontology as code (begründet Python-3.11-Minimum wegen `tomllib`)
- ADR-0033 — Registry-Pattern (Worker-Architektur-Kontext)
