# M1 Parity Validation Guide

## What gets validated

### 1) MCP server path

The Python repo should mirror the C# lecture flow for Milestone 1:

1. Start a local stdio MCP server
2. Complete `initialize`
3. Discover `get_system_info`
4. Execute `get_system_info`
5. Reject an invalid tool name without crashing

### 2) LLM-backed client path

The Python client should:

1. Start the same local stdio MCP server
2. Fetch `get_system_info`
3. Build an LLM prompt from that payload
4. Fail fast with a clear message if Azure OpenAI configuration is missing

## Automated checks

Run all tests:

```bash
cd /home/alon/MCPPythonDemo
python3 -m unittest discover -s tests -v
```

Key coverage:

- `tests/test_m1_smoke.py` - stdio MCP handshake, tool discovery, happy path, extra args, invalid tool
- `tests/test_system_info.py` - graceful fallback when `/proc` files are missing
- `tests/test_client.py` - client prompt building, fake-LLM agent loop, missing-config CLI failure

## Smoke checks

Server + agent smoke:

```bash
python3 scripts/smoke_test.py
```

Expected behavior:

- Server portion prints discovered tools and a live `get_system_info` payload
- Agent portion verifies that the client exits with code `2` and emits a human-readable Azure config message when credentials are absent

## Required Azure env vars for the agent path

Either prefix style is accepted:

```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_DEPLOYMENT="model-router"
```

or:

```bash
export MCP_DEMO_AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export MCP_DEMO_AZURE_OPENAI_API_KEY="your-api-key"
export MCP_DEMO_AZURE_OPENAI_DEPLOYMENT="model-router"
```

Optional:

```bash
export AZURE_OPENAI_API_VERSION="2024-10-21"
```
