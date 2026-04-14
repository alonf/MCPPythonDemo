# MCPDemo Roadmap (Python/Linux Adaptation)

This roadmap mirrors the teaching arc of the original C# `MCPDemo` repository, but maps it onto a Python implementation and Linux diagnostics domain.

## Status Summary

| Milestone | Original C# Theme | Python/Linux Plan | Status |
|----------|--------------------|-------------------|--------|
| 1 | Minimal stdio diagnostics tool | `get_system_info` + lecture chat client | ✅ Complete |
| 2 | Process inspection | Linux process listing, per-PID detail, and by-name paging | ✅ Complete |
| 3 | Resources and prompts | Linux log snapshot resources + prompts | ✅ Complete |
| 4 | HTTP transport and security | Python HTTP MCP transport + auth | ✅ Complete |
| 5 | Elicitation | Confirmation flow for risky operations | ✅ Complete |
| 6 | Sampling-assisted diagnostics | AI-assisted Linux diagnostics queries | ✅ Complete |
| 7 | Roots and boundaries | Safe filesystem/config roots | ⏳ Planned |

## Milestone 1 – Minimal diagnostics tool (STDIO) ✅

Implemented scope:
- stdio MCP server
- one read-only tool: `get_system_info`
- Linux/WSL-safe data sources:
  - `/etc/os-release`
  - `/proc/uptime`
  - `/proc/loadavg`
  - `/proc/meminfo`
- Python lecture chat client that launches the server and supports Azure OpenAI tool-calling

Milestone 1 remains the conceptual base teaching path.

## Milestone 2 – Process inspection ✅

Implemented scope:
- list running processes with lightweight summaries
- inspect one process by PID with Linux `/proc` detail
- inspect matching processes by name with default paging (`page_size=5`)
- keep the summary-first, detail-second teaching flow

## Milestone 3 – Resources and prompts ✅

Implemented scope:
- `create_log_snapshot` tool for common Linux log groups (`system`, `security`, `kernel`, `package`)
- read-only `syslog://snapshot/{snapshot_id}` resources with paged reads via `?limit=...&offset=...`
- four MCP prompts mirroring the C# teaching workflows:
  - `AnalyzeRecentApplicationErrors`
  - `ExplainHighCpu`
  - `DetectSecurityAnomalies`
  - `DiagnoseSystemHealth`
- chat-client helper access to MCP prompts and resources
- clear tool/resource/prompt separation, with tools creating snapshots and resources reading them

## Milestone 4 – HTTP transport and security ✅

Implemented scope:
- switched the runnable server from stdio-first to authenticated streamable HTTP
- mounted MCP on `/mcp`
- accepted the demo API key via `X-API-Key` header or `apiKey` query parameter
- preserved HTTP client session handling through the MCP SDK `mcp-session-id` flow
- updated the lecture client, smoke path, and inspector config for HTTP mode
- kept the Milestone 1-3 tool, resource, and prompt surface unchanged

## Milestone 5 – Elicitation ✅

Implemented scope:
- `kill_process` with server-driven form elicitation
- top-CPU candidate sampling when `process_id` is omitted
- mandatory typed confirmation phrase before termination
- Linux-safe SIGTERM then SIGKILL fallback semantics

## Milestone 6 – Sampling-assisted diagnostics ✅

Implemented scope:
- added `troubleshoot_linux_diagnostics` for the two-phase sampling pattern
- server validates every sampled `/proc` or `/sys` path plus optional field before execution
- exact Python adaptation: the sampled query format is a single safe `PATH` or `PATH | grep FIELD` line rather than WQL
- deterministic data collection stays separate from model-generated explanations
- lecture client now advertises sampling support and fulfills `sampling/createMessage`
- added `TroubleshootLinuxComponent` prompt guidance for the focused teaching flow

## Milestone 7 – Roots and limitations ⏳

Planned scope:
- safe access boundaries
- explicit limits around what the client/server may inspect

## Important Parity Note

This repo intentionally follows the **same milestone progression** as the original C# demo. Milestones 1-6 now have Python parity; public documentation should stay aligned with the real implementation state for Milestone 7 and later.
