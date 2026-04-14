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
from .log_snapshots import (
    LogSnapshotLine,
    LogSnapshotPage,
    LogSnapshotPagination,
    LogSnapshotSummary,
    clear_log_snapshots,
    create_log_snapshot,
    get_log_snapshot_page,
    render_log_snapshot_resource,
)
from .system_info import SystemInfoResult, collect_system_info

ProcessInfoResult = ProcessDetailResult
ProcessMemoryUsage = ProcessMemorySnapshot
get_process_by_name = get_processes_by_name
get_process_list = list_processes

__all__ = [
    "BasicProcessInfo",
    "LogSnapshotLine",
    "LogSnapshotPage",
    "LogSnapshotPagination",
    "LogSnapshotSummary",
    "ProcessDetailResult",
    "ProcessInfoResult",
    "ProcessMemorySnapshot",
    "ProcessMemoryUsage",
    "ProcessQueryResult",
    "SystemInfoResult",
    "collect_system_info",
    "create_log_snapshot",
    "clear_log_snapshots",
    "get_process_by_id",
    "get_processes_by_name",
    "get_process_by_name",
    "get_log_snapshot_page",
    "list_processes",
    "get_process_list",
    "render_log_snapshot_resource",
]
