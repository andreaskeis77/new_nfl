from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from new_nfl.settings import Settings


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    source_name: str
    source_tier: str
    source_kind: str
    source_priority: int
    transport: str
    extraction_mode: str
    owner_status: str
    dry_run_supported: bool
    notes: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AdapterPlan:
    adapter_id: str
    source_name: str
    registry_bound: bool
    transport: str
    extraction_mode: str
    raw_landing_prefix: str
    stage_dataset: str
    source_status: str
    notes: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class StaticSourceAdapter:
    def __init__(self, descriptor: AdapterDescriptor) -> None:
        self._descriptor = descriptor

    @property
    def adapter_id(self) -> str:
        return self._descriptor.adapter_id

    def describe(self) -> AdapterDescriptor:
        return self._descriptor

    def build_plan(
        self,
        settings: Settings,
        *,
        registry_bound: bool,
        source_status: str,
    ) -> AdapterPlan:
        raw_prefix = _build_raw_prefix(settings, self._descriptor.adapter_id)
        stage_dataset = f"stg.{self._descriptor.adapter_id}"
        return AdapterPlan(
            adapter_id=self._descriptor.adapter_id,
            source_name=self._descriptor.source_name,
            registry_bound=registry_bound,
            transport=self._descriptor.transport,
            extraction_mode=self._descriptor.extraction_mode,
            raw_landing_prefix=str(raw_prefix),
            stage_dataset=stage_dataset,
            source_status=source_status,
            notes=self._descriptor.notes,
        )


def _build_raw_prefix(settings: Settings, adapter_id: str) -> Path:
    return settings.raw_root / "planned" / adapter_id
