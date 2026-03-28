# HANDOFF T1.4E Target Schema Fix

Status: prepared

Scope:
- repair the remaining T1.4 execute-path failure in remote fetch
- bind remote raw landing load-events to an explicit target schema/object

Problem observed:
- `fetch-remote --execute` still failed against evolved local metadata with
  `NOT NULL constraint failed: load_events.target_schema`

Repair:
- remote fetch now records load-events with:
  - `target_schema = "raw"`
  - `target_object = "<adapter_id>_remote_fetch_receipt"`
  - `event_kind = "remote_raw_landing"`
  - `event_status = "remote_fetched"`
  - `pipeline_name = adapter.<adapter_id>.remote_fetch`

Expected next state:
- T1.4 execute path should be green for both fetch contract and remote fetch
- after green validation, T1.4 can be closed and T1.5 can begin
