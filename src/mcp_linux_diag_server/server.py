"""Milestone 6 MCP server entrypoint."""

import argparse
from typing import Annotated
from urllib.parse import parse_qs

from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field
from starlette.responses import PlainTextResponse
import uvicorn

from mcp_linux_diag_server.http_config import (
    API_KEY_HEADER,
    API_KEY_QUERY_PARAMETER,
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    DEFAULT_MCP_PATH,
    DEMO_API_KEY,
    build_mcp_url,
)
from mcp_linux_diag_server.tools import (
    BasicProcessInfo,
    KillProcessResult,
    LogSnapshotSummary,
    ProcessDetailResult,
    ProcessQueryResult,
    SystemInfoResult,
    collect_system_info,
    create_log_snapshot as collect_log_snapshot,
    get_process_by_id as collect_process_by_id,
    get_processes_by_name as collect_processes_by_name,
    kill_process as perform_kill_process,
    render_log_snapshot_resource,
    list_processes as collect_process_list,
    troubleshoot_linux_diagnostics as run_linux_diagnostics,
)

server = FastMCP(
    name="Linux Diagnostics Demo",
    instructions=(
        "Milestone 6 teaching server. Use tools to collect Linux diagnostics, "
        "read snapshot resources for larger results, discover prompts for guided workflows, "
        "connect over authenticated HTTP transport, require explicit elicitation before risky actions, "
        "and use sampling-assisted Linux diagnostics for deeper /proc and /sys inspection."
    ),
    host=DEFAULT_HTTP_HOST,
    port=DEFAULT_HTTP_PORT,
    streamable_http_path=DEFAULT_MCP_PATH,
)


class ApiKeyMiddleware:
    """Simple demo API key gate for the MCP HTTP endpoint."""

    def __init__(self, app, *, path_prefix: str = DEFAULT_MCP_PATH, expected_api_key: str = DEMO_API_KEY) -> None:  # noqa: ANN001
        self._app = app
        self._path_prefix = path_prefix
        self._expected_api_key = expected_api_key

    async def __call__(self, scope, receive, send) -> None:  # noqa: ANN001
        if scope["type"] != "http" or not scope["path"].startswith(self._path_prefix):
            await self._app(scope, receive, send)
            return

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
        api_key = headers.get(API_KEY_HEADER.lower()) or next(iter(query.get(API_KEY_QUERY_PARAMETER, [])), None)
        if api_key != self._expected_api_key:
            response = PlainTextResponse("Unauthorized", status_code=401)
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)


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
    name="kill_process",
    title="Kill Process",
    description=(
        "Terminate a running Linux process only after explicit elicitation. "
        "When process_id is omitted, the server asks the client to choose from top CPU consumers."
    ),
)
async def kill_process(
    ctx: Context,
    process_id: Annotated[
        int | None,
        Field(description="Optional Linux process ID to terminate. Omit it to choose from the top sampled CPU candidates."),
    ] = None,
    reason: Annotated[
        str | None,
        Field(description="Optional reason to include in the termination result."),
    ] = None,
) -> KillProcessResult:
    """Terminate a process only after explicit user confirmation."""
    return await perform_kill_process(process_id=process_id, reason=reason, ctx=ctx)


@server.tool(
    name="troubleshoot_linux_diagnostics",
    title="Troubleshoot Linux Diagnostics",
    description=(
        "Use client-side sampling to translate a natural-language Linux troubleshooting question into a safe "
        "/proc or /sys query, execute it on the server, and summarize the result."
    ),
)
async def troubleshoot_linux_diagnostics(
    ctx: Context,
    user_request: Annotated[
        str,
        Field(description="Natural-language Linux troubleshooting request, such as 'Show me dirty memory pages'."),
    ],
) -> str:
    """Use sampling plus server validation for deeper Linux diagnostics."""
    return await run_linux_diagnostics(user_request=user_request, ctx=ctx)


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
    name="TroubleshootLinuxComponent",
    title="Troubleshoot Linux Component",
    description="Guide the client toward the sampling-assisted Linux diagnostics workflow for a focused subsystem.",
)
def troubleshoot_linux_component(
    component: Annotated[str, Field(description="Subsystem or concern to inspect, such as dirty memory pages or CPU load.")] = "the user's issue",
) -> str:
    """Guide a focused Milestone 6 troubleshooting workflow."""
    return (
        "You are a Linux internals specialist.\n"
        f"The user wants a deep inspection of: {component}.\n\n"
        "WORKFLOW:\n"
        "1. Do not start with the broad DiagnoseSystemHealth prompt for this focused request.\n"
        "2. Call `troubleshoot_linux_diagnostics` with the user's natural-language request.\n"
        "3. Use the tool's diagnosis as the primary answer because the server validated the sampled query.\n"
        "4. Only fall back to broader process or log tools if the tool reports that the request is outside the allowlisted sources."
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


def create_http_app():
    """Create the authenticated Streamable HTTP MCP app."""  # noqa: ANN202
    return ApiKeyMiddleware(server.streamable_http_app())


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the HTTP MCP server."""
    parser = argparse.ArgumentParser(description="Run the Milestone 6 Linux diagnostics MCP server over HTTP.")
    parser.add_argument("--host", default=DEFAULT_HTTP_HOST, help=f"HTTP host to bind. Defaults to {DEFAULT_HTTP_HOST}.")
    parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT, help=f"HTTP port to bind. Defaults to {DEFAULT_HTTP_PORT}.")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the MCP server over streamable HTTP."""
    args = build_parser().parse_args(argv)
    endpoint = build_mcp_url(host=args.host, port=args.port)
    print("Status: Ready, waiting for MCP client over HTTP (Streamable)")
    print(f"Endpoint: {endpoint}")
    uvicorn.run(
        create_http_app(),
        host=args.host,
        port=args.port,
        log_level=server.settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
