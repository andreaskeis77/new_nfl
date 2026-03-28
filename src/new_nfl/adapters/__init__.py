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

__all__ = [
    'AdapterExecutionResult',
    'AdapterPlan',
    'ContractRunResult',
    'RemoteFetchResult',
    'adapter_binding_rows',
    'build_adapter_plan',
    'execute_adapter_contract',
    'execute_fetch_contract',
    'execute_remote_fetch',
    'get_adapter_descriptor',
    'latest_adapter_run_summary',
    'list_adapter_descriptors',
]
