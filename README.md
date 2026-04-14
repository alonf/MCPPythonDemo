# Linux Diagnostics MCP Server - Lecture Demo

A Python/Linux adaptation of the original `MCPDemo` teaching repository. This repo now reaches **Milestone 4 parity** for the public teaching flow: compact system inspection, Linux process drill-down, log snapshots as resources, workflow prompts, and authenticated MCP over HTTP on `/mcp`.

## What This Demo Shows

This lecture demo now includes:
- ✅ **Tools**: read-only Linux diagnostics tools for `get_system_info`, `get_process_list`, `get_process_by_id`, and `get_process_by_name`
- ✅ **Resources**: paged `syslog://snapshot/...` log snapshot resources
- ✅ **Prompts**: MCP workflow prompts for error analysis, CPU investigation, security review, and health diagnosis
- ✅ **HTTP transport**: streamable MCP over `http://127.0.0.1:5000/mcp`
- ✅ **API key auth**: `X-API-Key` header or `?apiKey=secure-mcp-key`
- ✅ **AI Chat Client**: a Python Azure OpenAI client that launches the local HTTP server and lets the model call MCP tools, prompts, and resources
- ✅ **Python 3.12 implementation** with the official MCP Python SDK
- ✅ **Multiple testing methods**
- ⏳ **Elicitation, sampling, and roots** are planned later

## Quick Start

### 1. Install

Server-only install:

```bash
python3 -m pip install --user --break-system-packages -e .
```

Install the lecture chat client extras:

```bash
python3 -m pip install --user --break-system-packages -e '.[llm]'
```

### 2. Quick Smoke Test (No LLM)

```bash
python3 scripts/smoke_test.py
```

This script:
1. Starts the local HTTP MCP server
2. Verifies `401 Unauthorized` without an API key
3. Performs the MCP initialize handshake on `/mcp`
4. Confirms `mcp-session-id` flow works across requests
5. Discovers tools, prompts, and resource templates
6. Exercises the system, process, and log snapshot flows
7. Verifies the lecture chat client fails safely when Azure OpenAI settings are missing

### 3. Run the Server Manually

```bash
python3 -m mcp_linux_diag_server
```

The server listens on:

- endpoint: `http://127.0.0.1:5000/mcp`
- demo API key: `secure-mcp-key`

### 4. Test with MCP Inspector or VS Code MCP config

Start the server in one terminal, then connect using the HTTP endpoint above.

This repo includes `.vscode/mcp.json` with the required header:

```json
{
  "servers": {
    "linux-diag-demo": {
      "url": "http://127.0.0.1:5000/mcp",
      "headers": {
        "X-API-Key": "secure-mcp-key"
      }
    }
  }
}
```

If your inspector accepts a URL directly, this query-string form also works:

```text
http://127.0.0.1:5000/mcp?apiKey=secure-mcp-key
```

### 5. Use the Lecture Chat Client

Copy the sample environment file and fill in your local Azure OpenAI settings:

```bash
cp .env.example .env.local
$EDITOR .env.local
python3 -m mcp_linux_diag_server.client --prompt "Summarize this machine."
```

To mirror the original .NET credential flow more closely, set:

```bash
MCP_DEMO_AZURE_OPENAI_USE_DEFAULT_CREDENTIAL=true
```

and omit the API key.

Run interactive chat:

```bash
python3 -m mcp_linux_diag_server.client
```

Or run a single prompt:

```bash
python3 -m mcp_linux_diag_server.client --prompt "What is the system information?"
```

## The Tools

### System Information
- **`get_system_info`** - Returns a compact Linux or WSL system snapshot
  - Host name
  - Current user
  - Linux distribution description
  - Kernel release
  - Architecture
  - Logical CPU count
  - Python runtime
  - Current working directory
  - Uptime
  - Load averages
  - Memory summary
  - WSL detection flag

