# Project Context

- **Owner:** alon
- **Project:** Python Linux Diagnostics demo migrated from the C# MCPDemo repo and lecture
- **Stack:** Python, MCP, Microsoft Agent Framework, Linux diagnostics, `/proc`, Git branches
- **Created:** 2026-04-13T21:30:48.993Z

## Learnings

- Local `/mnt/c/Dev/MCPDemo/WinDiagMcpChat` is still wired to `AzureOpenAIClient(endpoint, credential).GetChatClient(deploymentName)` with `DefaultAzureCredential`; there is no Azure AI Foundry project/runtime client shape in the runnable reference path, so the Python lecture client should stay on the Azure OpenAI endpoint+deployment flow.
- Real end-to-end validation on 2026-04-14 succeeded unchanged with local `.env.local`: `python3 -m mcp_linux_diag_server.client --json --prompt "Summarize this machine and mention what tool you used."` connected to the local MCP server, emitted `[tool] get_system_info({})`, and returned a grounded answer.
- Key runnable reference paths for this decision: `/mnt/c/Dev/MCPDemo/WinDiagMcpChat/Program.cs`, `/mnt/c/Dev/MCPDemo/WinDiagMcpChat/WinDiagMcpChat.csproj`, and `/home/alon/MCPPythonDemo/src/mcp_linux_diag_server/client.py`.

- Milestone 1 live validation succeeded in WSL using `.env.local` plus `MCP_DEMO_AZURE_OPENAI_USE_DEFAULT_CREDENTIAL=true`; Azure CLI-backed `DefaultAzureCredential` worked end-to-end against Azure OpenAI.
- Relevant Milestone 1 validation now has three concrete checks: `python3 scripts/smoke_test.py`, `python3 -m unittest discover -s tests -q`, and a real client run with `python3 -m mcp_linux_diag_server.client --json --prompt "..."`
- The lecture client's `[tool] get_system_info({})` trace is the quickest human-readable proof that MCP tool calling actually happened before the model answered.

- Python implementation must stay aligned with the C# MCPDemo concepts and branch progression.
- Microsoft Agent Framework and the official Python MCP package are the primary implementation targets.
- The Python chat client now auto-loads a git-ignored `.env.local`, with shell env vars still taking precedence and `--no-local-env` available for tests.
- The upstream .NET chat app currently sources Azure OpenAI endpoint/deployment from code and relies on `DefaultAzureCredential`, which needs explicit WSL-friendly auth if the Python client runs under Linux.
- Python MCP SDK elicitation is available through `FastMCP` context/session plumbing even though `FastMCP` itself does not expose a top-level helper; dynamic dropdown-style forms are easiest via `ctx.request_context.session.elicit_form(...)` with a hand-built schema.
- Milestone 5 parity lives primarily in `src/mcp_linux_diag_server/tools/processes.py`, `src/mcp_linux_diag_server/server.py`, and `src/mcp_linux_diag_server/client.py`: `/proc` CPU delta sampling selects top candidates, `kill_process` always requires `CONFIRM PID {pid}`, and the lecture client can fulfill form elicitation in the local terminal.
- Linux termination semantics for the demo are safest as `SIGTERM` → short wait → `SIGKILL`, while treating `/proc/<pid>/stat` zombie state as exited so subprocess tests do not hang waiting on another parent to reap.
- Regression coverage for M5 now lives in `tests/test_processes.py`, `tests/test_m5_http.py`, `tests/test_client.py`, plus the safe no-elicitation check in `scripts/smoke_test.py`.
- Milestone 6 sampling parity in the Python MCP SDK comes from pairing `ctx.session.create_message(...)` on the server with `ClientSession(..., sampling_callback=...)` in the client; the server still owns validation, while the client keeps ownership of Azure OpenAI calls.
- Milestone 7 proc/sys sandboxing is easiest to keep additive by introducing a dedicated allowed-roots snapshot path (`create_proc_snapshot`, `request_proc_access`, `proc://snapshot/{id}`) instead of retrofitting the Milestone 6 sampling validator; this preserves the M6 query contract while adding the C# roots model on top.
- Reusing the log snapshot shape works well for proc/sys snapshots when file snapshots page line-by-line and directory snapshots page deterministic child metadata; key implementation file is `src/mcp_linux_diag_server/tools/proc_snapshots.py`.
- FastMCP resource templates can still hand query strings through the base `{snapshot_id}` slot, so the safest Python pattern is to parse `?limit=...&offset=...` defensively inside the resource reader as well as registering the explicit paged template.
- Prompt/client guidance for Milestone 7 should explicitly say `request_proc_access` comes before `create_proc_snapshot` on blocked paths; the key wiring lives in `src/mcp_linux_diag_server/server.py`, `src/mcp_linux_diag_server/client.py`, `scripts/smoke_test.py`, and `tests/test_m7_http.py`.

