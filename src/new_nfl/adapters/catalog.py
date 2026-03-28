from __future__ import annotations

from new_nfl.adapters.base import AdapterDescriptor, AdapterPlan, StaticSourceAdapter
from new_nfl.metadata import list_sources
from new_nfl.settings import Settings


def _default_adapters() -> list[StaticSourceAdapter]:
    return [
        StaticSourceAdapter(
            AdapterDescriptor(
                adapter_id="nflverse_bulk",
                source_name="nflverse bulk datasets",
                source_tier="A",
                source_kind="dataset",
                source_priority=10,
                transport="file",
                extraction_mode="bulk_snapshot",
                owner_status="skeleton",
                dry_run_supported=True,
                notes=(
                    "Primary bulk adapter skeleton for historical and weekly datasets."
                ),
            )
        ),
        StaticSourceAdapter(
            AdapterDescriptor(
                adapter_id="official_context_web",
                source_name="official context web source",
                source_tier="B",
                source_kind="web",
                source_priority=20,
                transport="http",
                extraction_mode="context_enrichment",
                owner_status="skeleton",
                dry_run_supported=True,
                notes=(
                    "Secondary web-context adapter skeleton for official schedule "
                    "and context pages."
                ),
            )
        ),
        StaticSourceAdapter(
            AdapterDescriptor(
                adapter_id="public_stats_api",
                source_name="public stats api candidate",
                source_tier="B",
                source_kind="api",
                source_priority=30,
                transport="http",
                extraction_mode="incremental_api",
                owner_status="skeleton",
                dry_run_supported=True,
                notes=(
                    "Secondary API adapter skeleton for structured near-real-time "
                    "stats feeds."
                ),
            )
        ),
        StaticSourceAdapter(
            AdapterDescriptor(
                adapter_id="reference_html_fallback",
                source_name="reference html fallback",
                source_tier="C",
                source_kind="web",
                source_priority=90,
                transport="http",
                extraction_mode="html_fallback",
                owner_status="skeleton",
                dry_run_supported=True,
                notes=(
                    "Fallback HTML adapter skeleton used only when primary and "
                    "secondary paths fail."
                ),
            )
        ),
    ]


def list_adapter_descriptors() -> list[AdapterDescriptor]:
    return [adapter.describe() for adapter in _default_adapters()]


def get_adapter_descriptor(adapter_id: str) -> AdapterDescriptor | None:
    for adapter in _default_adapters():
        descriptor = adapter.describe()
        if descriptor.adapter_id == adapter_id:
            return descriptor
    return None


def build_adapter_plan(settings: Settings, adapter_id: str) -> AdapterPlan:
    registry_index = _source_registry_index(settings)
    for adapter in _default_adapters():
        descriptor = adapter.describe()
        if descriptor.adapter_id != adapter_id:
            continue
        source_row = registry_index.get(adapter_id)
        return adapter.build_plan(
            settings,
            registry_bound=source_row is not None,
            source_status=(source_row or {}).get("source_status", "missing"),
        )
    msg = f"Unknown adapter_id: {adapter_id}"
    raise KeyError(msg)


def adapter_binding_rows(settings: Settings) -> list[dict[str, object]]:
    registry_index = _source_registry_index(settings)
    rows: list[dict[str, object]] = []
    for descriptor in list_adapter_descriptors():
        source_row = registry_index.get(descriptor.adapter_id)
        rows.append(
            {
                "adapter_id": descriptor.adapter_id,
                "source_tier": descriptor.source_tier,
                "transport": descriptor.transport,
                "extraction_mode": descriptor.extraction_mode,
                "registry_bound": source_row is not None,
                "source_status": (source_row or {}).get("source_status", "missing"),
                "source_name": descriptor.source_name,
            }
        )
    return rows


def _source_registry_index(settings: Settings) -> dict[str, dict[str, object]]:
    rows = list_sources(settings)
    return {str(row["source_id"]): row for row in rows}
