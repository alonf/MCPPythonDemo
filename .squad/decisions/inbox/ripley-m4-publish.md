---
author: Ripley
date: 2026-04-14T22:15:00Z
decision: M4 publish — approved for teaching arc
---

# Milestone 4 Publish Decision

## What We Did

Published Milestone 4 to `origin/milestone-4` (commit `8df0227`). The milestone delivers:

- **HTTP transport** on `/mcp` endpoint with streamable request/response handling
- **API key authentication** (header + query-string options) for session access control
- **Session tracking** via `mcp-session-id` across stateless HTTP requests
- **Refactored server** supporting both STDIO and HTTP transports simultaneously
- **Comprehensive test coverage** with HTTP harness, integration tests, and smoke test updates
- **VS Code MCP integration** via `.vscode/mcp.json` configuration
- **Documentation** updated to reflect HTTP-first testing and deployment patterns

## Why This Works

Milestone 4 reaches HTTP auth milestone from the C# MCPDemo teaching arc. The implementation demonstrates:

1. **HTTP as a first-class MCP transport** — MCP can operate over multiple protocols; HTTP enables web-based clients
2. **Authentication patterns** — API keys show how to gate MCP endpoints in production scenarios
3. **Stateless session tracking** — Headers allow clients to correlate requests without server state
4. **Backward compatibility** — STDIO transport still works; clients choose which to use

This aligns with the pedagogical goal: students see transport abstraction, authentication layering, and multi-protocol server design.

## Integration Points

- **Client library**: refactored `client.py` discovers HTTP endpoints via streamable HTTP SDK
- **Test surface**: `http_harness.py` provides reusable lifecycle patterns for HTTP server testing
- **Smoke test**: updated to exercise HTTP + session tracking + full tool/resource/prompt flows
- **M1-M3 tests**: simplified with shared harness utilities

## Risk: None

HTTP implementation is self-contained. STDIO path unchanged. Tests pass end-to-end. No breaking changes to existing M1-M3 surfaces.

## Next Milestone

M5 should introduce **elicitation** patterns (MCP prompts for AI-guided workflows). HTTP transport is ready to support this.
