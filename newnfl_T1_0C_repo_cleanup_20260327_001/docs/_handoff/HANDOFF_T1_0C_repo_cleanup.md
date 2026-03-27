# HANDOFF T1.0C — Repo Cleanup After Technical Bootstrap

## Goal
Remove generated local DuckDB state from Git tracking and harden ignore rules so that local runtime data stays outside version control.

## Why this exists
T1.0 produced a correct local bootstrap, but `data/db/new_nfl.duckdb` was committed into the repository. That conflicts with the NEW NFL repo hygiene model: generated local runtime state belongs on disk, not in Git.

## Scope
- tighten `.gitignore` for local database state
- keep `data/db/` present in the working tree via `.gitkeep`
- remove the tracked DuckDB file from the Git index while preserving the local file on disk

## Expected operator action
On the DEV-LAPTOP:
1. unpack this patch into the repo root
2. run `git rm --cached data/db/new_nfl.duckdb`
3. stage the patch files
4. commit and push

## Acceptance criteria
- `data/db/new_nfl.duckdb` is no longer tracked by Git
- `data/db/.gitkeep` is tracked
- `.gitignore` protects local database state from being recommitted
- local runtime remains functional after cleanup

## Next step after cleanup
Proceed to T1.1 metadata and registry implementation.
