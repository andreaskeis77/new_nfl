from new_nfl.adapters.catalog import (
    AdapterPlan,
    adapter_binding_rows,
    build_adapter_plan,
    get_adapter_descriptor,
    list_adapter_descriptors,
)
from new_nfl.adapters.fetch_contract import (
    AdapterExecutionResult,
    ContractRunResult,
    execute_adapter_contract,
    execute_fetch_contract,
    latest_adapter_run_summary,
)
from new_nfl.adapters.remote_fetch import RemoteFetchResult, execute_remote_fetch
from new_nfl.adapters.slices import (
    DEFAULT_SLICE_KEY,
    SLICE_REGISTRY,
    SliceSpec,
    get_slice,
    list_slices,
    list_slices_for_adapter,
)

__all__ = [
    'AdapterExecutionResult',
    'AdapterPlan',
    'ContractRunResult',
    'DEFAULT_SLICE_KEY',
    'RemoteFetchResult',
    'SLICE_REGISTRY',
    'SliceSpec',
    'adapter_binding_rows',
    'build_adapter_plan',
    'execute_adapter_contract',
    'execute_fetch_contract',
    'execute_remote_fetch',
    'get_adapter_descriptor',
    'get_slice',
    'latest_adapter_run_summary',
    'list_adapter_descriptors',
    'list_slices',
    'list_slices_for_adapter',
]
