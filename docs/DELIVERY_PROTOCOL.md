# DELIVERY_PROTOCOL

## Purpose

This document defines how ChatGPT-delivered ZIP packages are structured, applied,
validated, and corrected in the NEW NFL repo.

## Default ZIP rule

All ZIP deliveries for this project must use **flat-root packaging**.

That means:
- files in the ZIP map directly to repository-relative paths
- the ZIP must not introduce an additional wrapper directory unless that wrapper
  directory is explicitly requested
- extraction target is the repository root unless explicitly stated otherwise

Example:

Correct:
- `src/new_nfl/metadata.py`
- `docs/_handoff/HANDOFF_T1_1C_final_quality_gate_fix.md`

Incorrect:
- `newnfl_T1_1C_final_quality_gate_fix_20260327_001/src/new_nfl/metadata.py`

## ZIP naming rule

ZIP names must be unique and follow this pattern:

`newnfl_<phase>_<scope>_<YYYYMMDD>_<counter>.zip`

Example:
- `newnfl_T1_1C_final_gate_and_delivery_doc_20260327_001.zip`

## Required assistant instructions per ZIP delivery

Every ZIP delivery must state:
- the exact filename
- the exact extraction target
- whether the archive is flat-root or intentionally wrapped
- the list of new or modified files
- acceptance criteria
- the exact DEV-LAPTOP or VPS command sequence

## Full-file delivery rule

For NEW NFL, the delivery default is:

- ChatGPT provides complete affected files
- complete files are delivered in a ZIP package
- Andreas should not need to reconstruct files from fragments
- Andreas should not need to search for single lines to replace

This applies especially to:
- implementation tranches
- bug-fix tranches
- debug tranches
- quality-gate repair tranches

Not the default:
- line-by-line patch instructions
- “search this line and replace it” workflows
- partial snippets that Andreas must merge manually

Allowed only as explicit exception:
- Andreas asks for a manual edit
- an urgent hotfix requires a temporary one-line operational correction

If an exception is used, it must be stated explicitly in the delivery instructions.

## Required user validation after extraction

Immediately after extraction, validate with:

```powershell
Set-Location C:\projekte\newnfl
git status
```

`git status` is the source of truth for whether the package landed in the expected
paths.

## Packaging failure rule

If a ZIP introduces an unintended wrapper directory or writes files into wrong
paths:
- stop feature progress
- fix the repository state first
- document the error in a handoff
- only then continue with the next tranche

## Runtime artifact rule

Local runtime artifacts must stay out of Git unless explicitly intended.

Examples:
- local DuckDB database files stay local-only
- `.gitkeep` may be used to preserve expected directory structure
- `.gitignore` must protect generated runtime state

## Commit gate rule

A tranche is not green if:
- required runtime validation failed
- required tests failed
- required lint/format gates failed
- the repo contains unintended packaged artifacts

## Practical lessons captured from early NEW NFL work

The project already encountered these concrete delivery and packaging issues:
- accidental ZIP wrapper directory committed into the repo
- local DuckDB file accidentally committed
- CLI/runtime behavior green while lint gate was still red
- migration logic working in tests but failing against an existing local database
  until compatibility fixes were added
- a manual line-edit instruction was given even though the project standard is
  full-file ZIP delivery

These are now part of the standard delivery discipline for future tranches.