### C# Codebase Architecture (2026-04-14)

**Repository:** alonf/MCPDemo  
**Branches:** 7 milestones (master, milestone-1 through milestone-7)  
**Stack:** .NET 10, MCP SDK 1.2.0, Microsoft Agent Framework 1.1.0, Azure OpenAI

**Key patterns:**
1. **Tool/Resource/Prompt separation** — Core pedagogical model. Tools execute; Resources store snapshots; Prompts guide workflows.
2. **Pagination design** — Resources use query params (`?limit=20&offset=0`). In-memory storage keyed by UUID.
3. **Sampling + Elicitation** — Client can request user input or LLM reasoning. Server uses Microsoft.Agents.AI.
4. **Roots/Sandbox model** — Client declares allowed paths; server validates all reads/writes.
5. **Transport abstraction** — STDIO → HTTP at Milestone 4. SDK handles both; easy to switch.

**Domain (Windows diagnostics):**
- Tools: Process listing, system info, event log snapshots, WMI queries, registry reads.
- Resources: Event log snapshot URIs with pagination, registry resource URIs.
- Prompts: ExplainHighCpu, DetectSecurityAnomalies, DiagnoseSystemHealth.

**C# implementation notes:**
- Uses ASP.NET Core for HTTP server.
- Colored console logging with custom formatter.
- Event log snapshots stored in memory; supports XPath filtering.
- WMI access via `System.Management`; sampling generates safe queries.
- Registry access read-only with roots whitelist.

### Python Migration Strategy

**Preserve:**
- Tool/Resource/Prompt separation (non-negotiable).
- Pagination mechanism.
- Elicitation + sampling lifecycle.
- Roots enforcement model.
- Single evolving demo across 7 milestones.
- Colored logging + visibility.

**Adapt:**
- Domain: Linux diagnostics (psutil, /proc, syslog, /etc).
- Transport: FastAPI or aiohttp for HTTP (simpler than ASP.NET for Python).
- Agent framework: Defer server-side sampling if Python preview not ready. Client-side synthesis instead.
- Logging: Use Python `logging` module with formatters.

**Simplify:**
- No destructive operations in Milestone 1–5 (kill_process is dry-run/elicitation only).
- Syslog/journalctl instead of Windows Event Log (simpler API, same teaching value).
- /etc configs instead of registry writes (read-only domain).
- psutil as primary diagnostics API (avoids raw /proc parsing complexity).

**Structure:**
```
mcp_linux_diag_server/
├── src/
│   ├── main.py, server.py
│   ├── tools/ (process, system, syslog, registry)
│   ├── resources/ (storage, syslog, registry)
│   ├── prompts/ (diagnostics workflows)
│   └── services/ (logger, roots, sandbox)
├── client/ (chat client, transport, handlers)
├── tests/
└── pyproject.toml
```

