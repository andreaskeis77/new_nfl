# HANDOFF T1.4A Compatibility and Validation Fix

Status: proposed

Scope:
- restore metadata compatibility against existing local database evolution
- preserve previously exposed metadata APIs used by earlier tests
- restore adapter exports expected by earlier tranches
- document stronger internal validation expectations for future deliveries

Validated target:
- T1.4 should run against an upgraded local database, not only against a fresh one
- quality gates should stay green after remote-fetch integration
- prior tranche tests should remain compatible

Next step:
- rerun T1.4 validation and only commit if all gates are green
