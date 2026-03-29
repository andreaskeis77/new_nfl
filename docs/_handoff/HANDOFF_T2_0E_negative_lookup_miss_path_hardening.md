# HANDOFF T2.0E Negative Lookup Miss Path Hardening

Status: delivered and ready for local validation

Scope:
- harden the negative path of `describe-core-field`
- keep exact-hit behavior unchanged
- return deterministic miss metadata and operator-visible suggestions
- keep the bolt narrow and query-surface-only

What changed:
- `src/new_nfl/core_lookup.py` now returns `miss_reason` and `suggestions` on misses
- exact misses now probe a small deterministic suggestion set from `core.schedule_field_dictionary`
- `src/new_nfl/cli.py` now prints `MISS_REASON`, `SUGGESTION_COUNT`, and `SUGGESTION=` lines before exiting with code `1`
- tests now cover both exact hits and miss-path suggestions

Expected local green signals:
- imports remain green
- lookup and browse tests remain green
- `describe-core-field --field game_id` still returns a hit
- `describe-core-field --field game` now returns a miss with suggestion lines and exit code `1`

Preferred next step after local validation:
- continue with the next small query-surface bolt or move to the next real non-dictionary asset
