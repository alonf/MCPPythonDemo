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
