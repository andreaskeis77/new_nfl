# HANDOFF T1.4C API Compatibility Fix

Status: prepared

Scope:
- restore adapter catalog compatibility with the T1.2/T1.3 public adapter surface
- ensure `AdapterDescriptor` again exposes `dry_run_supported`
- ensure `AdapterPlan` again exposes `as_dict()` through the shared base model
- pass `source_id` into remote fetch load-event recording for legacy-compatible load event inserts
- keep T1.4 remote fetch behavior otherwise unchanged

Expected validation focus:
- import and collection must succeed
- adapter tests must pass again
- `run-adapter --execute` must no longer fail on `plan.as_dict()`
- `fetch-remote --execute` must no longer fail on `load_events.source_key`

Next step:
- rerun the T1.4 validation chain and only commit if all gates are green
