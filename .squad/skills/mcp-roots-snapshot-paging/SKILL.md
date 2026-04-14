# MCP Roots + Snapshot Paging Skill

## Use When

You need to add a safe sandboxed read surface to an MCP server without breaking older tools.

## Pattern

1. Keep the new sandbox feature additive:
   - preserve older tools unchanged
   - add a dedicated `request_*_access` tool plus a dedicated snapshot tool
2. Put all normalization and authorization in one validator:
   - absolute-path requirement
   - traversal rejection
   - supported-root restriction
   - symlink-escape rejection
   - allowed-root match before reading
3. Reuse the existing snapshot/resource UX:
   - tool returns `{resource_uri, paginated_resource_template}`
   - resource returns metadata + entries + pagination
4. Page different source kinds with the same envelope:
   - file snapshots → line entries
   - directory snapshots → deterministic child metadata entries
5. Tell the model the order explicitly:
   - `request_*_access` first for blocked paths
   - `create_*_snapshot` second
   - `read_resource` third
6. Be defensive with MCP resource query handling:
   - register the paged template
   - also parse `?limit=...&offset=...` if it leaks through the base `{id}` route

## Reference Files

- `src/mcp_linux_diag_server/tools/proc_snapshots.py`
- `src/mcp_linux_diag_server/server.py`
- `src/mcp_linux_diag_server/client.py`
- `tests/test_proc_snapshots.py`
- `tests/test_m7_http.py`
