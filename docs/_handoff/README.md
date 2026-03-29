# Handoffs

Dieses Verzeichnis enthält strukturierte Handoffs für wiederaufnahmebedürftige
Zwischenstände, abgeschlossene Tranches, RCs und relevante Debugging-Situationen.

## Regeln

- Ablage nach dem Schema `HANDOFF_<cycle>_<bolt>_<short_title>.md`
- kein Wunschdenken, nur validierter Stand
- genau ein bevorzugter nächster Schritt
- Referenz auf relevante Gates, Doku und ggf. Ops-Artefakte
- bei Delivery-/Apply-Problemen muss der operative Fehler ebenfalls dokumentiert
  werden, nicht nur der fachliche Fix

## Delivery-/Apply-Konvention

Für NEW NFL gilt bei ZIP-Artefakten standardmäßig:
- flat-root ZIP
- lokale Ablage im Windows-Downloads-Ordner des Users
- expliziter DEV-LAPTOP-Apply-Block im Deliverable
- temporäre `_apply/`-Ordner nach erfolgreicher Validierung wieder entfernen

Wenn diese Konvention verletzt wurde, gehört das in den Handoff.

## Aktueller Stand

Operative Handoffs sind vorhanden. Der README-Stand muss mit dem tatsächlichen
Verzeichnisinhalt synchron bleiben.
