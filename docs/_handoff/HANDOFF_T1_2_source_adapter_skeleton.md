# HANDOFF T1.2 Source Adapter Skeleton

Status: prepared for local import, execution, and validation

Scope:
- add source adapter abstraction layer
- add adapter catalog aligned to seeded source registry ids
- add CLI commands to list and describe adapter skeletons
- add adapter tests
- update concept and ADR coverage for adapter posture

Delivered files:
- src/new_nfl/adapters/__init__.py
- src/new_nfl/adapters/base.py
- src/new_nfl/adapters/catalog.py
- src/new_nfl/bootstrap.py
- src/new_nfl/cli.py
- tests/test_adapters.py
- tests/test_cli_adapter.py
- docs/concepts/NEW_NFL_SOURCE_ADAPTER_SKELETON_v0_1.md
- docs/adr/ADR-0017-source-adapter-abstraction.md
- docs/adr/ADR-0018-adapter-registry-binding-and-dry-run-contract.md

Validation target:
- bootstrap remains green
- seeded registry still shows four source records
- adapter list shows four adapter skeletons
- adapter description resolves a dry-run plan for at least one adapter
- ruff and pytest are green

Next step after green:
- T1.3 first real adapter fetch contract and raw landing artifact capture
