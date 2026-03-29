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
- `newnfl_T1_1C_final_gate_fix/src/new_nfl/metadata.py`

## ZIP naming rule

ZIP names must be unique and follow this pattern:

`newnfl_<cycle>_<bolt>_<short_title>_<yyyymmdd>_<nnn>.zip`

Example:
- `newnfl_T1_5_repair_01_stage_load_export_fix_20260328_001.zip`

## Required assistant instructions per ZIP delivery

Every ZIP delivery must state:
- the exact filename
- the exact extraction target
- whether the archive is flat-root or intentionally wrapped
- the list of new or modified files
- acceptance criteria
- the exact DEV-LAPTOP or VPS command sequence


## Mandatory response structure

For NEW NFL, delivery messages must clearly separate:

### Einordnung
- short context or rationale
- only as much explanation as needed for the next decision
- no operational steps hidden in prose

### Aktion
- concrete operator instructions
- explicit location such as DEV-LAPTOP, VPS-USER, or VPS-ADMIN
- copyable commands
- expected result
- what Andreas should report back

Rule:
- Andreas must be able to identify the executable step immediately.
- Explanatory text and action text must not be mixed in a way that forces
  interpretation.
- ZIP deliveries must put the apply block and validation commands under the
  **Aktion** section.

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

If an exception is used, it must be stated explicitly in the delivery
instructions.

## Default artifact landing location

For NEW NFL on the DEV-LAPTOP, delivered ZIP files are assumed to be stored in
the Windows user's **Downloads** folder unless Andreas explicitly states a
different landing location.

Default source location:
- `C:\Users\<windows-user>\Downloads`

The assistant must not invent an alternative default such as a repo-local
`_drop/` folder unless Andreas explicitly requested that workflow.

## Mandatory apply block

Every ZIP delivery must include an explicit **DEV-LAPTOP apply block** that:
1. resolves the ZIP from the Windows user's Downloads folder
2. extracts it into a repo-local temporary apply directory
3. copies the delivered files into the repository root paths
4. performs a quick post-apply sanity check
5. removes temporary apply directories after validation

This apply block is mandatory. The user should not need to infer how the ZIP is
supposed to be applied.

## No manual copy/paste fallback by default

For NEW NFL, manual copy/paste replacement of Python or documentation files is
**not** the default repair path.

Do not fall back to manual code copy/paste unless:
- Andreas explicitly asks for manual overwrite instructions, or
- a ZIP path is temporarily impossible and the exception is stated clearly

## Required user validation after extraction

Immediately after apply, validate with:

```powershell
Set-Location C:\projekte\newnfl
git status --short
```

`git status --short` is the source of truth for whether the package landed in
the expected paths.

## Post-apply hygiene rule

Temporary apply directories created only for ZIP delivery must be removed after
the validation step unless Andreas explicitly wants them kept for inspection.

Typical temporary path:
- `C:\projekte\newnfl\_apply\<bolt_name>`

These directories must not remain as accidental untracked repo clutter.

## Packaging failure rule

If a ZIP introduces an unintended wrapper directory, writes files into wrong
paths, or the apply instructions rely on the wrong default landing location:
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
- a required operational path is still red even if tests are green

## Practical lessons captured from T1.x and the T1.5 repair

The project already encountered these concrete delivery and packaging issues:
- accidental ZIP wrapper directory committed into the repo
- local DuckDB file accidentally committed
- CLI/runtime behavior green while lint gate was still red
- migration logic working in tests but failing against an existing local
  database until compatibility fixes were added
- a manual line-edit instruction was given even though the project standard is
  full-file ZIP delivery
- new feature paths were checked before replaying the last green path
- tests passed while a required CLI execute path was still red
- an artifact was delivered without an explicit apply block
- a delivery assumed the wrong local landing folder instead of the Windows
  Downloads folder
- a fallback into manual copy/paste caused unnecessary operator friction

These are now part of the standard delivery discipline for future tranches.
