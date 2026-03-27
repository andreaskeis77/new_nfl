# NEW NFL – Observability v0.1

## 1. Zweck

Dieses Dokument beschreibt das Zielbild für Logs, Health-Checks, Run-Evidence,
Freshness und Diagnosefähigkeit.

## 2. Aktueller Stand

Noch keine Runtime. Noch keine Jobs. Noch keine produktionsnahen Health-Checks.

## 3. Zielbild

NEW NFL soll später mindestens beobachtbar machen:

- erfolgreiche und fehlgeschlagene Ingestion-Runs
- Quelle, Zeitpunkt und Umfang wichtiger Datenimporte
- Health-Status zentraler Komponenten
- Freshness der wichtigsten Datenbereiche
- UI- und API-Basisverfügbarkeit
- Scheduler-/Dienstestatus auf dem VPS
- DQ- oder Konsolidierungsprobleme

## 4. Geplante Artefakt-Orte

- `docs/_ops/quality_gates/`
- `docs/_ops/releases/`
- spätere Laufzeit-Logs außerhalb des Repos
- spätere Reports / Exporte nach definierter Struktur

## 5. Regel

Ohne verwertbare Laufzeitbeobachtung gilt ein produktionsnaher Stand nicht als belastbar.
