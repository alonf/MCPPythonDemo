"""Tool implementations for the Linux diagnostics server."""

from .processes import (
    BasicProcessInfo,
    KillProcessResult,
    ProcessCpuUsage,
    ProcessDetailResult,
    ProcessMemorySnapshot,
    ProcessQueryResult,
    get_process_by_id,
    get_process_candidate_by_id,
    get_processes_by_name,
    kill_process,
    list_processes,
    sample_top_cpu_processes,
)
from .m6_diagnostics import (
    LinuxDiagnosticObservation,
    LinuxDiagnosticQuery,
    extract_sampling_text,
    read_linux_diagnostic,
    troubleshoot_linux_diagnostics,
    validate_linux_diagnostic_query,
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
    "KillProcessResult",
    "LinuxDiagnosticObservation",
    "LinuxDiagnosticQuery",
    "ProcessCpuUsage",
    "ProcessDetailResult",
    "ProcessInfoResult",
    "ProcessMemorySnapshot",
    "ProcessMemoryUsage",
    "ProcessQueryResult",
    "SystemInfoResult",
    "collect_system_info",
    "create_log_snapshot",
    "clear_log_snapshots",
    "extract_sampling_text",
    "get_process_by_id",
    "get_process_candidate_by_id",
    "get_processes_by_name",
    "get_process_by_name",
    "get_log_snapshot_page",
    "kill_process",
    "list_processes",
    "get_process_list",
    "read_linux_diagnostic",
    "render_log_snapshot_resource",
    "sample_top_cpu_processes",
    "troubleshoot_linux_diagnostics",
    "validate_linux_diagnostic_query",
]
