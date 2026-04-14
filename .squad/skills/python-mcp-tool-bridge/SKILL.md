# Python MCP Tool Bridge Skill

## Use When

You need a Python lecture/demo client that lets an LLM call MCP tools without waiting for server-side sampling support.

## Pattern

1. Start the MCP server locally with `StdioServerParameters(command=sys.executable, args=["-m", server_module])`.
2. Connect with `stdio_client(...)` + `ClientSession`, then `initialize()` and `list_tools()`.
3. Convert each MCP `Tool` into an OpenAI function tool by reusing `name`, `description`, and `inputSchema`.
4. Run a chat-completions loop:
   - send system + user messages plus tool schema
   - if the model returns tool calls, execute them through `session.call_tool(...)`
   - feed serialized tool results back as `role="tool"`
   - stop when the model returns plain assistant text
5. Keep config explicit via env vars for endpoint, API key, deployment, and API version.

## Runtime Shape Check

- Before adding Azure AI Foundry project/runtime abstractions, inspect the live reference client code that actually runs the lecture flow.
- If that runnable path uses `AzureOpenAIClient(endpoint, credential).GetChatClient(deploymentName)` or the equivalent endpoint + deployment + credential shape, keep the Python bridge on the simpler Azure OpenAI runtime path.
- Only switch the Python client to a Foundry project client when the reference app itself is using a project endpoint/client in its active runnable path.

## Testing Pattern

- For live validation in WSL, first verify `az account show` succeeds, then run `python3 -m mcp_linux_diag_server.client --json --prompt "..."`; the `[tool] ...` trace plus final JSON answer is the fastest proof that Azure OpenAI and the MCP bridge both worked.
- Unit-test config parsing independently.
- Unit-test MCP-tool → OpenAI-tool translation as a pure function.
- Unit-test the agent loop with a fake model and fake MCP session so no external credentials are required.
- Keep smoke tests focused on server startup plus client configuration guardrails.

## Reference Files

- `src/mcp_linux_diag_server/client.py`
- `tests/test_client.py`
- `scripts/smoke_test.py`
