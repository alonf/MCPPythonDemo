"""Milestone 3 MCP server entrypoint."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_linux_diag_server.tools import (
    BasicProcessInfo,
    LogSnapshotSummary,
    ProcessDetailResult,
    ProcessQueryResult,
    SystemInfoResult,
    collect_system_info,
    create_log_snapshot as collect_log_snapshot,
    get_process_by_id as collect_process_by_id,
    get_processes_by_name as collect_processes_by_name,
    render_log_snapshot_resource,
    list_processes as collect_process_list,
)

server = FastMCP(
    name="Linux Diagnostics Demo",
    instructions=(
        "Milestone 3 teaching server. Use tools to collect Linux diagnostics, "
        "read snapshot resources for larger results, and discover prompts for guided workflows."
    ),
)


@server.tool(
    name="get_system_info",
    title="Get System Info",
    description="Return a small Linux system snapshot that works on Ubuntu and WSL.",
)
def get_system_info() -> SystemInfoResult:
    """Return a minimal Linux diagnostics snapshot."""
    return collect_system_info()


@server.tool(
    name="get_process_list",
    title="Get Process List",
    description="Return a lightweight Linux process list with process names and PIDs. Use this before requesting detail.",
)
def get_process_list() -> list[BasicProcessInfo]:
    """Return a lightweight Linux process list."""
    return collect_process_list()


@server.tool(
    name="get_process_by_id",
    title="Get Process By ID",
    description="Return detailed Linux process information for one PID.",
)
def get_process_by_id(
    process_id: Annotated[int, Field(description="Linux process ID to inspect.")],
) -> ProcessDetailResult:
    """Return detailed Linux process information for one PID."""
    return collect_process_by_id(process_id)


@server.tool(
    name="get_process_by_name",
    title="Get Process By Name",
    description="Return paged detailed Linux process information for a process name. Defaults to page 1 and 5 results per page.",
)
def get_process_by_name(
    process_name: Annotated[str, Field(description="Process name to match, such as python or python3.")],
    page_number: Annotated[int | None, Field(description="Optional page number. Defaults to 1.")] = None,
    page_size: Annotated[int | None, Field(description="Optional page size. Defaults to 5.")] = None,
) -> ProcessQueryResult:
    """Return paged detailed Linux process information for a process name."""
    return collect_processes_by_name(process_name, page_number=page_number, page_size=page_size)


@server.tool(
    name="create_log_snapshot",
    title="Create Log Snapshot",
    description=(
        "Create an immutable snapshot from a common Linux log file and return a resource URI. "
        "When log_name is omitted, the server picks the first supported local source."
    ),
)
def create_log_snapshot(
    log_name: Annotated[
        str | None,
        Field(description="Optional Linux log to snapshot: system, security, kernel, or package."),
    ] = None,
    filter_text: Annotated[
        str | None,
        Field(description="Optional case-insensitive substring filter to keep only matching log lines."),
    ] = None,
    max_lines: Annotated[
        int | None,
        Field(description="Optional max number of matching lines to retain. Defaults to 200."),
    ] = None,
) -> LogSnapshotSummary:
    """Create a Linux log snapshot and return the resource URIs needed to read it."""
    return collect_log_snapshot(log_name=log_name, filter_text=filter_text, max_lines=max_lines)


@server.resource(
    "syslog://snapshot/{snapshot_id}",
    name="Linux Log Snapshot",
    title="Linux Log Snapshot",
    description="Read a stored Linux log snapshot using the default limit=50 and offset=0.",
    mime_type="application/json",
)
def get_log_snapshot_resource(snapshot_id: str) -> str:
    """Read a stored Linux log snapshot."""
    return render_log_snapshot_resource(snapshot_id)


@server.resource(
    "syslog://snapshot/{snapshot_id}?limit={limit}&offset={offset}",
    name="Paged Linux Log Snapshot",
    title="Paged Linux Log Snapshot",
    description="Read a stored Linux log snapshot with explicit pagination.",
    mime_type="application/json",
)
def get_log_snapshot_resource_page(snapshot_id: str, limit: int, offset: int) -> str:
    """Read one page of a stored Linux log snapshot."""
    return render_log_snapshot_resource(snapshot_id, limit=limit, offset=offset)


@server.prompt(
    name="AnalyzeRecentApplicationErrors",
    title="Analyze Recent Application Errors",
    description="Guide the client through Linux log snapshot creation, pagination, and error analysis.",
)
def analyze_recent_application_errors(
    search_text: Annotated[str, Field(description="Text to look for in the application or system log. Defaults to error.")] = "error",
) -> str:
    """Guide an application-error troubleshooting workflow."""
    return (
        "Analyze recent application-style errors on this Linux machine.\n\n"
        "1. Call `create_log_snapshot` with `{\"log_name\": \"system\", \"filter_text\": "
        f"\"{search_text}\", \"max_lines\": 200}}`.\n"
        "2. Take the returned `resource_uri` and read it with `read_resource`.\n"
        "3. If the snapshot has `pagination.has_more=true`, keep reading the next pages by increasing "
        "`offset` in the paginated resource URI.\n"
        "4. Group repeated failures by service name, executable name, or recurring message text.\n"
        "5. Summarize the likely root cause, impacted components, and the next Linux checks to run."
    )


@server.prompt(
    name="ExplainHighCpu",
    title="Explain High CPU",
    description="Guide the client through correlating CPU-heavy processes with Linux logs.",
)
def explain_high_cpu() -> str:
    """Guide a multi-tool CPU troubleshooting workflow."""
    return (
        "Explain sustained high CPU usage by correlating process data with Linux logs.\n\n"
        "1. Call `get_process_list` and identify the most relevant PIDs.\n"
        "2. Use `get_process_by_id` or `get_process_by_name` for detailed drill-down on the top processes.\n"
        "3. Create a `system` log snapshot filtered to `error` or the process name when relevant.\n"
        "4. Read the snapshot resource page-by-page and look for crashes, throttling, restart loops, or I/O failures.\n"
        "5. Report the likely cause, the process most involved, and concrete remediation steps."
    )


@server.prompt(
    name="DetectSecurityAnomalies",
    title="Detect Security Anomalies",
    description="Guide the client through reviewing suspicious processes and security-relevant logs.",
)
def detect_security_anomalies(
    search_text: Annotated[str, Field(description="Text to look for in the security log. Defaults to failed.")] = "failed",
) -> str:
    """Guide a Linux security review workflow."""
    return (
        "Review this machine for security-relevant anomalies.\n\n"
        "1. Start with `get_process_list` and flag unusual or unexpected process names.\n"
        "2. Drill into suspicious processes with `get_process_by_id`.\n"
        "3. Call `create_log_snapshot` with `{\"log_name\": \"security\", \"filter_text\": "
        f"\"{search_text}\", \"max_lines\": 200}}`.\n"
        "4. Read the snapshot resource and look for repeated authentication failures, privilege escalation hints, "
        "or unusual session activity.\n"
        "5. Rate the outcome as Normal, Low, Medium, High, or Critical and explain the evidence."
    )


@server.prompt(
    name="DiagnoseSystemHealth",
    title="Diagnose System Health",
    description="Guide the client through a broad Linux health-check using tools, resources, and pagination.",
)
def diagnose_system_health(
    search_text: Annotated[str, Field(description="Text to look for in the main system log. Defaults to error.")] = "error",
) -> str:
    """Guide a broad Linux system health workflow."""
    return (
        "Produce a Linux system health report by combining system, process, and log evidence.\n\n"
        "1. Call `get_system_info` for the machine baseline.\n"
        "2. Call `get_process_list` and use detail lookups for the most relevant PIDs.\n"
        "3. Create a `system` log snapshot filtered to "
        f"`{search_text}` and read it with `read_resource` using pagination when needed.\n"
        "4. Correlate process churn, memory pressure, or restart loops with the log evidence.\n"
        "5. Return an overall health summary, top risks, and the next diagnostic actions."
    )


def main() -> None:
    """Run the MCP server over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
