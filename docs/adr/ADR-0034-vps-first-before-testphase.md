# ADR-0034: VPS-Migration vor Testphase — T3.1 vor T3.0

## Status
Accepted (2026-04-24, im Anschluss an T2.8 v1.0-Cut mit Operator entschieden)

## Kontext

T2.8 hat den v1.0-Cut auf DEV-LAPTOP markiert (Tag `v1.0.0-laptop`, 2026-04-24). Der ursprüngliche Plan aus [T2_3_PLAN.md](../T2_3_PLAN.md) sah anschließend folgende Reihenfolge vor:

1. **T3.0 Testphase** auf DEV-LAPTOP (Juli 2026, ~4 Wochen) — Scheduler-Automation, Designed Degradation, Backfill-Lasttest, Backup/Restore-Drill.
2. **T3.1 VPS-Migration** danach (Ende Juli / Anfang August 2026) — Deploy auf den bereits vorhandenen Contabo-Windows-VPS, Cloudflare Tunnel, 7-Tage-Parallel-Lauf Laptop + VPS.

Bei der Session-Planung 2026-04-24 direkt nach dem v1.0-Cut ist ein **struktureller Plan-Fehler** aufgefallen:

- **T3.0A-DoD** verlangt „3 Tage stabiler Tick-Stream" auf DEV-LAPTOP — setzt implizit voraus, dass der Laptop 24/7 läuft.
- **T3.1-DoD** verlangt „7 Tage Parallel-Lauf VPS + Laptop mit identischen Outputs" — setzt ebenfalls Always-on-Laptop voraus.
- **Reale Laptop-Nutzung:** nachts aus, untertags unregelmäßig, Standby/Reboot-Zyklen unkontrolliert. Ein 4-Wochen-Scheduler-Test auf dieser Maschine kann den DoD nicht sauber nachweisen — Lücken im Tick-Stream sind nicht von Scheduler-Bugs unterscheidbar.
- **Der VPS existiert bereits** und wird produktiv für das `capsule`-Projekt genutzt (siehe [capsule-Doku](https://github.com/andreaskeis77/capsule/tree/main/docs)). Tailscale-RDP, Windows-Hardening und `cloudflared`-Service sind dort bereits aufgesetzt — für NEW NFL entfällt deshalb der VPS-Grundausbau.

Die Konsequenz: **Die Testphase muss dort laufen, wo der Scheduler dauerhaft laufen kann**, und das ist der VPS, nicht der Laptop.

## Entscheidung

Wir tauschen die Reihenfolge:

1. **T3.1 VPS-Migration** wird vorgezogen auf **Juni-Ende / Anfang Juli 2026**.
2. **T3.0 Testphase** läuft anschließend **auf dem VPS**, nicht auf DEV-LAPTOP. Zielkorridor bleibt Juli 2026, ~4 Wochen.

Zusätzliche Präzisierungen für T3.1 (NEW-NFL-spezifisch, weichen vom `capsule`-Deployment ab):

- **Tailscale-only** — NEW NFL wird nicht über Cloudflare Tunnel veröffentlicht. Web-UI und CLI sind ausschließlich über das Tailnet des Operators erreichbar. Kein Cloudflare-Access, keine öffentliche Subdomain, kein DNS-Eintrag.
- **Repo-Pfad auf VPS:** `C:\newNFL`. Backend-Port: `8001` (capsule belegt 8000).
- **Scheduled-Task-Präfix:** `NewNFL-*` (klare Trennung von `Capsule-*`).
- **Backup-Ablage:** lokal auf VPS unter `C:\newNFL-Backups\`. Offsite-Sync über Tailnet auf DEV-LAPTOP als Folgearbeit, nicht T3.1-Blocker.
- **`cloudflared`-Service bleibt unangetastet** — wir fassen die bestehende capsule-Infrastruktur nicht an.

DEV-LAPTOP bleibt Entwicklungs-Umgebung. Scheduler-Automation auf DEV-LAPTOP entfällt ersatzlos.

## Alternativen

### A. T3.0 auf DEV-LAPTOP wie ursprünglich geplant, Laptop als Dauerläufer konfigurieren
**Verworfen.** Windows-Power-/Sleep-Einstellungen, Batterie-Zyklen und ungeplante Reboots (Updates, BSOD) sind auf einem privaten Laptop nicht unter Kontrolle zu bringen. Selbst mit maximaler Disziplin bleibt das Setup unzuverlässig — und Unzuverlässigkeit in der Test-Umgebung verunmöglicht die Testaussage.

### B. Zweites Always-on-Gerät dedicated für T3.0
**Verworfen.** Investition in Hardware nur für 4 Wochen Testphase ist unverhältnismäßig, wenn der Produktiv-VPS ohnehin bereitsteht.

### C. T3.0 auf VPS, aber als separate Pipeline parallel zu DEV-LAPTOP
**Verworfen.** Würde bedeuten, dass DEV-LAPTOP weiter als „Source of Truth" läuft und der VPS nur als Test-Spiegel dient. Das verdoppelt den Wartungsaufwand und schiebt die eigentliche Migration nur auf. Besser: VPS wird direkt Ziel-Umgebung, Laptop wird Dev-only.

### D. T3.0-DoDs abschwächen (z. B. „3 Tage mit Lücken akzeptiert")
**Verworfen.** Der DoD beweist operative Stabilität — Abschwächung entwertet den Test. Der Zweck von T3.0 ist gerade, die ungeplanten Fehler-Modi zu finden, die in der Entwicklung nicht auftreten.

### E. T3.0 ganz weglassen, direkt auf Produktiv
**Verworfen.** Backup/Restore-Drill und Designed-Degradation-Validation sind fachlich nötig bevor die echte NFL-Saison gestartet wird — das ist explizit im [v1.0-Release-Evidence-Dokument](../_ops/releases/v1.0.0-laptop.md) als offener Punkt festgehalten (5. Definition-Kriterium auf ⚠️).

## Konsequenzen

**Positive:**
- **Testumgebung = Produktionsumgebung.** Keine Drift zwischen Test-Hardware und Ziel-Hardware mehr. Was in T3.0 läuft, läuft in T3.1-Produktiv.
- **Always-on möglich.** VPS läuft 24/7, Scheduler-DoDs sind sauber messbar.
- **Backup/Restore-Drill (T3.0F) validiert auf echter Produktions-Hardware** — nicht mehr auf einem Laptop, der später eh nicht der Ziel-Ort ist.
- **Cloudflare-Access-Aufwand entfällt.** Tailscale-only ist für Single-Operator-Use-Case die einfachere und sicherere Lösung. Spart in T3.1 erheblichen Konfigurationsaufwand.
- **VPS-Bootstrap wird sofort produktionsrelevant** statt „später mal". Fehler im Deployment-Pfad werden jetzt gefunden, nicht erst kurz vor Preseason.

**Negative:**
- **Infrastruktur und Pipeline gleichzeitig debuggen.** Wenn im 4-Wochen-Test etwas schiefgeht, ist nicht sofort klar, ob Task-Scheduler, nflverse-Endpoint, Tailscale-Network, DuckDB oder Pipeline schuld ist. **Gegenmittel:** T3.1-DoD verlangt sauberen Smoke-Lauf vor T3.0-Start (siehe [T2_3_PLAN.md §10](../T2_3_PLAN.md)).
- **Backup-Strategie muss ernster genommen werden.** Auf dem VPS liegt die einzige produktive DB. Contabo-Provider-Snapshots + lokaler Backup-Job ab T3.1-DoD Pflicht, nicht optional.
- **VPS-Migration ist selbst eine vielschichtige Arbeit** (Tailscale, Python-Venv, DuckDB-Migration, Scheduled Tasks). Entsprechend sorgfältig in [T2_3_PLAN.md §10](../T2_3_PLAN.md) zu planen.

## Umsetzung

1. **Dieser ADR** dokumentiert die Entscheidung.
2. **`docs/T2_3_PLAN.md` §1, §9, §10** werden im Zuge dieses Commits aktualisiert: Kalenderfenster-Tabelle tauscht T3.0 und T3.1, T3.0A wird auf „Scheduler-Automation auf VPS" umformuliert, T3.1-DoD streicht den 7-Tage-Parallel-Lauf und ergänzt Tailscale-only-Präzisierung.
3. **`docs/PROJECT_STATE.md`** — Current cycle und Preferred next bolt geflippt auf T3.1.
4. **Folge-Dokumente (Phase 2 der Session):**
   - `docs/_ops/vps/VPS_DOSSIER.md` — NEW-NFL-spezifische VPS-Konventionen (Pfad, Port, Task-Präfix, Backup-Ablage, Tailscale-Erreichbarkeit).
   - `docs/_ops/vps/VPS_DEPLOYMENT_RUNBOOK.md` — Schritt-für-Schritt-Anweisungen für den Operator mit Gerät-/User-/Shell-Prefix.
5. **Folge-Artefakte (Phase 4 der Session):**
   - `deploy/windows-vps/vps_bootstrap.ps1` analog zum capsule-Muster.
   - `deploy/windows-vps/vps_install_tasks.ps1` für `NewNFL-*`-Scheduled-Tasks.
   - `deploy/windows-vps/vps_smoke_test.ps1` für T3.1-DoD.

## DoD

- [x] Reihenfolge-Entscheidung dokumentiert und begründet
- [x] Alternativen benannt und verworfen mit Grund
- [x] Konsequenzen positiv/negativ benannt, Gegenmittel für negative Punkte genannt
- [x] T2_3_PLAN.md und PROJECT_STATE.md Updates im gleichen Commit wie dieser ADR
- [x] Status `Accepted` — Entscheidung ist im Operator-Abstimmungs-Moment getroffen, nicht hypothetisch

## Referenzen

- [docs/_ops/releases/v1.0.0-laptop.md](../_ops/releases/v1.0.0-laptop.md) — v1.0-Cut-Evidence, §5 Restrisiken (#6 Backup als Runner-Job fehlt, #7 Event-File-Rotation — beide werden in T3.0 auf VPS relevant)
- [docs/T2_3_PLAN.md](../T2_3_PLAN.md) §9 (T3.0-Scope) und §10 (T3.1-Scope) — die konkreten Sub-Bolt-Definitionen
- [docs/PROJECT_STATE.md](../PROJECT_STATE.md) — Current cycle / Preferred next bolt
- [capsule-Deployment-Runbook](https://github.com/andreaskeis77/capsule/blob/main/docs/VPS_DEPLOYMENT_RUNBOOK.md) — VPS-Grundausbau (Tailscale, `cloudflared`-Service, Windows-Hardening), den NEW NFL wiederverwendet statt zu duplizieren
- [capsule-RUNBOOK_VPS_ACCESS_AND_CLOUDFLARE](https://github.com/andreaskeis77/capsule/blob/main/docs/RUNBOOK_VPS_ACCESS_AND_CLOUDFLARE.md) — Cloudflare-Tunnel-Setup (für NEW NFL *nicht* nachgebaut; explizite Entscheidung oben)
- ADR-0005 (Scheduler and VPS runtime model frame) — Basis-Frame für VPS-Betrieb
