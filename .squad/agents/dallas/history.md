# Project Context

- **Owner:** alon
- **Project:** Python Linux Diagnostics demo migrated from the C# MCPDemo repo and lecture
- **Stack:** Python, MCP, Microsoft Agent Framework, Linux diagnostics, `/proc`, Git branches
- **Created:** 2026-04-13T21:30:48.993Z

## Learnings

- The target demo is Linux Diagnostics, so `/proc` and Linux-native system interfaces are core design inputs.
- The migration should keep the lecture structure while adapting to Linux-specific data sources cleanly.

## Lecture Analysis (Season_of_AI_5_MCP.pdf)

### Context
- MCPDemo is a **Windows/.NET-focused** lecture on MCP (Model Context Protocol)
- Structure: 7 milestones showing MCP concepts via Windows diagnostics (event logs, WMI, registry)
- Tools: listProcesses(), getProcessDetails(pid), queryEventLog(), readRegistry(), troubleshootWithWmi()
- Resources: snapshots of event logs, processes, registry (stored as JSON files)
- Prompts: AnalyzeRecentApplicationErrors, ExplainHighCpu, DetectSecurityAnomalies, DiagnoseSystemHealth
- Client: WinDiagMcpChat with Azure OpenAI integration for AI-guided workflows
- Transports: STDIO → HTTP with bearer token auth
- Safety: Elicitation (prompt user for missing params), Sampling (LLM-as-subroutine), Roots (sandbox paths)

### Branches (7 milestones)
- milestone-1: Minimal tool (STDIO, getSystemInfo)
- milestone-2: Process inspection (listProcesses, getProcessDetails)
- milestone-3: Event log analysis (Resources, Prompts)
- milestone-4: HTTP transport + security
- milestone-5: Elicitation for dangerous ops (killProcess)
- milestone-6: Sampling-assisted WMI troubleshooting
- milestone-7: Roots & sandbox model

### Linux Migration Implications

**SIGNAL MAPPING (Windows → Linux):**
- Event Logs → /var/log (syslog, journalctl)
- WMI → /proc, /sys, sysfs, cgroups
- Registry → /proc/sys, /etc config files
- Process metrics (private bytes, virtual mem) → /proc/[pid]/ entries
- Task Scheduler → cron, systemd timers
- Windows event subscriptions → rsyslog filters, journal queries

**DATA SOURCES (Linux-specific):**
- /proc/meminfo - Memory usage
- /proc/loadavg - Load average
- /proc/[pid]/stat - Process CPU/memory
- /proc/[pid]/fd/ - Open file descriptors
- /proc/net/tcp - Network sockets
- /sys/class/thermal/ - Temperature sensors
- /proc/pressure/ - PSI (Pressure Stall Info)
- journalctl - Structured logging (systemd)
- /var/log/syslog, /var/log/auth.log - Text-based logs
- cgroup interfaces - Resource accounting

**LINUX-SPECIFIC GOTCHAS:**
1. **Privilege model:** No UAC. Root access needed for full diagnostics; non-root sees only own processes/data.
2. **Namespace isolation:** Containers/VMs see filtered /proc. Tools must respect PID namespaces.
3. **Virtual filesystems:** /proc, /sys are ephemeral; stat calls can race with PID exit.
4. **Text format fragility:** Log parsing is fragile; prefer structured APIs (journalctl JSON, /proc parsers).
5. **Permissions:** Reading /proc/[pid]/fd or /sys/ may fail silently for other users' processes.
6. **Portability:** glibc vs musl, systemd vs init, cgroup v1 vs v2 affect signal shape.
7. **Cost of /proc parsing:** Frequent reads can spike CPU; cache snapshots.

**INSTRUCTIONAL VALUE (Linux angle):**
- Show /proc as "the" diagnostics API—students learn low-level Linux interfaces.
- Contrast: Windows WMI (high-level) vs Linux /proc (raw kernel state).
- Elicitation: "Show me the top CPU process" → parse /proc/[pid]/stat for each PID, rank by utime+stime.
- Sampling: "Analyze why memory is high" → LLM reads /proc/meminfo + /proc/[pid]/status snapshots, reasons.
- Safety: Roots restrict access to /proc, /sys by path. Teach why: avoid leaking other users' data.
- Permissions: Demonstrate how tools fail gracefully when non-root; offer fallbacks.

**ROADMAP ALIGNMENT:**
- M1: get_system_info() → read /proc/meminfo, /proc/cpuinfo, /proc/loadavg
- M2: list_processes(), get_process_info(pid) → scan /proc/[pid]/stat, /proc/[pid]/status
- M3: create_log_snapshot(logName, hoursBack) → journalctl or syslog parsing; store as resource
- M4: HTTP transport (same as Windows version)
- M5: (Optional) kill_process(pid, reason) with elicitation (dangerous on Linux too)
- M6: Sampling for "explain high memory" → LLM reasons over /proc/ snapshots
- M7: Roots: restrict to /proc, /sys, /var/log paths; demonstrate non-root limitations

