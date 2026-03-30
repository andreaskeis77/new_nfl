# HANDOFF T2.2A VPS Deploy Runbook for Preview Release

Status: delivered and ready for local validation

Scope:
- define the first VPS preview-release runbook
- keep the bolt docs-only
- prepare the project for the first controlled VPS replay of the local preview path

Why this bolt exists:
- the project already has a local preview-release candidate
- a VPS release should not start as improvised shell work
- the next step should be an explicit replayable runbook, not a hidden sequence of ad-hoc commands

What this bolt does:
- updates `docs/PROJECT_STATE.md` to reflect the current release posture
- adds `docs/RUNBOOK_VPS_PREVIEW_RELEASE.md`
- defines the first narrow VPS preview procedure

What this bolt does not do:
- no new code path
- no systemd setup
- no reverse proxy
- no public internet exposure
- no new data asset

Preferred next step after local validation:
- T2.2B — VPS preview release execution and smoke test
