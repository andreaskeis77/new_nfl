# NEW NFL Metadata Schema Outline v0.1

Status: Draft for A0.4 architectural convergence  
Phase: A0.4  
Scope: Initial metadata schema families before DDL implementation

## 1. Purpose

This document defines the required **metadata schema outline** for NEW NFL before the first implementation tranche. It is not yet executable DDL. It is the structural contract that later table definitions must follow.

The metadata layer exists to make ingestion, consolidation, validation, and later simulation evaluation observable and governable.

## 2. Principles

1. Metadata is part of the product, not an implementation detail.
2. Every ingest activity must be attributable to a run.
3. Every transformed artifact must be traceable to its upstream source.
4. DQ events must be queryable.
5. Registry tables must be stable, compact, and human-inspectable.
6. Simulation outputs must be traceable to their input state and evaluation results.

## 3. Recommended metadata schema families

### 3.1 `meta`
System registries, operational events, DQ events, lineage references, configuration snapshots, and runtime evidence pointers.

### 3.2 `sim`
Simulation registry, run configuration fingerprints, outcomes, and evaluation records.

Note: most global operational metadata should still live in `meta`. The `sim` schema exists because simulation activity becomes a major first-class domain later.

## 4. Mandatory metadata tables (phase-1 baseline)

## 4.1 `meta.source_registry`

Purpose:
- catalog all configured or known data sources

Suggested columns:
- `source_id`
- `source_name`
- `source_tier`
- `source_priority`
- `source_type`
- `access_method`
- `base_reference`
- `expected_frequency`
- `is_active`
- `owner_note`
- `created_at`
- `updated_at`

Key rules:
- one row per logical source, not per request
- source status changes must not destroy history silently

## 4.2 `meta.source_endpoint_registry`

Purpose:
- represent concrete endpoints, feeds, pages, or extract definitions tied to a source

Suggested columns:
- `endpoint_id`
- `source_id`
- `endpoint_name`
- `endpoint_kind`
- `endpoint_reference`
- `entity_scope`
- `rate_limit_note`
- `auth_requirement`
- `is_active`
- `created_at`
- `updated_at`

## 4.3 `meta.ingest_run`

Purpose:
- represent each top-level ingestion or refresh run

Suggested columns:
- `ingest_run_id`
- `run_type`
- `trigger_mode`
- `started_at`
- `finished_at`
- `status`
- `initiated_by`
- `code_version`
- `config_fingerprint`
- `environment_name`
- `summary_json`

## 4.4 `meta.load_event`

Purpose:
- track table- or entity-level load/write activity inside a run

Suggested columns:
- `load_event_id`
- `ingest_run_id`
- `source_id`
- `endpoint_id`
- `target_layer`
- `target_schema`
- `target_object`
- `operation_type`
- `row_count`
- `byte_count`
- `status`
- `warning_count`
- `error_count`
- `started_at`
- `finished_at`
- `details_json`

## 4.5 `meta.raw_artifact_registry`

Purpose:
- register durable raw payload artifacts written to disk

Suggested columns:
- `raw_artifact_id`
- `ingest_run_id`
- `source_id`
- `endpoint_id`
- `artifact_path`
- `artifact_format`
- `content_hash`
- `byte_count`
- `retrieved_at`
- `retention_class`
- `parse_status`

## 4.6 `meta.dq_event`

Purpose:
- record data-quality exceptions, warnings, or informational anomalies

Suggested columns:
- `dq_event_id`
- `ingest_run_id`
- `severity`
- `rule_class`
- `rule_name`
- `entity_type`
- `entity_key`
- `target_schema`
- `target_object`
- `event_status`
- `detected_at`
- `details_json`

## 4.7 `meta.conflict_event`

Purpose:
- record canonicalization conflicts across sources

Suggested columns:
- `conflict_event_id`
- `ingest_run_id`
- `entity_type`
- `entity_key`
- `attribute_name`
- `preferred_source_id`
- `discarded_source_id`
- `resolution_mode`
- `resolution_status`
- `details_json`
- `detected_at`

