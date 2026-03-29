# HANDOFF T2.1A Stage Load Source File Pinning

Status: ready for local validation

Scope:
- harden `stage-load` so it can target an explicit registered source file
- keep the existing default behavior of using the latest source file when no pin is supplied
- expose the new source-file pinning path through the CLI
- add a narrow replay-focused test

Why this bolt exists:
- the current `stage-load` contract resolves the latest registered source file for an adapter
- that is sufficient for a first narrow slice, but it is a replay weakness once multiple landed files exist for the same adapter
- the next small hardening step is to make the source-file selection explicit when the operator wants deterministic replay

What changes:
- `execute_stage_load()` accepts an optional `source_file_id`
- `stage-load` CLI accepts `--source-file-id`
- a targeted test proves that an older registered source file can still be selected explicitly

Preferred next step after local validation:
- use the new source-file pinning path as the basis for future asset-explicit staging and canonical-load work
