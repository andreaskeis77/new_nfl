# NEW NFL Metadata Model v0.1

Status: Draft for architecture tranche A0.3  
Owner: Andreas + ChatGPT  
Scope: Runtime metadata, provenance, run tracking, identity, DQ events, and internal registries

## 1. Purpose

NEW NFL must treat metadata as first-class system data. This document defines the conceptual metadata model required to operate a resilient, auditable, multi-source NFL platform.

The metadata layer is not just technical bookkeeping. It is the control plane for:

- source governance
- ingest run history
- provenance
- data quality
- freshness
- consolidation
- later model/simulation evaluation

## 2. Metadata Domains

The metadata model is split into six domains:

1. **Source Registry**
2. **Run Registry**
3. **Load Events**
4. **Data Quality Events**
5. **Canonical Identity and Mappings**
6. **Prediction / Simulation Registry** (reserved for later phases)

## 3. Source Registry Domain

Purpose:
- persistent catalog of approved sources and their operational role

Core conceptual fields:
- `source_id`
- `source_name`
- `source_role`
- `source_tier`
- `priority_rank`
- `access_mode`
- `dataset_class`
- `enabled_flag`
- `stability_note`
- `fallback_policy`
- `terms_or_risk_note`
- `introduced_in_phase`
- `last_reviewed_at`

## 4. Run Registry Domain

Purpose:
- represent every acquisition or processing run as a traceable unit

Core conceptual fields:
- `run_id`
- `run_type`
- `run_scope`
- `trigger_mode`
- `started_at`
- `ended_at`
- `run_status`
- `executor_context`
- `code_version`
- `config_fingerprint`
- `notes`

Run statuses:
- `started`
- `succeeded`
- `partial`
- `failed`
- `quarantined`
- `cancelled`

## 5. Load Events Domain

Purpose:
- trace what each run attempted and what it produced per source/dataset/layer

Core conceptual fields:
- `load_event_id`
- `run_id`
- `source_id`
- `dataset_class`
- `target_layer`
- `retrieved_at`
- `source_locator`
- `artifact_fingerprint`
- `record_count_raw`
- `record_count_accepted`
- `record_count_rejected`
- `bytes_in`
- `parser_version`
- `normalization_version`
- `load_status`

Target layers:
- `raw`
- `staging`
- `canonical`
- `read_model`
- `analytics`

## 6. Data Quality Events Domain

Purpose:
- durable record of quality problems, warnings, conflicts, and gating outcomes

Core conceptual fields:
- `dq_event_id`
- `run_id`
- `source_id`
- `dataset_class`
- `entity_type`
- `entity_key`
- `severity`
- `dq_rule_id`
- `dq_rule_class`
- `event_status`
- `detected_at`
- `details_json`
- `resolution_note`

Suggested severities:
- `info`
- `warning`
- `error`
- `critical`

Suggested rule classes:
- schema
- completeness
- freshness
- referential
- duplication
- conflict
- plausibility
- drift

## 7. Canonical Identity and Mapping Domain

Purpose:
- keep stable internal identifiers independent from any one source

Core conceptual entities:
- team
- player
- game
- season
- week
- venue
- simulation_run
- scenario

Core mapping concepts:
- internal canonical id
- source-specific external id
- mapping confidence
- mapping validity period
- alias history

This domain is central for multi-source consolidation.

## 8. Provenance Grain

Provenance must be preserved at appropriate grain. The design intent is:

- **run-level provenance**  
  What happened in a processing run?

- **artifact-level provenance**  
  Which source artifact or payload was retrieved?

- **record/batch-level provenance**  
  Which source data contributed to this normalized or canonical result?

Not every layer needs the same detail exposed for UI purposes, but the architecture should preserve enough traceability to reconstruct origin when needed.

## 9. Core Provenance Fields

Any normalized or canonical record should be able to retain or reference at least:

- `source_id`
- `run_id`
- `retrieved_at`
- `source_record_id` if available
- `source_record_hash` or batch fingerprint
- `parser_version`
- `normalization_version`
- `confidence_status`

## 10. Freshness Metadata

Freshness is not a general feeling. It is measured.

Conceptual freshness fields:
- `expected_refresh_frequency`
- `last_successful_retrieval_at`
- `fresh_until`
- `freshness_status`
- `source_lag_seconds_or_hours`

Freshness statuses may include:
- `fresh`
- `aging`
- `stale`
- `unknown`

## 11. Quarantine Concept

Certain records or batches must be isolatable without destroying evidence. The metadata model therefore supports conceptual quarantine states for:
- runs
- load events
- DQ events
- normalized batches
- mapping candidates

Quarantine is not deletion. It is a controlled holding state pending review or later repair.

## 12. Simulation Registry Reserve

Although Phase 1 does not implement simulation workflows, the architecture should reserve metadata concepts for future traceability.

Reserved conceptual fields:
- `simulation_run_id`
- `scenario_id`
- `input_snapshot_id`
- `feature_set_version`
- `model_version`
- `prediction_target`
- `evaluation_window`
- `actual_outcome_link`
- `scoring_metric_set`
- `evaluation_status`

This prevents later simulation work from becoming detached from historical inputs.

## 13. Phase 1 Minimal Required Metadata

Phase 1 should minimally support:
- source registry
- run registry
- load events
- DQ events
- canonical id mappings for core entities
- freshness status for major dataset classes

## 14. Non-Goals for A0.3

This document does not yet:
- define physical database tables
- define final column names for all runtime objects
- define every DQ rule
- define every simulation metadata structure
- define UI rendering of metadata

## 15. Decision Impact

A strong metadata model is what makes NEW NFL diagnosable, governable, and extensible. Without it, the project would devolve into a collection of fetched files and unverifiable merges.
