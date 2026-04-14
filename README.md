# Linux Diagnostics MCP Server - Lecture Demo

A Python/Linux adaptation of the original `MCPDemo` teaching repository. This repo now reaches **Milestone 6 parity** for the public teaching flow: compact system inspection, Linux process drill-down, log snapshots as resources, workflow prompts, authenticated MCP over HTTP on `/mcp`, explicit elicitation before process termination, and sampling-assisted Linux diagnostics.

## What This Demo Shows

This lecture demo now includes:
- ✅ **Tools**: Linux diagnostics tools for `get_system_info`, `get_process_list`, `get_process_by_id`, `get_process_by_name`, and elicitation-gated `kill_process`
- ✅ **Resources**: paged `syslog://snapshot/...` log snapshot resources
- ✅ **Prompts**: MCP workflow prompts for error analysis, CPU investigation, security review, and health diagnosis
- ✅ **HTTP transport**: streamable MCP over `http://127.0.0.1:5000/mcp`
- ✅ **API key auth**: `X-API-Key` header or `?apiKey=secure-mcp-key`
- ✅ **AI Chat Client**: a Python Azure OpenAI client that launches the local HTTP server, lets the model call MCP tools, prompts, and resources, and handles local form elicitation in the terminal
- ✅ **Python 3.12 implementation** with the official MCP Python SDK
- ✅ **Multiple testing methods**
- ✅ **Milestone 5 elicitation** for `kill_process`
- ✅ **Milestone 6 sampling-assisted Linux diagnostics**
- ⏳ **Roots** are planned later

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
6. Exercises the system, process, log snapshot, and sampling-assisted diagnostics flows
7. Verifies `kill_process` fails safely when the client does not advertise elicitation support
8. Verifies the lecture chat client fails safely when Azure OpenAI settings are missing

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
- **`kill_process`** - Terminates a Linux process only after explicit elicitation
  - If `process_id` is omitted, the server samples the top CPU consumers and asks the client to choose one
  - The server always requires the typed confirmation phrase `CONFIRM PID {pid}`
  - The lecture client handles these prompts locally in the terminal when stdin/stdout are interactive
- **`troubleshoot_linux_diagnostics`** - Uses sampling to convert a natural-language Linux diagnostics question into a validated `/proc` or `/sys` read
  - The server validates the sampled path and field against an allowlist before reading anything
  - Exact Python adaptation: the sampled query is a single safe `PATH` or `PATH | grep FIELD` line instead of WQL
  - The server then samples again to summarize the observation back to the user

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
- **`TroubleshootLinuxComponent`** - Focused deep-dive workflow that steers the agent toward `troubleshoot_linux_diagnostics`

## Projects

### `src/mcp_linux_diag_server/server.py`
The authenticated HTTP MCP server exposing the Milestone 1-6 diagnostics tools, log resources, and workflow prompts.

### `src/mcp_linux_diag_server/client.py`
The lecture chat client that:
- launches the local HTTP server
- connects over streamable HTTP with the demo API key
- exposes MCP prompt/resource APIs as helper tools for the model
- fulfills MCP form elicitation in the local terminal when the model triggers `kill_process`
- fulfills MCP sampling requests so the server can synthesize safe Linux diagnostics queries and summaries
- executes tool-calling turns

## Testing Methods

| Method | Visual | Interactive | LLM | Best For |
|--------|--------|-------------|-----|----------|
| `python3 scripts/smoke_test.py` | ❌ No | ❌ No | ❌ No | quick verification of M1-M6 server behavior |
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
✅ **Milestone 5** - Elicitation-backed `kill_process`  
✅ **Milestone 6** - Sampling-assisted Linux diagnostics  
⏳ **Milestone 7** - Roots

## License

MIT. See [LICENSE.txt](LICENSE.txt).

## Resources

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- [Original C# MCPDemo](https://github.com/alonf/MCPDemo)
