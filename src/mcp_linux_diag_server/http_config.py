"""Shared HTTP transport settings for the Milestone 5 demo."""

from __future__ import annotations

DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 5000
DEFAULT_MCP_PATH = "/mcp"
DEMO_API_KEY = "secure-mcp-key"
API_KEY_HEADER = "X-API-Key"
API_KEY_QUERY_PARAMETER = "apiKey"
SESSION_ID_HEADER = "mcp-session-id"


def build_mcp_url(*, host: str = DEFAULT_HTTP_HOST, port: int = DEFAULT_HTTP_PORT, path: str = DEFAULT_MCP_PATH) -> str:
    """Build the local MCP HTTP endpoint URL."""
    return f"http://{host}:{port}{path}"
