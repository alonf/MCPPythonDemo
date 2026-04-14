"""Tool implementations for the Linux diagnostics server."""

from .processes import (
    BasicProcessInfo,
    ProcessDetailResult,
    ProcessMemorySnapshot,
    ProcessQueryResult,
    get_process_by_id,
    get_processes_by_name,
    list_processes,
)
from .system_info import SystemInfoResult, collect_system_info

ProcessInfoResult = ProcessDetailResult
ProcessMemoryUsage = ProcessMemorySnapshot
get_process_by_name = get_processes_by_name
get_process_list = list_processes

__all__ = [
    "BasicProcessInfo",
    "ProcessDetailResult",
    "ProcessInfoResult",
    "ProcessMemorySnapshot",
    "ProcessMemoryUsage",
    "ProcessQueryResult",
    "SystemInfoResult",
    "collect_system_info",
    "get_process_by_id",
    "get_processes_by_name",
    "get_process_by_name",
    "list_processes",
    "get_process_list",
]
