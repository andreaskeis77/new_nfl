from __future__ import annotations

import json
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from new_nfl.adapters.catalog import build_adapter_plan, get_adapter_descriptor
from new_nfl.metadata import (
    compute_sha256,
    create_ingest_run,
    get_source,
    record_load_event,
    record_source_file,
)
from new_nfl.settings import Settings


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RemoteFetchResult:
    adapter_id: str
    pipeline_name: str
    run_mode: str
    run_status: str
    ingest_run_id: str
    landing_dir: str
    manifest_path: str
    receipt_path: str
    load_event_id: str
    landed_file_count: int
    asset_count: int
    stage_dataset: str
    source_status: str
    source_url: str
    downloaded_file_path: str
    downloaded_bytes: int
    sha256_hex: str


def _filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    candidate = Path(parsed.path).name.strip()
    return candidate or "downloaded_asset.bin"


def execute_remote_fetch(
    settings: Settings,
    *,
    adapter_id: str,
    execute: bool,
    remote_url_override: str | None = None,
) -> RemoteFetchResult:
    descriptor = get_adapter_descriptor(adapter_id)
    if descriptor is None:
        raise ValueError(f"Unknown adapter_id={adapter_id}")

    source = get_source(settings, adapter_id)
    if source is None:
        raise ValueError(f"Unknown source registry entry for adapter_id={adapter_id}")

    pipeline_name = f"adapter.{adapter_id}.remote_fetch"
    remote_url = (remote_url_override or source.get("default_remote_url") or "").strip()
    if not remote_url:
        raise ValueError(f"No remote URL configured for adapter_id={adapter_id}")

    plan = build_adapter_plan(settings, adapter_id)

    if not execute:
        landing_dir = str(settings.raw_root / "landed" / adapter_id / "<planned-remote>")
        return RemoteFetchResult(
            adapter_id=adapter_id,
            pipeline_name=pipeline_name,
            run_mode="dry_run",
            run_status="planned_remote_fetch",
            ingest_run_id="",
            landing_dir=landing_dir,
            manifest_path="",
            receipt_path="",
            load_event_id="",
            landed_file_count=0,
            asset_count=1,
            stage_dataset=plan.stage_dataset,
            source_status=plan.source_status,
            source_url=remote_url,
            downloaded_file_path="",
            downloaded_bytes=0,
            sha256_hex="",
        )

    ingest_run_id = create_ingest_run(
        settings,
        pipeline_name=pipeline_name,
        adapter_id=adapter_id,
        run_mode="execute",
        run_status="remote_fetched",
        trigger_kind="cli",
        landing_dir="",
        manifest_path="",
        receipt_path="",
        asset_count=1,
        landed_file_count=3,
        message="T1.4 first true remote fetch",
    )
    landing_dir = settings.raw_root / "landed" / adapter_id / ingest_run_id
    landing_dir.mkdir(parents=True, exist_ok=True)

    filename = _filename_from_url(remote_url)
    downloaded_file_path = landing_dir / filename
    request_manifest_path = landing_dir / "request_manifest.json"
    fetch_receipt_path = landing_dir / "fetch_receipt.json"

    with urllib.request.urlopen(remote_url) as response:
        with downloaded_file_path.open("wb") as fh:
            shutil.copyfileobj(response, fh)

    downloaded_bytes = downloaded_file_path.stat().st_size
    sha256_hex = compute_sha256(downloaded_file_path)

    manifest_payload = {
        "adapter_id": adapter_id,
        "pipeline_name": pipeline_name,
        "remote_url": remote_url,
        "run_mode": "execute",
        "planned_assets": 1,
        "stage_dataset": plan.stage_dataset,
        "descriptor": descriptor.as_dict(),
        "created_at": _utc_timestamp(),
    }
    request_manifest_path.write_text(
        json.dumps(manifest_payload, indent=2),
        encoding="utf-8",
    )

    source_file_id = record_source_file(
        settings,
        ingest_run_id=ingest_run_id,
        adapter_id=adapter_id,
        source_url=remote_url,
        local_path=str(downloaded_file_path),
        file_size_bytes=downloaded_bytes,
        sha256_hex=sha256_hex,
    )
    receipt_payload = {
        "adapter_id": adapter_id,
        "pipeline_name": pipeline_name,
        "run_status": "remote_fetched",
        "source_url": remote_url,
        "downloaded_file_path": str(downloaded_file_path),
        "downloaded_bytes": downloaded_bytes,
        "sha256_hex": sha256_hex,
        "source_file_id": source_file_id,
        "created_at": _utc_timestamp(),
    }
    fetch_receipt_path.write_text(
        json.dumps(receipt_payload, indent=2),
        encoding="utf-8",
    )

    load_event_id = record_load_event(
        settings,
        ingest_run_id=ingest_run_id,
        pipeline_name=pipeline_name,
        event_kind="remote_raw_landing",
        source_id=adapter_id,
        object_path=str(fetch_receipt_path),
        payload=receipt_payload,
    )

    return RemoteFetchResult(
        adapter_id=adapter_id,
        pipeline_name=pipeline_name,
        run_mode="execute",
        run_status="remote_fetched",
        ingest_run_id=ingest_run_id,
        landing_dir=str(landing_dir),
        manifest_path=str(request_manifest_path),
        receipt_path=str(fetch_receipt_path),
        load_event_id=load_event_id,
        landed_file_count=3,
        asset_count=1,
        stage_dataset=plan.stage_dataset,
        source_status=plan.source_status,
        source_url=remote_url,
        downloaded_file_path=str(downloaded_file_path),
        downloaded_bytes=downloaded_bytes,
        sha256_hex=sha256_hex,
    )
