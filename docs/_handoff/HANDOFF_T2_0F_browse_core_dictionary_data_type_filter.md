# HANDOFF T2.0F Browse Core Dictionary Data Type Filter

Status: ready for local validation

Scope:
- extend `browse-core` with an exact `data_type` filter
- keep the bolt on the existing canonical dictionary object
- keep the change read-only and CLI-focused

What changes:
- `src/new_nfl/core_browse.py` now accepts a normalized `data_type_filter`
- `browse-core` can combine `--field-prefix` and `--data-type`
- CLI output now prints `DATA_TYPE_FILTER=` for deterministic operator feedback
- tests cover parser behavior and combined browse filtering

What this bolt does not do:
- no new ingest path
- no new core object
- no fuzzy matching beyond the existing prefix browse path

Preferred next step after local validation:
- either commit this browse hardening bolt, or move to the next asset only after the current dictionary surface is considered sufficient
