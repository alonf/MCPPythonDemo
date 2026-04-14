# Testing Guide

This repo now supports three reliable ways to test the Python Milestone 6 demo:

1. **Automated smoke test script** (fast, repeatable)
2. **Unit tests** (implementation safety)
3. **MCP Inspector / VS Code config** (visual UI for MCP exploration)

## 1) Automated Smoke Test Script ⚡

Fastest way to verify the current demo end-to-end without needing an LLM:

```bash
python3 scripts/smoke_test.py
```

This script:
1. Starts the HTTP MCP server
2. Verifies `401 Unauthorized` when the API key is omitted
3. Performs the MCP initialize handshake on `/mcp`
4. Confirms `mcp-session-id` is returned and reused
5. Discovers tools, prompts, and resource templates
6. Exercises `get_system_info`, process tools, log snapshots, and sampling-assisted diagnostics
7. Confirms `kill_process` fails safely when elicitation is unavailable
8. Confirms the lecture client fails safely when Azure OpenAI settings are not configured

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
- HTTP smoke coverage for the M1-M6 server surface
- raw HTTP auth/session regression coverage

## 3) MCP Inspector / VS Code MCP Config 🔍

### Launch the server

```bash
python3 -m mcp_linux_diag_server
```

### Connect using HTTP

- endpoint: `http://127.0.0.1:5000/mcp`
- header: `X-API-Key: secure-mcp-key`
- alternate URL form: `http://127.0.0.1:5000/mcp?apiKey=secure-mcp-key`

The repo includes `.vscode/mcp.json` with the required header already filled in.

### In the browser or client

1. Click **Connect**
2. Open the **Tools** tab
3. Select **get_system_info**, **kill_process**, or another milestone tool
4. Click **Call Tool**

The **Logs** tab is useful for inspecting HTTP JSON-RPC traffic.

## Comparison

| Method | Setup | Visual UI | Real-time | LLM Required | Best For |
|--------|-------|-----------|-----------|--------------|----------|
| `scripts/smoke_test.py` | ⭐ Easy | ❌ No | ❌ No | ❌ No | fast verification |
| `unittest discover` | ⭐ Easy | ❌ No | ❌ No | ❌ No | regression safety |
| Inspector / `.vscode/mcp.json` | ⭐⭐ Medium | ✅ Yes | ✅ Yes | ❌ No | teaching and debugging |

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

### Inspector Cannot Connect

- Verify the server is already running on port 5000
- Verify the API key is present as `X-API-Key: secure-mcp-key`
- Use an elicitation-capable client if you want to exercise `kill_process`
- Re-run `python3 scripts/smoke_test.py`

### Lecture Chat Client Exits Immediately

That is expected when Azure OpenAI settings are missing. Configure `.env.local` from `.env.example`, or export the equivalent shell variables first.

## Resources

- [README.md](../README.md)
- [MCPDemoRoadmap.md](./MCPDemoRoadmap.md)
- [Model Context Protocol](https://modelcontextprotocol.io/)
