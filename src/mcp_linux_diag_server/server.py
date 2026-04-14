"""Milestone 2 MCP server entrypoint."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from mcp_linux_diag_server.tools import (
    BasicProcessInfo,
    ProcessDetailResult,
    ProcessQueryResult,
    SystemInfoResult,
    collect_system_info,
    get_process_by_id as collect_process_by_id,
    get_processes_by_name as collect_processes_by_name,
    list_processes as collect_process_list,
)

server = FastMCP(
    name="Linux Diagnostics Demo",
    instructions=(
        "Milestone 2 teaching server. Start with compact system or process summaries, "
        "then drill into one Linux process with the detail tools."
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


def main() -> None:
    """Run the MCP server over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