**REPO STRUCTURE (Python MCP adaptation):**
- server.py - MCP server entry point (stdio/http transport)
- tools/system_info.py - Parse /proc/meminfo, /proc/cpuinfo, etc.
- tools/process.py - List/detail processes via /proc/[pid]/
- tools/logs.py - Query journalctl or /var/log files
- tools/sampling.py - LLM-as-subroutine helpers
- resources/ - Snapshot storage (e.g. log exports)
- client/ - Python async MCP client (replaces WinDiagMcpChat)
- tests/ - Unit tests for /proc parsing, error handling

---

## Team Updates (2026-04-14 Orchestration)

### Ash Alignment (Architecture Validation)

Ash completed migration analysis; confirms Dallas signal mapping is sound.
- Tool/Resource/Prompt separation validated as non-negotiable pedagogy.
- psutil as primary process API aligns with /proc reference role.
- Sampling lifecycle: client-side for M1–5 approved; defers Agent Framework complexity.

**Implication for M3+:** Snapshot storage + resource pagination ready; no /proc parsing blocker.

### Decision Records Merged

5 architectural decisions formally recorded in decisions.md:
- D1: 7-milestone pedagogical arc preserved
- D2: Linux diagnostics domain
- D3: Client-side sampling for M1–5
- D4: Tech stack (mcp, FastAPI, psutil)
- D5: Tool/Resource/Prompt pattern mandatory

**Action:** Linux constraints documented; risks & mitigations filed. No architecture changes needed.

### Documentation Action

Create LINUX_DIAGNOSTICS.md reference guide for students (covers /proc signals, permissions, namespace caveats).

### Next: Coordinator Review

Ready for Ash to spawn on M1 STDIO server. Bishop to finalize repo/branch conventions.

---

## Session: M1 Data Source Definition (2026-04-14, Milestone Kickoff)

**Task:** Define exact Linux data sources for Milestone 1 `get_system_info()` implementation without WSL-specific code.

**Artifacts Reviewed:**
- Season_of_AI_5_MCP.pdf (lecture structure and Windows→Linux mapping)
- MCPDemoRoadmap.md (M1 tool spec: getSystemInfo)
- .squad/decisions.md (D2: Windows diagnostics → Linux diagnostics mapping, D4: Tech stack confirmation)
- .squad/skills/linux-proc-diagnostics/SKILL.md (parsing patterns, error handling)

**Recommendation Delivered:**
- **Source:** `/etc/os-release` for OS identity, `/proc/cpuinfo` for CPU, `/proc/meminfo` for RAM, `/proc/loadavg` for load
- **No WSL-specific code:** All sources work identically on WSL2 and bare-metal Ubuntu
- **Data structure:** JSON/dict with os, cpu, memory, load sub-objects; memory in bytes (no overflow)
- **Error handling:** Graceful degradation; tool returns error message, doesn't crash
- **Testing:** Non-root test, WSL vs bare-metal parity, parse robustness

**Decision Written:** `.squad/decisions/inbox/dallas-m1-linux-mechanism.md`

**Status:** Ready for Ash to implement STDIO server with this spec. No code changes; specification only.

---

## Team Updates (2026-04-13T22:03:56Z Orchestration)

### M1 Architecture Defined (Ripley)
- Tight scope for M1: STDIO transport + get_system_info tool
- stdlib + /proc/uptime only (no psutil, no extended /proc parsing until M2)
- Deferred: process tools (M2), journalctl (M3), HTTP (M4)

### M1 Linux Data Source Specification (Dallas)
- **Completed:** Full /proc file spec for get_system_info implementation
- Sources: /etc/os-release (OS), /proc/cpuinfo (CPU), /proc/meminfo (Memory), /proc/loadavg (Load)
- Confirmed: No WSL-specific code needed; patterns work identically WSL and bare-metal
- Error handling: Graceful degradation (error message, no crash)
- Testing strategy: Non-root, WSL vs bare-metal parity, parse robustness

### M1 Validation (Newt)
- Prepared concrete test harness with JSON-RPC examples (4 smoke tests + 6 edge cases)
- QA sign-off checklist ready for implementation verification

### M1 Implementation (Ash)
- STDIO server with get_system_info tool built and packaged
- All 9 fields present with graceful error handling
- Tests and docs complete

**Status:** M1 decision written to decisions.md. Implementation ready for Newt validation.

## 2026-04-13T22:36:32Z: M1 Parity Analysis — Linux Diagnostics Scope Confirmed

- M1 parity analysis confirmed Linux diagnostics approach aligns with D2 decision
- get_system_info tool implementation verified: 9 fields using /proc and stdlib equivalents
- All data sources (os-release, /proc/uptime, /proc/cpuinfo) tested non-root readable on WSL and bare-metal
- M2+ roadmap: Event log parity via syslog/journalctl; process metrics via /proc/[pid]/stat
- Status: M1 Linux diagnostics scope locked; ready for M2 planning
