
# HANDOFF T2.0G Core Dictionary Summary by Data Type

Status: delivered and ready for local validation

Scope:
- add a small aggregate summary path on top of the existing browseable core dictionary slice
- group the current core dictionary by `data_type`
- keep the bolt read-only and narrow

Why this bolt exists:
- after exact lookup and filtered browse, the next useful read path is a compact aggregate view
- this creates a simple operator summary without introducing a broader reporting surface
- it remains on the same canonical core object

What changes:
- add `src/new_nfl/core_summary.py`
- add CLI command `summarize-core --adapter-id nflverse_bulk`
- add focused tests for grouped data-type counts and parser support

Preferred next step after local validation:
- either commit this summary slice or pivot to the first non-dictionary asset bolt
