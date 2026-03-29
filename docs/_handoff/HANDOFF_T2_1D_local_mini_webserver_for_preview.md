# HANDOFF T2.1D Local Mini Webserver For Preview

Status: ready for local validation

Scope:
- add a small local HTTP server for the existing core dictionary preview
- keep the bolt read-only against the existing core dictionary slice
- avoid VPS/deploy concerns in this tranche

What changed:
- added `src/new_nfl/web_server.py`
- added CLI command `serve-web-preview`
- added focused tests for preview HTML generation and CLI parsing

What this bolt does not do:
- no new ingest path
- no schema change
- no VPS deployment
- no authentication or multi-user serving

Preferred next step after green:
- T2.1E: package the local preview/server path into a first explicit VPS deployment runbook
