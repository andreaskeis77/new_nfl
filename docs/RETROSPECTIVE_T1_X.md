# RETROSPECTIVE_T1_X

## Purpose

This document captures the method lessons from the T1.x cycle.

The purpose is not to pretend that defects can be eliminated entirely. The
purpose is to identify recurring failure classes and turn them into better
engineering rules.

## What worked

The T1.x cycle already demonstrated several strengths:

- defects became visible rather than hidden
- tests and CLI checks produced actionable signals
- handoffs and docs were updated alongside technical work
- fixes became progressively smaller and more localized
- packaging and delivery discipline improved significantly over time

## Main failure patterns observed

### 1. Compatibility drift against existing local state

Several changes worked on fresh states or isolated tests, but failed against the
user's real local DuckDB and metadata surface.

Examples included:

- old vs new metadata columns
- legacy table constraints
- inserts failing on required columns in evolved local schemas

### 2. Internal contract drift

Modules stopped speaking the same API.

Examples included:

- fields expected by one module but missing from another
- exports referenced in `__init__` but absent in underlying modules
- descriptor/plan responsibilities drifting without coordinated replay

### 3. Replay gaps

New paths were tested, but previously green paths were not always replayed with
the same rigor.

That allowed regressions to survive until Andreas executed the commands on the
real repo state.

### 4. Mixed tranches

Some tranches mixed:

- new feature work
- compatibility work
- API refactors
- schema evolution
- docs/process updates

That increased the chance of multi-cause failures.

## What this means

The problem was not simply "there were bugs".

The more useful diagnosis is:

- validation order was not strict enough
- compatibility with evolved state was under-checked
- public contract surfaces were not treated explicitly enough
- tranches were sometimes larger than ideal for the change type

## Method changes adopted from this retrospective

### 1. Collection-first validation

Import/collection is now a required early gate before feature-path validation.

### 2. Replay-before-new-path rule

The last relevant green path must be replayed before the new path is accepted.

### 3. Fresh-state and evolved-state thinking

Both are now required mental models for validation. Fresh-state-only confidence
is insufficient.

### 4. Contract-surface thinking

Public exports, dataclass/model fields, CLI surfaces, and core metadata columns
must be treated as explicit compatibility surfaces.

### 5. No partial green status

A tranche is not green if a required operational path is still red, even if
lint and tests pass.

### 6. Smaller compatibility bolts

When failure is clearly localized, the preferred repair is a narrowly scoped
compatibility bolt, not a broader rework.

## Practical checklist for future cycles

Before marking a tranche green, challenge it with these questions:

1. What was the last green path?
2. Did we replay it?
3. What public contract surface could this change break?
4. Did we think about the evolved local DB state?
5. Is there any required execute path still red?
6. Are we mixing too many concerns in one tranche?

## What should improve next

For the next cycles, the main improvement goals are:

- fewer compatibility regressions against evolved local state
- earlier detection of collection/import drift
- more explicit contract tests
- smaller and more isolated compatibility fixes
- better separation between feature tranches and cleanup tranches

## Final judgment on T1.x

T1.x was not perfect, but it was productive.

The cycle already built a functioning engineering spine:

- method foundation
- metadata registry
- adapter skeleton
- fetch contract
- first remote-fetch path

The next step is not to demand perfection. It is to preserve learning and
reduce avoidable error classes in T1.4/T1.5 and beyond.