**Milestone arc for Python:**
- M1: get_system_info tool, STDIO, basic JSON-RPC flow.
- M2: Process tools (list, by_id), pagination, detailed metrics.
- M3: Syslog snapshots as resources, prompts as workflows, read_resource tool.
- M4: HTTP transport, bearer token auth, same tools/resources/prompts.
- M5: Elicitation for kill_process (confirm before destructive action).
- M6: Server-side sampling or client-side if Agent Framework not ready.
- M7: Roots enforcement, path whitelist, security boundaries.

**Tech choices:**
- MCP SDK: `mcp` (PyPI, official).
- HTTP: FastAPI (async, simple, production-grade).
- LLM client: azure-openai or openai.
- Diagnostics: psutil (process), logging/journalctl (syslog), pathlib (file access).
- Agent Framework: microsoft-agents (defer if preview unstable).

**Risks:**
- MCP Python SDK feature parity with C#.
- Agent Framework Python preview availability.
- Syslog vs. journalctl trade-off (need domain guidance).
- Sampling complexity if Agent Framework not ready.

**Decision points (coordinator to resolve):**
1. Verify mcp PyPI SDK supports tools, resources, prompts, sampling, elicitation.
2. Confirm Agent Framework Python preview stable?
3. Syslog or journalctl for demo?
4. Azure OpenAI endpoint + creds for chat client?

---

## Team Updates (2026-04-14 Orchestration)

### Dallas Alignment (Linux Diagnostics Mapping)

Dallas completed signal mapping: Windows → Linux equivalents confirmed.
- Event Log → syslog/journalctl (recommended: journalctl for structured logs)
- WMI → /proc/[pid]/, /sys (more educational; students learn kernel interfaces)
- Registry → /proc/sys, /etc (read-only; teaches principle of least privilege)
- Process metrics: /proc/[pid]/stat, /proc/[pid]/status (granular; utime, stime, vss, rss)

**Implication for M1–2:** Use psutil as primary API; recommend /proc reference guide for advanced students.

### Decision Records Merged

5 architectural decisions formally recorded in decisions.md:
- D1: 7-milestone pedagogical arc preserved
- D2: Linux diagnostics domain
- D3: Client-side sampling for M1–5
- D4: Tech stack (mcp, FastAPI, psutil)
- D5: Tool/Resource/Prompt pattern mandatory

**Action:** No changes to architecture. Proceed with STDIO M1–2 as planned.

### Next: Bishop Analysis

