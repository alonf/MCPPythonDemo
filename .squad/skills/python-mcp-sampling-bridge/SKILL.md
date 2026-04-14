# Python MCP Sampling Bridge

## Use When

- A Python MCP server needs `sampling/createMessage` parity with another implementation
- The client should own the LLM runtime while the server orchestrates sampling

## Pattern

1. On the server, call `ctx.session.create_message(...)`.
2. On the client, pass an async `sampling_callback` into `ClientSession(...)`; this automatically advertises sampling capability.
3. Keep the callback thin: translate MCP messages to your model input, call the model, return `CreateMessageResult`.
4. Treat sampled output as untrusted input. Validate it on the server, retry with validation errors when needed, and only then execute deterministic work.
5. For Linux diagnostics teaching flows, a constrained `PATH` or `PATH | grep FIELD` format is easier to validate than free-form shell commands.

## Repo Example

- `src/mcp_linux_diag_server/tools/m6_diagnostics.py`
- `src/mcp_linux_diag_server/client.py`
- `tests/test_linux_diagnostics.py`
