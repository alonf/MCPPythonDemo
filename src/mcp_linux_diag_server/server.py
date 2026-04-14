"""Milestone 1 MCP server entrypoint."""

from mcp.server.fastmcp import FastMCP

from mcp_linux_diag_server.tools.system_info import SystemInfoResult, collect_system_info

server = FastMCP(
    name="Linux Diagnostics Demo",
    instructions=(
        "Milestone 1 teaching server. Exposes one read-only Linux diagnostics tool "
        "over stdio and keeps the rest of the MCP surface for later milestones."
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


def main() -> None:
    """Run the MCP server over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
