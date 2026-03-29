# HANDOFF T2.1B Source File Discovery

Status: ready for local validation

Scope:
- add a small read-only operator path to discover registered source files
- support practical use of `stage-load --source-file-id ...`
- keep the bolt narrow and metadata-surface only

What changes:
- add `src/new_nfl/source_files.py`
- add `list-source-files` command to the CLI
- print registered `source_file_id` rows newest first with a small limit

Why this bolt exists:
- T2.1A introduced explicit source-file pinning for stage load
- the operator should be able to discover valid `source_file_id` values without
  direct manual database inspection

Preferred next step after local validation:
- continue with the next small operator-facing metadata or replay-hardening bolt
