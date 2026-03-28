# HANDOFF T1.4D remote fetch descriptor compatibility fix

Status: proposed fix

Scope:
- repair remote fetch execute path to use the adapter plan for stage dataset access
- preserve descriptor metadata in the request manifest through descriptor.as_dict()
- avoid further API drift in the execute path

Validated target state:
- fetch-remote --execute no longer accesses descriptor.stage_dataset
- tests test_cli_remote_fetch and test_remote_fetch pass
- no behavior change for dry-run mode

Next step:
- rerun import, bootstrap, seed, run-adapter, fetch-remote, ingest-run listing, and quality gates