## 4.8 `meta.table_freshness`

Purpose:
- report latest successful refresh posture for major logical outputs

Suggested columns:
- `freshness_id`
- `logical_object_name`
- `layer_name`
- `last_successful_run_id`
- `last_successful_at`
- `expected_refresh_class`
- `freshness_status`
- `lag_seconds`
- `details_json`

## 4.9 `meta.config_snapshot`

Purpose:
- record compact snapshots or fingerprints of relevant runtime configuration

Suggested columns:
- `config_snapshot_id`
- `ingest_run_id`
- `snapshot_type`
- `config_fingerprint`
- `snapshot_ref`
- `created_at`

## 4.10 `meta.entity_key_registry`

Purpose:
- map canonical identifiers and major external identifiers

Suggested columns:
- `entity_key_registry_id`
- `entity_type`
- `canonical_id`
- `source_id`
- `external_id`
- `external_id_type`
- `valid_from`
- `valid_to`
- `is_current`
- `created_at`

## 4.11 `meta.quarantine_registry`

Purpose:
- track quarantined rows, files, or entity slices awaiting review or rule update

Suggested columns:
- `quarantine_id`
- `ingest_run_id`
- `quarantine_scope`
- `entity_type`
- `entity_key`
- `artifact_ref`
- `reason_class`
- `reason_detail`
- `status`
- `created_at`
- `resolved_at`

## 4.12 `meta.release_evidence`

Purpose:
- tie operational or schema milestones to release history

Suggested columns:
- `release_evidence_id`
- `release_tag_or_ref`
- `evidence_type`
- `artifact_ref`
- `created_at`
- `note`

## 5. Simulation metadata tables (future-facing baseline)

## 5.1 `sim.simulation_run`

Purpose:
- record each simulation or model execution

Suggested columns:
- `simulation_run_id`
- `simulation_type`
- `started_at`
- `finished_at`
- `status`
- `code_version`
- `input_dataset_fingerprint`
- `parameter_fingerprint`
- `summary_json`

## 5.2 `sim.simulation_output_registry`

Purpose:
- register stored outputs from simulations

Suggested columns:
- `simulation_output_id`
- `simulation_run_id`
- `output_type`
- `storage_ref`
- `row_count`
- `created_at`

## 5.3 `sim.simulation_evaluation`

Purpose:
- evaluate later how well a simulation or model performed

Suggested columns:
- `simulation_evaluation_id`
- `simulation_run_id`
- `evaluation_date`
- `evaluation_scope`
- `metric_name`
- `metric_value`
- `comparison_ref`
- `details_json`

## 6. Naming rules

- singular or plural naming must be consistent once chosen; recommended convention is singular for event-like tables and plural only when strongly justified
- primary key names should be explicit, not generic `id` where ambiguity exists
- timestamps use `_at`
- booleans use `is_` or `has_`
- JSON payload columns use `_json`
- canonical identifiers use `canonical_id` or domain-specific explicit identifiers

## 7. Relationship rules

Minimum relationship chain:

- `source_registry` → `source_endpoint_registry`
- `ingest_run` → `load_event`
- `ingest_run` → `raw_artifact_registry`
- `ingest_run` → `dq_event`
- `ingest_run` → `conflict_event`
- `ingest_run` → `config_snapshot`

Later technical DDL may choose physical foreign keys selectively, but the logical referential model is mandatory even when hard constraints are deferred for performance or ingestion practicality.

## 8. Query expectations

The metadata model must make these questions easy to answer:

- Which sources are active?
- Which endpoints failed today?
- Which runs wrote to `core`?
- Which objects are stale?
- Which records were quarantined and why?
- Which simulation runs used which input state?
- What changed between two release baselines?

## 9. Exit criteria for implementation readiness

This outline is ready to become executable schema work when:

- table list is accepted
- critical columns are accepted
- logical relationships are accepted
- naming rules are accepted
- open questions are reduced to DDL specifics, not structural ambiguity
