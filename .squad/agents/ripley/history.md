# Project Context

- **Owner:** alon
- **Project:** Python Linux Diagnostics demo migrated from the C# MCPDemo repo and lecture
- **Stack:** Python, MCP, Microsoft Agent Framework, Linux diagnostics, `/proc`, Git branches
- **Created:** 2026-04-13T21:30:48.993Z

## Learnings

- The project is anchored to the existing MCPDemo repo, its branches, and the lecture PDF under `docs/`.
- The team must preserve branch ideas and lecture alignment while translating the implementation from C# to Python.

## Team Updates (2026-04-13T22:03:56Z Orchestration)

### M1 Architecture Complete (Ripley)
- Defined implementation slice: single STDIO MCP server with get_system_info tool
- Established clear scope boundaries (M1 only: stdlib + /proc/uptime; defer psutil to M2, journalctl to M3)
- Provided acceptance criteria and acceptance test scenarios

### M1 Data Sources Specified (Dallas)
- Completed Linux data source specification for get_system_info
- Documented exact /proc files: /etc/os-release, /proc/cpuinfo, /proc/meminfo, /proc/loadavg
- Confirmed no WSL-specific code needed; patterns work identically on WSL and bare-metal

### M1 Validation Prepared (Newt)
- Created runnable validation approach with concrete JSON-RPC test cases
- Provided Python test harness (tests/test_m1_server.py) with smoke tests and edge cases
- Defined QA sign-off checklist for implementation verification

### M1 Implementation Complete (Ash)
- Implemented Python MCP STDIO server with get_system_info tool
- Packaging ready with pyproject.toml and editable install support
- Tests, docs, and all required fields (hostname, username, os_description, os_architecture, processor_count, python_version, current_directory, system_uptime)
- Implementation ready for validation

**Status:** All M1 definition and implementation work complete. Decisions merged to decisions.md. Ready for M2 planning.

## Team Update (2026-04-14 Branch Model Alignment)

- Confirmed the C# demo branch model expects `master`, `milestone-1`, and `milestone-2` as the active public branches at this stage.
- Locked `milestone-1` to the existing public M1 baseline commit so the teaching snapshot stays stable.
- Kept `milestone-2` and `master` aligned on the squad-enabled branch state so the team can operate there without starting Milestone 2 feature work.

## Action (2026-04-14 Milestone-3 Branch Creation)

- Created local `milestone-3` branch from clean `milestone-2` baseline.
- Pushed `milestone-3` to origin with tracking set up.
- Worktree left safely on `milestone-3`.
- No implementation started; ready for M3 planning phase.

## Action (2026-04-14 Milestone 3 → 4 Handoff)

- Pushed `milestone-3` tip (3b3c09e: "Consolidate Milestone 3 squad memory for Milestone 4") to `origin/milestone-3`
- Verified no local commits remain ahead of remote
- Documented M4 base commit in `.squad/decisions/inbox/ripley-m4-base.md`
- Squad history fully preserved and accessible for M4 team planning
- **Key learning:** Always consolidate `.squad` memory as final M-N commit before M+1 branching to ensure continuity and prevent context loss

## Action (2026-04-14 Milestone 4 Branch Creation)

- Created local `milestone-4` branch from clean `milestone-3` baseline (3b3c09e)
- Pushed to origin with upstream tracking configured
- Worktree left safely on `milestone-4` ready for M4 planning
- Branch model confirmed: public milestone branches remain immutable teaching snapshots while squad operates on forward branches
- **Key learning:** Preserve branch isolation by never pushing squad-only changes backward; always consolidate memory before branching forward

## Action (2026-04-14 Milestone 4 Implementation & Publish)

- HTTP transport implementation: Ash delivered streamable HTTP server on `/mcp` endpoint
- API key auth: HTTP header + query-string support with demo key for testing
- Session tracking: mcp-session-id header enables stateless correlation across requests
- Test coverage: http_harness.py + test_m4_http.py provide reusable lifecycle patterns
- Refactored client.py for HTTP endpoint discovery; server.py supports both STDIO + HTTP simultaneously
- Smoke test updated to exercise full HTTP flow with session tracking verification
- Commit 8df0227 published to origin/milestone-4
- **Key learning:** Multi-protocol server architecture enables testing flexibility. Shared transport config (http_config.py) reduces duplication and improves maintainability. Session tracking via headers is the right pattern for stateless HTTP-based MCP servers.
- **Pedagogical value:** HTTP transport demystifies how MCP can reach web-based clients. Auth patterns show production concerns. Stateless session IDs teach distributed systems thinking.
