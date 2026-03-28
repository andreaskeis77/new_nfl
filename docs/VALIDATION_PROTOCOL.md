# VALIDATION_PROTOCOL

## Purpose

This document defines the preferred preflight validation pattern before ChatGPT
hands over a NEW NFL tranche.

## Minimum preflight sequence

1. Replay assumptions from the latest green tranche.
2. Check fresh-state behavior.
3. Check upgrade behavior against an already-evolved local database.
4. Clear import and collection failures before deeper tests.
5. Preserve public exports used by existing CLI commands and tests, or update all
   dependent files in the same tranche.
6. Clear lint and formatting failures before handoff.
7. Only then hand the tranche to Andreas.

## Required replay classes

Every tranche should be checked against these classes before handoff:

- module import / test collection
- existing green CLI commands from the previous tranche
- new CLI commands introduced by the current tranche
- lint / format gates
- pytest gates

## Why this exists

The project already experienced repeated failures caused by:

- schema drift against an existing local DuckDB file
- regressions against already-existing tests and CLI surfaces
- packaging that looked correct in isolation but not against the real repo state
- lint issues that were introduced after a functional fix
- collection failures caused by missing exports during adapter refactors

This protocol exists to reduce those failure classes.

## Collection-first rule

If imports or pytest collection fail, deeper validation is not considered valid.
The first repair target must then be import compatibility and public surface
stability.

## Delivery consequence

If a tranche fails collection or a previous green CLI path, the tranche is still
red and must be repaired before it is treated as complete.
