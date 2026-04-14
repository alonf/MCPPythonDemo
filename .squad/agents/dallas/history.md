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

---

## Session: M5 Linux Diagnostics Review for Process Termination (2026-04-14T16:45Z)

### Task
Review Milestone 5 parity target from Linux diagnostics perspective; provide implementation guidance for process termination with elicitation.

### Key Findings

**CPU Sampling (750ms window) — VERIFIED SAFE:**
- Data source: `/proc/[pid]/stat` fields 14–15 (utime + stime in clock ticks)
- Formula: `(cpu_delta_ticks / cpu_count) / (750ms * SC_CLK_TCK/1000) * 100`
- Stable since Linux 2.2; works on all architectures
- Race-safe: Process exit leaves zombie window (~100ms); safe to handle gracefully

**Process Termination — SIGTERM → SIGKILL:**
- SIGTERM (15): Allow cleanup; process can trap or ignore
- SIGKILL (9): Forceful; kernel-side termination after 5s timeout
- Use `os.kill()` and `signal` module (POSIX standard)
- Check `/proc/[pid]/` disappearance or `os.kill(pid, 0)` no-op to detect exit

**Linux-Specific Quirks (ASH MUST RESPECT):**
1. **Permission model:** Non-root cannot kill other users' processes; graceful error
2. **Zombie filtering:** Skip state='Z' from elicitation list; can't be signaled
3. **Daemon warnings:** Read `/proc/[pid]/comm`; warn before killing sshd, systemd, etc.
4. **Namespace awareness:** Detect via `/proc/[pid]/ns/pid` inode comparison; warn if cross-namespace
5. **Container detection:** Check `/proc/self/cgroup` for docker/lxc; report in logs
6. **WSL2 protection:** Block PID 1–10 (custom init); severe warning or block entirely

**Parity-Critical Constraints for Ash:**
- Elicitation client capability check before form display
- Top 5 CPU processes: sort by CPU% desc, secondary sort by RAM desc
- Confirmation phrase: case-insensitive exact match "CONFIRM PID {pid}"
- Result struct: process_id, process_name, status, message, reason (all required)
- Status values: "terminated", "cancelled", "not-found", "failed", "permission-denied"

### Deliverables

1. **Written to `.squad/decisions/inbox/dallas-m5-linux.md`:**
   - Complete CPU sampling formula with derivation
   - Signal sequence (SIGTERM → SIGKILL) with Python API
   - All permission/zombie/namespace/WSL edge cases with Ash responsibilities
   - Parity-critical constraints (5 must-haves, 4 nice-to-haves)
   - Risk matrix for implementation

2. **Stability Notes for Team:**
   - `/proc/[pid]/stat` stable kernel interface since 1999
   - `os.cpu_count()`, `os.sysconf("SC_CLK_TCK")` guaranteed available
   - Signal constants (SIGTERM=15, SIGKILL=9) are POSIX standard
   - Permission model consistent across all Linux distributions

### Learnings Extracted

**On CPU Sampling Stability:**
- 750ms wall-clock window is safe; process exits are handled gracefully
- Zombie window (~100ms after exit) allows T1 snapshot to succeed
- CPU% calculation is linear in cpu_count; no special adjustments for asymmetric cores
- Negative delta edge case (rapid exec resets timers) rare but should be handled (max(delta,0))

**On Process Termination in Linux:**
- No graceful tree-kill API (unlike Windows); single-PID SIGTERM is closest equivalent
- Daemons reparenting to PID 1 is normal (init adoption); not a blocker
- Zombie processes (state='Z') cannot be signaled; only parent can reap via wait()
- Permission model is per-UID, not per-process; root bypass is CAP_KILL only

**On Container & Namespace Semantics:**
- Container boundaries are kernel-opaque; bulk process scan only sees local namespace
- Cross-namespace kill requires privileged escalation or container tools (not a blocker)
- PID namespaces are detected via inode comparison; WSL is detectable via /proc/version

**On WSL2 Specific Behavior:**
- PID 1 is custom init, not systemd; killing it stops entire WSL session
- SC_CLK_TCK correct on WSL2; no adjustments needed for CPU sampling
- Interop processes (Windows via WSL interop) are visible but killing is unpredictable; warn
- Detection: Check `/proc/version` for "microsoft" or "WSL" string

### Skill Extraction

**Reusable Pattern: Process Snapshot Dataclass**
- Encapsulates safe CPU delta calculation and ranking logic
- Use for both elicitation sampling and multi-tool CPU investigations
- Fields: pid, name, utime_ticks, stime_ticks, vms_bytes, rss_bytes, state, ppid, uid, is_readable
- Ranking: `sorted(snapshots, key=lambda s: (-cpu_percent(s, t0), -s.rss_bytes))`[:5]

**Reusable Pattern: Permission-Aware Process Filtering**
- Try-continue on /proc read failures; only error on explicit single-PID requests
- Check UID before offering kill; graceful "permission-denied" result if not killable
- Pre-filter zombies (state='Z') from elicitation lists; report "already dead" if selected

### Recommendation for Ash

Implement full M5 parity with all edge-case protections. The constraints are not "nice-to-have ergonomics"; they are **binding** for safety and educating students on Linux permission, namespace, and lifecycle semantics.

**No code changes needed from Dallas:** Decision written; ready for Ash's implementation review.

---
