# NEW NFL Delivery Protocol

Status: active
Owner: Andreas + ChatGPT
Last updated: 2026-03-27

## Purpose

This document defines how ChatGPT delivers repository changes to Andreas and how Andreas applies them on the development laptop or VPS. It exists because delivery mistakes are not theoretical; they can create repository noise, accidental nested directories, or tracked runtime artifacts. Delivery mechanics are therefore part of the engineering method and not an afterthought.

## Core Rules

1. Every ZIP file delivered by ChatGPT must have a unique filename.
2. The ZIP archive content must mirror the repository root directly.
3. A ZIP archive must not introduce an additional wrapper folder unless explicitly announced and intentionally required.
4. ChatGPT must explicitly state the expected extraction target and whether the ZIP is flat-root or wrapper-folder based.
5. Andreas should extract ZIP files into the repository root only after the target path is stated explicitly.
6. After extraction, `git status` is the mandatory truth source.
7. Runtime-generated local state must not be committed unless the tranche explicitly says so.
8. If a packaging error occurs, the correction must be documented in repository files and not only in chat.

## ZIP Naming Standard

ZIP filenames must use this pattern:

`newnfl_<phase>_<scope>_<YYYYMMDD>_<sequence>.zip`

Examples:

- `newnfl_A0_3_source_governance_20260327_001.zip`
- `newnfl_T1_0_technical_bootstrap_20260327_001.zip`

Rules:

- `<phase>` is the tranche or repair identifier.
- `<scope>` is short, stable, and descriptive.
- `<sequence>` starts at `001` for a given day and scope if needed.
- Filenames must remain unique so the local Downloads folder does not become ambiguous.

## Archive Layout Standard

Default rule: the ZIP archive must be **flat-root** relative to the repository.

That means the archive content should look like this when opened:

- `README.md`
- `docs/...`
- `src/...`
- `tests/...`
- `tools/...`

It must **not** look like this unless explicitly intended:

- `newnfl_T1_0C_repo_cleanup_20260327_001/README.md`
- `newnfl_T1_0C_repo_cleanup_20260327_001/docs/...`

A wrapper folder creates a high risk of accidental nested content inside the Git repository and is therefore forbidden by default.

## Delivery Contract in Every Tranche

Every delivery message from ChatGPT must include:

- ZIP filename
- purpose of the tranche
- exact extraction target
- whether the archive is flat-root
- exact commands to validate the result
- expected `git status` shape
- commit message proposal

## Extraction Protocol

### DEV-LAPTOP

Standard extraction target:

`C:\projekte\newnfl`

Standard command pattern:

```powershell
Set-Location C:\projekte\newnfl
$zip = "$env:USERPROFILE\Downloads\<zipfile>.zip"
Expand-Archive -LiteralPath $zip -DestinationPath C:\projekte\newnfl -Force
git status
```

### VPS

The same pattern applies, but only when ChatGPT explicitly marks the step as `VPS-USER` or `VPS-ADMIN`.

## Post-Extraction Validation

Immediately after extraction Andreas must run:

```powershell
git status
```

Validation questions:

- Are the expected files modified or added?
- Did any unexpected top-level directory appear?
- Did any runtime artifacts become tracked?
- Does the file placement match the tranche description?

If the answer to any of these is no, the tranche is not green.

## Runtime Artifact Rule

Examples of local runtime artifacts that should normally remain untracked:

- `data/db/*.duckdb`
- transient logs
- local caches
- temporary exports
- environment-specific state files unless explicitly versioned

If a runtime artifact is accidentally committed:

1. untrack it
2. strengthen ignore rules
3. document the mistake and correction in the repo
4. only then continue

## Packaging Error Procedure

If ChatGPT delivers a malformed ZIP or wrong archive layout:

1. stop and do not wave the issue through
2. inspect `git status`
3. remove accidental nested directories or wrongly placed files
4. correct tracking state with Git
5. add or update a handoff documenting the incident
6. update this delivery protocol or another governing document if the mistake reveals a missing rule

## Decision Rule

ChatGPT must prefer a slightly more verbose delivery instruction over an ambiguous one.

Andreas must prefer validating the repository state over assuming the extraction worked.

## Current Operating Assumption

All future NEW NFL ZIP deliveries are expected to be **flat-root archives** unless explicitly stated otherwise.