### Process Inspection
- **`get_process_list`** - Returns a lightweight list of running processes with names and PIDs
- **`get_process_by_id`** - Returns detailed Linux process information for one PID
- **`get_process_by_name`** - Returns paged detailed process information for a process name
  - Defaults to `page_number=1`
  - Defaults to `page_size=5`
  - Keeps the list-first, detail-second teaching flow from the original demo

### Log Snapshots
- **`create_log_snapshot`** - Creates an immutable snapshot from a common Linux log file and returns resource URIs
  - Supports `system`, `security`, `kernel`, and `package` log groups
  - Optional `filter_text` narrows the snapshot to matching lines
  - Returns a base resource URI plus a paginated resource template

## Resources

- **`syslog://snapshot/{snapshot_id}`** - Reads a stored Linux log snapshot with default pagination
- **`syslog://snapshot/{snapshot_id}?limit={limit}&offset={offset}`** - Reads a specific page from a stored snapshot

Every resource read returns:
- snapshot metadata
- captured lines
- pagination metadata (`total_count`, `returned_count`, `limit`, `offset`, `has_more`, `next_offset`)

## Prompts

- **`AnalyzeRecentApplicationErrors`** - Error-focused log analysis workflow
- **`ExplainHighCpu`** - Correlate CPU-heavy processes with Linux logs
- **`DetectSecurityAnomalies`** - Review suspicious processes plus auth/security log evidence
- **`DiagnoseSystemHealth`** - End-to-end system health workflow

## Projects

### `src/mcp_linux_diag_server/server.py`
The authenticated HTTP MCP server exposing the Milestone 1-4 diagnostics tools, log resources, and workflow prompts.

### `src/mcp_linux_diag_server/client.py`
The lecture chat client that:
- launches the local HTTP server
- connects over streamable HTTP with the demo API key
- exposes MCP prompt/resource APIs as helper tools for the model
- executes tool-calling turns

## Testing Methods

| Method | Visual | Interactive | LLM | Best For |
|--------|--------|-------------|-----|----------|
| `python3 scripts/smoke_test.py` | ❌ No | ❌ No | ❌ No | quick verification of M1-M4 server behavior |
| MCP Inspector / `.vscode/mcp.json` | ✅ Yes | ✅ Yes | ❌ No | development, debugging, teaching |
| `python3 -m mcp_linux_diag_server.client` | ❌ No | ✅ Yes | ✅ Yes | lecture demo flow |

For the Milestone 1 validation checklist that still underpins the base lecture flow, see [M1_VALIDATION_GUIDE.md](M1_VALIDATION_GUIDE.md).

## Project Structure

```text
MCPPythonDemo/
├── README.md
├── LICENSE.txt
├── pyproject.toml
├── .env.example
├── .vscode/
│   └── mcp.json
├── scripts/
│   └── smoke_test.py
├── src/
│   └── mcp_linux_diag_server/
│       ├── __main__.py
│       ├── client.py
│       ├── http_config.py
│       ├── server.py
│       └── tools/
│           ├── log_snapshots.py
│           ├── processes.py
│           └── system_info.py
├── tests/
│   ├── http_harness.py
│   ├── test_client.py
│   ├── test_m1_smoke.py
│   ├── test_m2_smoke.py
│   ├── test_m3_smoke.py
│   ├── test_m4_http.py
│   ├── test_log_snapshots.py
│   ├── test_processes.py
│   └── test_system_info.py
```

## Requirements

- Python 3.12+
- `mcp[cli]`
- Azure OpenAI only if you want to run the lecture chat client

## Milestones

✅ **Milestone 1** - Minimal diagnostics tool over stdio plus lecture chat client  
✅ **Milestone 2** - Process inspection  
✅ **Milestone 3** - Log snapshot resources and prompts  
✅ **Milestone 4** - HTTP transport and security  
⏳ **Milestone 5+** - Elicitation, sampling, and roots

## License

MIT. See [LICENSE.txt](LICENSE.txt).

## Resources

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- [Original C# MCPDemo](https://github.com/alonf/MCPDemo)
