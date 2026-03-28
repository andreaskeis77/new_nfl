# ADR-0022 Remote Fetch Asset Manifest and Checksum Receipt

Status: Accepted

## Decision
Each execute-mode remote fetch writes:
- `request_manifest.json`
- `fetch_receipt.json`
- at least one downloaded payload file

The receipt must include:
- source URL
- byte size
- SHA-256 checksum
- local file path
- ingest run id
- adapter id

## Rationale
Remote fetches must be auditable and reproducible at the file level before staging logic is added.