Bishop (MCP/C# Expert) in progress on repo/branch structure. Coordinate branch naming and commit message conventions once Bishop completes.

---

## Team Updates (2026-04-13T22:03:56Z Orchestration)

### M1 Architecture & Scope (Ripley)
- Established clear boundaries: M1 STDIO server + single get_system_info tool
- Scope constraints: stdlib only + /proc/uptime (no psutil, no journalctl)
- Deferred: M2 process tools, M3 logs, M4 HTTP

### M1 Linux Data Source Specification (Dallas)
- Finalized /proc file spec: /etc/os-release, /proc/cpuinfo, /proc/meminfo, /proc/loadavg
- Confirmed all sources work identically on WSL2 and bare-metal (no distro-specific code)
- Error handling: graceful degradation with error messages (tool does not crash)

### M1 Validation Approach (Newt)
- Created concrete test harness: JSON-RPC smoke tests + 6 edge cases
- Defined QA sign-off checklist for implementation verification
- Ready to validate Ash's implementation

### M1 Implementation (Ash)
- STDIO MCP server built with get_system_info tool
- All 9 required fields: hostname, username, os_description, os_architecture, process_architecture, processor_count, python_version, current_directory, system_uptime
- Packaging complete (pyproject.toml, editable install)
- Tests written (unit + integration)
- Documentation (README, API docs)

**Status:** M1 work complete. Decisions merged from inbox to decisions.md. Ready for M2 iteration.

### Milestone 1 Lecture Parity (2026-04-14)

- Python M1 now includes a lecture client at `src/mcp_linux_diag_server/client.py` that starts the stdio MCP server, advertises MCP tools to Azure OpenAI as function tools, and lets the model call `get_system_info` during the chat loop.
- Azure configuration is explicit and secret-free: `MCP_DEMO_AZURE_OPENAI_ENDPOINT`, `MCP_DEMO_AZURE_OPENAI_API_KEY`, optional deployment/version overrides, with fallback to the standard Azure env var names.
- `README.md`, `.env.example`, and `scripts/smoke_test.py` now cover both the server path and the lecture client path; the smoke script validates server behavior and confirms the client fails cleanly when Azure config is absent.
- Regression coverage lives in `tests/test_client.py`, `tests/test_m1_smoke.py`, and `tests/test_system_info.py`.

## 2026-04-13T22:36:32Z: M1 Parity Python Implementation Complete

- Implemented Python M1 server using MCP SDK with get_system_info tool (9 fields)
- Added Azure OpenAI chat client with function calling support for M1 lecture demonstration
- Configured environment-based credential management (preflight validation added)
- Test coverage: unit tests for server tools; integration tests with fake LLM model
- Documentation: Quickstart, API Reference, Client Guide for lecture use
- Status: Ready for M1 closure and M2 planning per Newt QA approval


---

## Team Updates (2026-04-14T07:15:48Z — Milestone 1 Live Run Sign-Off)

### Ash: Live M1 Validation Complete ✅

- Confirmed M1 works end-to-end in WSL with Azure CLI login + `.env.local`
- Python client successfully called `get_system_info` via MCP and received Azure OpenAI response
- No code changes needed; auth flow proven ready for lecture use
- Key evidence: single authenticated run showing `Connected to MCP server` + `[tool] get_system_info({})` + usable LLM answer

### Newt: QA Sign-Off ✅

- Independently validated Ash's live run output
- All three required markers present in single output stream
- Approved M1 for production lecture demonstration
- Caveat noted: smoke test covers server startup + missing-config paths, not live Azure success (now proven separately)

---

## Team Updates (2026-04-14T08:00:28Z — Foundry Runtime Decision Closure)

### Foundry Runtime Audit Complete ✅

- Bishop verified local C# reference (`/mnt/c/Dev/MCPDemo`) uses **direct Azure OpenAI**, not Azure AI Foundry project/runtime
- C# repo search: `Azure.AI.OpenAI` + `Microsoft.Agents.AI.OpenAI`, no `Azure.AI.Projects` found
- Python client (`src/mcp_linux_diag_server/client.py`) already aligned: uses direct Azure OpenAI endpoint + deployment
- Real run succeeded: Python client called `get_system_info` tool successfully with local `.env.local`

### Decision Confirmed

- **No Python client runtime shape change required**
- Both Python and C# stay on direct Azure OpenAI path
- If future user requirement is true Foundry project/runtime, that is **new gap in both** codebases, not just Python
- M1–5 continue as currently implemented

### Implication

- Python lecture client is architecturally correct
- No rework needed to match C# reference
- Focus remains on M2–5 milestone progression

---

## Team Updates (2026-04-14T12:51:00Z — Milestone 2 Parity Implementation)

### Milestone 2 Process Tools Complete ✅

- Added Linux `/proc`-backed process inspection for the milestone-2 branch:
  - `get_process_list`
  - `get_process_by_id`
  - `get_process_by_name`
- Kept the lecture flow aligned with Bishop's delta: summary first, detail second, default page size 5
- Avoided adding `psutil`; `/proc` was enough and kept the repo dependency surface unchanged

### Validation Notes

- Full test suite passed: `python3 -m unittest discover -s tests -v`
- Updated smoke test now exercises the new process tools as well as the original missing-Azure-config client check
- README and roadmap now describe Milestone 2 as implemented while keeping Milestone 3+ explicitly deferred


---

## Team Updates (2026-04-14T13:00:00Z — Milestone 2 Delivery Complete)

### Milestone 2 Process Tools Delivered ✅

- **Ash:** Implemented Linux `/proc`-backed process tools on `milestone-2` branch
  - `get_process_list`: Full process enumeration with paging (default: 5 per page)
  - `get_process_by_id`: Per-PID detail snapshot with stat + status metrics
  - `get_process_by_name`: Filtered list with regex matching and paging
  - Updated server guidance and lecture client examples
  - No external dependencies added; `/proc` kept intentional to teach kernel diagnostics

- **Newt:** Comprehensive test coverage delivered
  - Unit tests (`tests/test_processes.py`): `/proc` parsing edge cases, fallback behavior, pagination cursor logic
  - Integration smoke (`tests/test_m2_smoke.py`): SDK-driven stdio validation against live sleeper subprocess
  - Full test suite passes: `python3 -m unittest discover -s tests -v` ✅
  - Smoke test passes: `python3 scripts/smoke_test.py` ✅

### Technical Achievements

- **Data source decision:** Linux `/proc` direct reads (not `psutil`) ratified in D6
- **Test strategy:** Dual lanes (unit + smoke) ratified in D7
- **Branch model:** `milestone-1` public, `milestone-2` squad-enabled ratified in D8
- **Documentation:** README/roadmap updated; M2 complete, M3+ deferred

### Decisions Merged to decisions.md

D6, D7, D8 from decision inbox merged:
- `decisions/inbox/ash-m2.md` → decisions.md (D6)
- `decisions/inbox/newt-m2-tests.md` → decisions.md (D7)
- `decisions/inbox/ripley-branch-model.md` → decisions.md (D8)
- Inbox files cleared

### Squad Status

- All agents reported completion
- Session log saved: `.squad/log/2026-04-14T13:00:00Z-milestone-2-delivery.md`
- Cross-agent history appended to agent files
- Ready for publication or M3 planning

---

## Team Updates (2026-04-14T14:55:00Z — Milestone 4 HTTP Parity)

### Milestone 4 Transport Parity Complete ✅

- Switched the runnable Python MCP server from stdio-first to authenticated streamable HTTP on `/mcp`
- Added demo API key validation for both `X-API-Key` and `?apiKey=...`
- Kept the Milestone 1-3 tool, resource, and prompt registrations unchanged
- Updated the lecture client to launch the local HTTP server and connect through the MCP SDK's HTTP transport

### Validation Learnings

- The Python MCP SDK already preserves `mcp-session-id` correctly for HTTP clients, so the main parity work is making sure the first initialize response is authenticated and allowed through unchanged.
- Reviewer-grade M4 validation needs two lanes: a raw HTTP lane for `401`/session-header behavior and an SDK lane for the unchanged M1-M3 tool, resource, and prompt surface.
- Using a tiny shared HTTP config module keeps the server, lecture client, smoke script, and inspector config aligned on host, port, route, and demo key without drifting.
- Milestone 6's live sampling contract is a single plain-text target (`PATH` or `PATH | grep FIELD`); when smoke/test fixtures drift back to JSON, the server correctly rejects them and the published smoke lane breaks even though the feature itself is intact.

---

## Team Updates (2026-04-14T12:56:18Z — M6 naming-rule follow-up)

### Ash: Milestone-labeled module rename applied ✅

- Renamed `src/mcp_linux_diag_server/tools/m6_diagnostics.py` to the domain-based `src/mcp_linux_diag_server/tools/linux_diagnostics.py`
- Updated package exports, test imports, and the sampling-bridge skill reference so no live repo references still point at the milestone-labeled module path
- Kept the public MCP surface unchanged (`troubleshoot_linux_diagnostics`, validation helpers, smoke flow), so this stayed a corrective follow-up instead of new feature work

### Useful Learnings

- Milestone names are fine for branch/docs planning, but Python module filenames should stay domain-based so imports remain stable after the milestone is complete.
- For rename-only follow-ups, a fast repo-wide search before and after the move is the cleanest way to prove package exports, tests, and teaching docs all stayed aligned.
