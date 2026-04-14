# Python MCP Elicitation Skill

## Use When

You need a Python MCP server/client pair to support safe server-driven form elicitation, especially for risky actions like process termination.

## Pattern

1. **Server tool**
   - Accept `Context` in the tool signature.
   - Check client capability with `ctx.request_context.session.check_client_capability(...)`.
   - If dynamic form options are needed, call `ctx.request_context.session.elicit_form(...)` with a hand-built restricted JSON schema instead of relying on static Pydantic models.

2. **Selection step**
   - Build a single top-level field with `oneOf` options:
     - `const`: machine-readable value (PID, identifier, etc.)
     - `title`: human-readable label for the client UI
   - Keep the form flat; MCP elicitation schemas are intentionally simple.

3. **Confirmation step**
   - Always require a typed phrase for destructive actions.
   - Validate exact phrase match server-side, but compare case-insensitively for usability.

4. **Lecture/demo client**
   - Pass `elicitation_callback=` to `ClientSession(...)` only when local interaction is actually possible (`stdin/stdout` are TTYs).
   - In the callback, support:
     - single-field `oneOf`/`enum` selection forms
     - single-field text prompts
   - Return `ElicitResult(action="cancel")` on blank input so the server can treat it as a safe cancel.

5. **Linux process termination**
   - Prefer `SIGTERM` first, then `SIGKILL` after a short timeout.
   - Treat zombie processes as exited in `/proc/<pid>/stat` to avoid hanging on child processes owned by another parent.

## Reference Files

- `src/mcp_linux_diag_server/tools/processes.py`
- `src/mcp_linux_diag_server/server.py`
- `src/mcp_linux_diag_server/client.py`
- `tests/test_processes.py`
- `tests/test_m5_http.py`
