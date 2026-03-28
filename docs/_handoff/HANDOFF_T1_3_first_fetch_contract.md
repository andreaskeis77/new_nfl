# HANDOFF T1.3 First Fetch Contract

Status: ready for local import and validation

Scope:
- introduce the first real adapter execution contract
- keep remote fetching out of scope
- bind execute-mode runs to landed raw artifacts and metadata records
- keep dry-run side-effect free

Files in scope:
- src/new_nfl/adapters/fetch_contract.py
- src/new_nfl/adapters/__init__.py
- src/new_nfl/bootstrap.py
- src/new_nfl/cli.py
- src/new_nfl/metadata.py
- tests/test_adapter_fetch_contract.py
- tests/test_cli_fetch_contract.py
- docs/concepts/NEW_NFL_FIRST_FETCH_CONTRACT_v0_1.md
- docs/adr/ADR-0019-first-fetch-contract-and-raw-landing-receipt.md
- docs/adr/ADR-0020-dry-run-vs-execute-adapter-contract.md

Expected validation:
- bootstrap green
- seed-sources green
- dry-run adapter command green
- execute adapter command green
- ingest-run listing green
- quality gates green

Next intended step after green:
- T1.4 first true remote fetch implementation for one adapter
