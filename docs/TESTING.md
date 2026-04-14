# Testing Guide

This repo currently supports three reliable ways to test the Python Milestone 1 demo:

1. **Automated smoke test script** (fast, repeatable)
2. **Unit tests** (implementation safety)
3. **MCP Inspector** (visual UI for MCP exploration)

## 1) Automated Smoke Test Script ⚡

Fastest way to verify the current demo end-to-end without needing an LLM:

```bash
python3 scripts/smoke_test.py
```

This script:
1. Starts the stdio MCP server
2. Performs the MCP initialize handshake
3. Discovers tools
4. Executes `get_system_info`
5. Confirms the lecture client fails safely when Azure OpenAI settings are not configured

Use this for quick verification before publishing changes.

## 2) Unit Tests ✅

Run the unit and integration-style tests:

```bash
python3 -m unittest discover -s tests -q
```

This covers:
- system info collection
- MCP tool schema translation for Azure OpenAI
- local `.env.local` file loading behavior
- lecture client configuration failures
- the Milestone 1 server smoke path

## 3) MCP Inspector (Visual) 🔍

Inspector is the best way to explore the Milestone 1 MCP surface visually.

### Launch

```bash
export PATH="$HOME/.local/bin:$PATH"
mcp dev src/mcp_linux_diag_server/server.py:server --with-editable .
```

### In the browser

1. Click **Connect**
2. Open the **Tools** tab
3. Select **get_system_info**
4. Click **Call Tool**

The **Logs** tab is useful for inspecting raw JSON-RPC traffic.

## Comparison

| Method | Setup | Visual UI | Real-time | LLM Required | Best For |
|--------|-------|-----------|-----------|--------------|----------|
| `scripts/smoke_test.py` | ⭐ Easy | ❌ No | ❌ No | ❌ No | fast verification |
| `unittest discover` | ⭐ Easy | ❌ No | ❌ No | ❌ No | regression safety |
| MCP Inspector | ⭐⭐ Medium | ✅ Yes | ✅ Yes | ❌ No | teaching and debugging |

## Example Output

`get_system_info` returns a payload shaped like:

```json
{
  "machine_name": "demo-host",
  "user_name": "demo-user",
  "os_description": "Ubuntu 24.04 LTS",
  "kernel_release": "6.x.x",
  "architecture": "x86_64",
  "processor_count": 8,
  "python_runtime": "3.12.3",
  "current_directory": "/path/to/repo",
  "uptime_seconds": 12345.67,
  "uptime_human": "3h 25m 45s",
  "load_average": {
    "one_minute": 0.42,
    "five_minutes": 0.38,
    "fifteen_minutes": 0.31
  },
  "memory": {
    "total_bytes": 17179869184,
    "available_bytes": 8589934592,
    "used_bytes": 8589934592
  },
  "wsl_detected": false
}
```

## Troubleshooting

### Server Won't Start

```bash
python3 -m mcp_linux_diag_server
```

If that fails, make sure the package is installed in editable mode and that Python 3.12+ is available.

### Tool Not Showing Up in Inspector

- Reinstall the package: `python3 -m pip install --user --break-system-packages -e .`
- Re-run `python3 scripts/smoke_test.py`
- Reconnect in Inspector and inspect the **Logs** tab

### Lecture Chat Client Exits Immediately

That is expected when Azure OpenAI settings are missing. Configure `.env.local` from `.env.example`, or export the equivalent shell variables first.

## Resources

- [README.md](../README.md)
- [MCPDemoRoadmap.md](./MCPDemoRoadmap.md)
- [Model Context Protocol](https://modelcontextprotocol.io/)
