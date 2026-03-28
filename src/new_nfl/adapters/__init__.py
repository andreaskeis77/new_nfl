from new_nfl.adapters.catalog import (
    adapter_binding_rows,
    build_adapter_plan,
    get_adapter_descriptor,
    list_adapter_descriptors,
)
from new_nfl.adapters.fetch_contract import (
    AdapterExecutionResult,
    execute_adapter_contract,
    latest_adapter_run_summary,
)

__all__ = [
    'AdapterExecutionResult',
    'adapter_binding_rows',
    'build_adapter_plan',
    'execute_adapter_contract',
    'get_adapter_descriptor',
    'latest_adapter_run_summary',
    'list_adapter_descriptors',
]
