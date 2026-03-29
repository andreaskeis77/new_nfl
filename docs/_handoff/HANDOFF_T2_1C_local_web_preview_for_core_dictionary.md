# HANDOFF T2.1C Local Web Preview for Core Dictionary

Status: ready for local validation

Scope:
- add a first local HTML preview for the existing core dictionary slice
- keep the bolt read-only with respect to staged and core data
- avoid introducing a broader web framework before a minimal visible preview exists

What this bolt adds:
- `src/new_nfl/web_preview.py` to render a static HTML preview file
- `render-web-preview` CLI command
- tests for preview rendering and parser coverage

What this bolt does not do:
- no new ingest path
- no VPS deployment yet
- no live web server yet
- no new source asset

Preferred next step after local validation:
- either a small VPS runbook/deploy bolt for the local preview flow
- or a new ingest bolt for a first non-dictionary facts asset
