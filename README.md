# Linux Diagnostics MCP Server - Lecture Demo

A Python/Linux adaptation of the original `MCPDemo` teaching repository. This repo mirrors the C# demo's public structure and documentation style while staying truthful about current scope: **Milestone 1 parity only** today.

## What This Demo Shows

This is an early **MCP lecture demo** with:
- ✅ **Tools**: one read-only Linux diagnostics tool, `get_system_info`
- ✅ **AI Chat Client**: a Python Azure OpenAI client that launches the local stdio server and lets the model call MCP tools
- ✅ **STDIO transport**
- ✅ **Python 3.12 implementation** with the official MCP Python SDK
- ✅ **Multiple testing methods**
- ⏳ **Resources, prompts, HTTP transport, elicitation, sampling, and roots** are planned later and are **not implemented yet**

Perfect for learning the MCP basics before expanding into the later milestones from the original C# arc.

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
1. Starts the local stdio MCP server
2. Performs the MCP handshake
3. Discovers tools
4. Executes `get_system_info`
5. Verifies the lecture chat client fails safely when Azure OpenAI settings are missing

### 3. Test with MCP Inspector

```bash
export PATH="$HOME/.local/bin:$PATH"
mcp dev src/mcp_linux_diag_server/server.py:server --with-editable .
```

Then in Inspector:
1. Connect to the server
2. Open the **Tools** tab
3. Select **get_system_info**
4. Call the tool and inspect the JSON response

### 4. Use the Lecture Chat Client

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

## The Tool

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

## Projects

### `src/mcp_linux_diag_server/server.py`
The stdio MCP server exposing the Milestone 1 `get_system_info` tool.

### `src/mcp_linux_diag_server/client.py`
The lecture chat client that:
- launches the local stdio server
- lists MCP tools
- translates MCP tool schemas to Azure OpenAI tool definitions
- executes tool-calling turns

## Testing Methods

| Method | Visual | Interactive | LLM | Best For |
|--------|--------|-------------|-----|----------|
| `python3 scripts/smoke_test.py` | ❌ No | ❌ No | ❌ No | quick verification |
| MCP Inspector | ✅ Yes | ✅ Yes | ❌ No | development, debugging, teaching |
| `python3 -m mcp_linux_diag_server.client` | ❌ No | ✅ Yes | ✅ Yes | lecture demo flow |

## Project Structure

```text
MCPPythonDemo/
├── README.md
├── LICENSE
├── pyproject.toml
├── .env.example
├── scripts/
│   └── smoke_test.py
├── src/
│   └── mcp_linux_diag_server/
│       ├── __main__.py
│       ├── client.py
│       ├── server.py
│       └── tools/
│           └── system_info.py
├── tests/
│   ├── test_client.py
│   ├── test_m1_smoke.py
│   └── test_system_info.py
```

## Requirements

- Python 3.12+
- `mcp[cli]`
- Azure OpenAI only if you want to run the lecture chat client

## Milestones

✅ **Milestone 1** - Minimal diagnostics tool over stdio plus lecture chat client  
⏳ **Milestone 2** - Process inspection  
⏳ **Milestone 3** - Resources and prompts  
⏳ **Milestone 4** - HTTP transport and security  
⏳ **Milestone 5+** - Elicitation, sampling, and roots

This repo does **not** claim feature parity with the later C# milestones yet.

## License

MIT. See [LICENSE](LICENSE).

## Resources

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP Inspector](https://github.com/modelcontextprotocol/inspector)
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- [Original C# MCPDemo](https://github.com/alonf/MCPDemo)
