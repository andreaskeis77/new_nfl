# VALIDATION_PROTOCOL

## Purpose

This document defines the required validation order for NEW NFL tranches. The
goal is not only to detect defects, but to detect the **right class of defects
early**: import/collection failures, API contract drift, upgrade-state breakage,
and operational path regressions.

## Core rule

Validation is not a bag of checks. It is an ordered ladder. Do not jump
directly to `pytest` or `ruff` and assume the tranche is green.

## Validation ladder

For implementation and fix tranches, the preferred order is:

1. **Extraction/path validation**
   - ZIP landed flat-root
   - ZIP was resolved from the expected source location
   - for DEV-LAPTOP this is the Windows user's Downloads folder unless
     explicitly stated otherwise
   - `git status --short` shows expected paths only

2. **Post-apply sanity check**
   - confirm the intended files actually changed
   - verify the first lines or a minimal structural check of the replaced files
   - confirm no shell commands or apply prose were accidentally written into
     Python or Markdown source files

3. **Import/collection gate**
   - direct import of the relevant package entrypoint
   - no module collection errors
   - no broken public exports

4. **Last green path replay**
   - replay the most relevant previously green CLI/runtime path
   - ensure the new tranche did not silently break older behavior

5. **New path validation**
   - execute the new CLI/runtime path introduced by the tranche
   - verify both dry-run and execute variants where applicable

6. **State coverage**
   - fresh state validation
   - upgrade/evolved state validation against an existing local DB if relevant

7. **Quality gates**
   - `ruff`
   - `pytest`
   - project quality-gate wrapper if present

Only after this ladder is green may the tranche be considered green.

## Mandatory replay classes

The following replay classes matter especially for NEW NFL:
- package import / CLI import
- source registry seed
- adapter discovery and description
- existing execute paths after new adapter/fetch changes
- metadata tables under both fresh and evolved local DB states

## Contract surfaces that require replay

Replay is mandatory when a tranche touches any of these:
- `src/new_nfl/cli.py`
- package `__init__` exports
- adapter descriptors or plans
- `meta.*` table schemas or inserts
- metadata helper functions used by multiple CLI paths
- delivery/apply instructions when the tranche is ZIP-based and operator-applied

## Fresh vs evolved state

Two states must be thought about separately:

### Fresh state

A newly bootstrapped local repo state with a fresh local DuckDB file.

### Evolved state

A realistic local working state that already contains:
- prior metadata tables
- prior ingest runs
- prior load events
- prior local raw landing directories

A tranche is not sufficiently validated if it only works on fresh state while
failing on evolved state.

## Green definition

A tranche is green only if:
- required extraction/path validation passes
- required post-apply sanity check passes
- required import/collection passes
- required replay of last green path passes
- new path passes
- required state coverage passes
- `ruff` passes
- `pytest` passes

## Red classification examples

A tranche stays red if any of the following is true:
- import error during CLI startup
- tests pass but required CLI execute path fails
- new path works only on fresh state but not on evolved state
- one module expects a public field or export that another no longer provides
- DB insert/update fails because compatibility columns were not considered
- a ZIP was applied from the wrong landing folder
- apply instructions caused shell text to be written into source files

## Assistant preflight expectation

Before delivering a tranche, ChatGPT should explicitly think through:
- which path was last green
- which public contract might be broken
- which upgraded local state might be affected
- whether the new path introduces new required columns or metadata fields
- whether the apply instructions match the repo's expected operator workflow

If this could not be checked with confidence, that uncertainty must be stated as
delivery risk.

## Practical T1.x lessons

The T1.x cycle revealed recurring failure modes:
- compatibility drift against existing local metadata surfaces
- broken public exports between modules
- descriptor/plan API drift
- tests green while required CLI execute path remained red
- late discovery of import/collection errors
- delivery/apply drift between artifact instructions and the user's real local
  workflow

These lessons are now part of the default validation discipline.
