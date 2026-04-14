# Ash: Milestone 7 Python implementation

- **Date:** 2026-04-14
- **Scope:** Milestone 7 roots, proc/sys snapshots, prompt/client wiring

## Decision

Implement Milestone 7 as a separate proc/sys snapshot subsystem instead of modifying the Milestone 6 sampling validator.

## Why

- Keeps M5/M6 behavior unchanged while still adding the C#-style roots/sandbox pattern.
- Reuses the proven snapshot/resource UX from log snapshots with a domain-specific adaptation:
  - file snapshots page line-by-line
  - directory snapshots page deterministic child metadata
- Centralizes allowed-root enforcement, traversal rejection, and symlink-escape rejection in one place before any proc/sys read occurs.

## Key Files

- `src/mcp_linux_diag_server/tools/proc_snapshots.py`
- `src/mcp_linux_diag_server/server.py`
- `src/mcp_linux_diag_server/client.py`
- `scripts/smoke_test.py`
- `tests/test_proc_snapshots.py`
- `tests/test_m7_http.py`
