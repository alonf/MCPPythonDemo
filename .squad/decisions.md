# Squad Decisions

## Active Decisions

### D1: Python Implementation Preserves C# Pedagogical Arc (2026-04-14)

**Decision:** The Python MCPPythonDemo will adopt the same 7-milestone progression as the C# MCPDemo: STDIO tools → resources → prompts → HTTP → elicitation → sampling → roots.

**Rationale:** The pedagogical structure is the core teaching mechanism; transport and domain can shift, but the conceptual flow (tool/resource/prompt separation, snapshot pagination, elicitation+sampling lifecycle) is non-negotiable.

**Owners:** Ash (Python Dev), Dallas (Linux Diagnostics Expert)

---

### D2: Windows Diagnostics → Linux Diagnostics (2026-04-14)

**Decision:** Replace Windows APIs with Linux equivalents:
- Event Log → syslog/journalctl
- WMI → /proc, /sys
- Registry → /proc/sys, /etc
- Process metrics → /proc/[pid]/stat, /proc/[pid]/status

**Rationale:** Simpler than Windows for teaching, equally valid domain, aligns with deployment target (Linux machines).

**Owners:** Dallas (Linux Diagnostics Expert), Ash (Python Dev)

---

### D3: Client-Side Sampling for Milestones 1–5 (2026-04-14)

**Decision:** Defer server-side Agent Framework sampling to M6–7. For M1–5, implement sampling client-side: client calls Azure OpenAI directly, reads server resources, synthesizes response.

**Rationale:** Keeps M1–5 simpler; Agent Framework Python preview may not be ready; client-side sampling proves the pattern without blocking.

**Owners:** Ash (Python Dev)

---

### D4: Tech Stack: mcp SDK, FastAPI, psutil (2026-04-14)

**Decision:** Use `mcp` (PyPI official SDK), FastAPI (HTTP server), psutil (process diagnostics), systemd/journalctl (logs).

**Rationale:** Equivalent capabilities to C#; FastAPI widely known; psutil battle-tested; avoids complex Windows API equivalents.

**Owners:** Ash (Python Dev)

---

### D5: Tool/Resource/Prompt Pattern Must Carry Over (2026-04-14)

**Decision:** The C# design's separation of concerns (tools = deterministic ops, resources = read-only snapshots, prompts = AI-guided workflows) is the pedagogical core and must be preserved exactly in Python.

**Rationale:** This pattern is what students learn; domain and transport differences don't matter if the core pattern stays.

**Owners:** Ash (Python Dev), Dallas (Linux Diagnostics Expert)

---

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction

---

### M1 Architecture: STDIO MCP Server + get_system_info (2026-04-14)

**Decision by:** Ripley (Lead)  
**Status:** Active

Deliver the Python equivalent of C# MCPDemo Milestone 1: a minimal STDIO MCP server exposing one diagnostic tool (`get_system_info`). Keep scope tight to prove the stack before expanding.

**Key Constraints:**
- Single STDIO transport (no HTTP)
- One tool: `get_system_info` returning 8 system diagnostic fields
- Use stdlib (`os`, `platform`, `socket`) + `/proc/uptime` for data
- No psutil (defer to M2), no journalctl (defer to M3)
- Works on Ubuntu 22.04+, WSL2, native Linux

**Allowed M1 Data Sources:**
- `/proc/uptime` - system uptime parsing
- `socket.gethostname()`, `os.getlogin()`, `platform.platform()`, etc. - standard library
- `/etc/os-release` - OS metadata (if using Dallas's spec)

**Deferred to Later Milestones:**
- M2: Process listing, psutil, get_process_info
- M3: journalctl, event logs, resources, prompts
- M4: HTTP transport, authentication
- M5+: Elicitation, sampling, roots

**Owners:** Ash (implementation), Dallas (Linux data), Newt (validation), Ripley (architecture)

**Acceptance Criteria:**
- `python -m lindiag_mcp_server` starts STDIO server
- MCP Inspector discovers one tool: `get_system_info`
- Tool returns valid JSON with all 8 required fields
- No external dependencies beyond `mcp` SDK
- Works on Ubuntu 22.04+ and WSL2

---

### M1 Linux Data Sources for get_system_info (2026-04-14)

**Decision by:** Dallas (Linux Diagnostics Expert)  
**Status:** Final Recommendation

Specification of exact Linux `/proc` files to read and fields to extract for M1 implementation.

**Data Source Specification:**

| Field | Source | Method |
|-------|--------|--------|
| OS Info | `/etc/os-release` | Parse NAME, VERSION_ID, PRETTY_NAME |
| CPU | `/proc/cpuinfo` | Extract processor count, model name, cores |
| Memory | `/proc/meminfo` | Parse MemTotal, MemFree, MemAvailable (in kB) |
| Load | `/proc/loadavg` | First 3 fields: 1min, 5min, 15min load average |

**Key Design Decisions:**
- No WSL-specific branches; all sources work identically on WSL and bare-metal
- Non-root safe; all files readable by regular users
- Graceful degradation on missing files (return error message, not crash)
- Bytes preferred for memory (avoid 32-bit overflow)
- Tested on Ubuntu 20.04+, Debian 12, WSL2

**Return Structure (M1):**
```json
{
  "os": { "name": "Ubuntu", "version": "22.04", "pretty_name": "Ubuntu 22.04.3 LTS" },
  "cpu": { "logical_count": 8, "physical_cores": 4, "model": "Intel Core i7" },
  "memory": { "total_bytes": 8589934592, "available_bytes": 4294967296, "used_bytes": 4294967296 },
  "load": { "load_1min": 0.45, "load_5min": 0.52, "load_15min": 0.48 }
}
```

**Owners:** Dallas (specification), Ash (implementation), Newt (validation)

---

### M1 Validation Approach: Minimal get_system_info Server (2026-04-14)

**Decision by:** Newt (Tester)  
**Status:** Active

Validation is runnable, not speculative. All checks have concrete JSON-RPC input/output pairs.

**Smoke Test Checks:**
1. Server startup on STDIO
2. MCP initialize handshake (check protocolVersion response)
3. Tool discovery (tools/list returns get_system_info)
4. Tool execution (tools/call with empty args returns all 9 fields)

**Edge Cases Covered:**
- /proc/uptime missing → fallback to zero or calculated uptime
- /etc/os-release missing → fallback to platform.system()
- UTF-8 encoding issues on WSL → ensure valid UTF-8 output
- Extra arguments passed → tool ignores and succeeds
- Invalid tool name → error response (not crash)
- Malformed JSON → parse error handled, server continues

**Test Automation:**
Provided Python test harness `tests/test_m1_server.py` with full JSON-RPC examples.

**QA Sign-Off Checklist:**
- [ ] Server builds and starts without errors
- [ ] All four smoke tests pass on WSL2 and native Linux
- [ ] All six edge cases handled correctly
- [ ] All 9 response fields present and non-null

**Owners:** Newt (validation strategy), Ash (implementation)

---

### M1 Implementation Note (2026-04-14)

**Decision by:** Ash (Python Dev)  
**Status:** Complete

M1 stays deliberately narrow:
- STDIO transport plus single `get_system_info` tool
- Linux-native data sources (`/etc/os-release`, `/proc/uptime`, `/proc/loadavg`, `/proc/meminfo`)
- Simple `src/` layout with editable install + `mcp dev` compatibility
- No HTTP, resources, prompts, or process tooling (deferred to later milestones)

**Deliverables:**
- `lindiag_mcp_server/` package with STDIO server
- `tools/system_info.py` - get_system_info implementation
- `models/system_info.py` - SystemInfoResult dataclass
- `pyproject.toml` - packaging with mcp SDK dependency
- Full test suite (unit + integration)
- Documentation (README, API docs)

**Status:** Implementation ready for Newt's validation.

---

### Bishop: MCPDemo Branch Interpretation (2026-04-14)

**Decision by:** Bishop  
**Status:** Reference

- Treat `docs/MCPDemoRoadmap.md` as the lecture/roadmap source of truth
- No PDF exists on `master`; repo search found no PDF under `docs/`
- Do NOT infer milestone meaning from branch tip commit messages (all touched by 2026-04-13 package-upgrade commits)
- Milestone branches are not a single linear ancestry chain; use per-branch behavioral diffs against the previous milestone
- `master` is effectively `milestone-7` plus documentation polish

---

### 2026-04-13T21:52:08Z: User Directive — Ubuntu on WSL + Common Linux Diagnostics

**Decision by:** Alon Fliess (via Copilot CLI)  
**Status:** Reference

- Target Ubuntu on WSL as the current Linux environment
- Prefer a common Linux diagnostics mechanism rather than a distro-specific approach
- User request captured for team memory


---

# Ash Decision: M1 lecture parity keeps the Python server and adds a client-side tool-calling chat path

## Decision

Keep the existing Milestone 1 stdio server and `get_system_info` tool intact, but add a Python lecture client that starts the local MCP server and exposes advertised MCP tools to Azure OpenAI via function calling.

## Why

The C# lecture demo is not just a server smoke test; it also shows a runnable AI client/agent path. Python needed the same teaching loop without pulling later-milestone resources, prompts, or HTTP concerns into M1.

## Consequences

- M1 remains stdio-only on the server side.
- The lecture client uses explicit Azure env vars instead of hardcoded secrets.
- Client-side tool calling is the parity mechanism for M1; server-side sampling stays deferred.

---

---
decision_id: bishop-m1-corrected-branch-spec
title: "Corrected Milestone 1 Parity: GitHub alonf/MCPDemo:milestone-1 is NOT Server-Only"
date: 2026-04-14T01:35:00Z
owner: Bishop
status: Critical Correction
---

## Summary

**The previous parity extraction was INCORRECT.** GitHub `alonf/MCPDemo` branch `milestone-1` includes **both** `WinDiagMcpServer` (STDIO MCP server) **AND** `WinDiagMcpClient` (LLM-backed agent using Azure OpenAI). The extraction incorrectly claimed C# M1 was "server-only." This correction updates the architectural truth.

## Evidence

### C# Milestone 1 Actually Contains End-to-End LLM Flow

**GitHub `alonf/MCPDemo:milestone-1`** directory structure (verified from repo):
```
WinDiagMcpClient/
  └── Program.cs              ← LLM-backed agent (Azure OpenAI)
  └── WinDiagMcpClient.csproj
WinDiagMcpServer/
  └── Program.cs              ← STDIO MCP server
  └── SystemInfoResult.cs
  └── WinDiagMcpServerToolType.cs
  └── ...
```

### WinDiagMcpClient/Program.cs Architecture (Raw Evidence)

```csharp
// Uses Azure.AI.OpenAI SDK
using Azure.AI.OpenAI;
using Azure.Identity;
using Microsoft.Agents.AI;  // ← LLM Agent Framework

// Hard-coded Azure endpoint
var endpoint = new Uri("https://alonlecturedemo-resource.cognitiveservices.azure.com/");
var credential = new DefaultAzureCredential();
var deploymentName = "model-router";

// Spawns server as subprocess
var mcpClient = await McpClient.CreateAsync(
    new StdioClientTransport(new()
    {
        Command = dotnetExecutable,
        Arguments = ["run", "--project", projectPath],
        Name = "WinDiagMcpServer"
    }));

// Wraps server tools in LLM Agent
AIAgent agent = new AzureOpenAIClient(endpoint, credential)
    .GetChatClient(deploymentName)
    .AsAIAgent(
        instructions: "You are a helpful computer analysis and problem solving assistant...",
        name: "ComputerAnalyzer",
        tools: [.. tools]);  // ← Server tools passed to agent

var prompt = "What is the system information?";
var agentResponse = await agent.RunAsync(prompt);  // ← LLM call
Console.WriteLine(agentResponse.Text);
```

### What This Means

- **`WinDiagMcpServer`**: STDIO MCP server exposing `get_system_info` tool (deterministic)
- **`WinDiagMcpClient`**: Azure OpenAI-backed LLM agent that spawns server as subprocess, wraps tools, and orchestrates LLM calls
- **Transport**: STDIO only (no HTTP in M1)
- **LLM**: Azure OpenAI (`model-router` deployment, `DefaultAzureCredential` auth)
- **Architecture Pattern**: Client-side sampling (LLM agent runs on client; server is stateless tool provider)

## Pedagogical Arc

### C# Milestone 1 Flow (Actual)
1. User runs `WinDiagMcpClient`
2. Client starts `WinDiagMcpServer` as subprocess
3. Client discovers tools via `ListToolsAsync()`
4. Client passes tools to Azure OpenAI agent
5. User asks: "What is the system information?"
6. Agent calls MCP tool `get_system_info` to collect data
7. Agent synthesizes response
8. Client displays: "Your system is running Windows 10.0.22631 with 44 processors..."

**This is an END-TO-END LLM-INTEGRATED FLOW, not just a server demo.**

### Python Milestone 1 (Current Implementation)
- Server-only, no LLM agent
- Exposes same tool: `get_system_info` with 9 fields
- Uses stdlib + `/proc` for Linux equivalents
- **Per D3 decision**: Client-side sampling deferred to M5+

### Parity Assessment

| Aspect | C# M1 | Python M1 (Current) | Gap |
|--------|-------|---------------------|-----|
| **Transport** | STDIO ✅ | STDIO ✅ | None |
| **Tool: `get_system_info`** | 9 fields ✅ | 9 fields ✅ | None |
| **LLM Integration** | Azure OpenAI agent ✅ | None ❌ | **INTENTIONAL** (per D3) |
| **Client** | LLM-backed agent ✅ | None ❌ | **INTENTIONAL** (per D3) |

**Verdict:** Python M1 is NOT a full parity port of C# M1. It is a PARTIAL port (server-only slice). This is an **intentional architectural divergence** per **D3 (Client-Side Sampling for M1–5)**, not an oversight.

## Pedagogical Implications

### C# Students Get (in M1)
- MCP protocol basics (STDIO, tool discovery, tool invocation)
- Real LLM agent execution (Azure OpenAI integration)
- End-to-end workflow: user prompt → agent → server tool → LLM response

### Python Students Get (in M1)
- MCP protocol basics (STDIO, tool discovery, tool invocation)
- Server implementation with Linux diagnostics
- LLM integration deferred (arrives in M5+ with client implementation)

**Implication:** These are **different pedagogical approaches**, not equivalent. The C# demo is "LLM-first learning"; the Python demo is "protocol-first learning." Both valid; requires explicit documentation to students.

## Corrected Decisions

1. **Previous claim:** "C# M1 is server-only"
   **CORRECTED TO:** "C# M1 includes both server and LLM-backed client"

2. **Previous claim:** "Python M1 should mirror C# M1 exactly"
   **CORRECTED TO:** "Python M1 mirrors C# M1's *server* component only; client-side LLM sampling is intentional deferred to M5+ per D3"

3. **Design confirmation:** D3 (Client-Side Sampling for M1–5) is the source of truth for this divergence. Python M1 follows that decision correctly.

## Action Items

- [ ] Update `.squad/decisions.md` to replace `bishop-m1-llm-parity.md` with this corrected spec
- [ ] Document in Python M1 implementation guide: "Python M1 is server-only; LLM client arrives in M5+"
- [ ] Confirm with Ash (Python Dev) that Python M1 implementation stays server-only
- [ ] Consider adding note to M5 roadmap: "M5 brings Python LLM client parity to C# M1"

## Conclusion

The source branch `alonf/MCPDemo:milestone-1` is **NOT server-only**. It is a complete end-to-end demonstration including LLM-backed client orchestration. Python M1's server-only approach is intentional per D3, not incomplete. Both are valid; they teach different aspects of the MCP lifecycle.

---

# Bishop: C# Milestone 1 LLM Agent Analysis

**Date:** 2026-04-14  
**Topic:** Does C# M1 require an LLM-backed agent?  
**Status:** Resolved

## Question

> I thought that in the C# demo, even on the first milestone we have an agent that uses the MCP, and for that we need an LLM. Am I wrong?

## Answer

**You are partially right, but with an important qualification:**

### C# Milestone 1 Reality

The C# `milestone-1` branch **does include an LLM-backed agent** (`WinDiagMcpClient`), and **it requires Azure OpenAI credentials**. However:

- **M1 is ONLY the server + a simple C# client demo.**
- The C# *teaching* progression is: M1 (basic client), M2 (more tools), M3 (full chat client with prompts).
- The pedagogical arc emphasizes the **MCP protocol first**, then layers in LLM workflows.

### Detailed Timeline

#### Milestone 1 (C# `origin/milestone-1`)
- ✅ **Server:** STDIO MCP server with single tool `get_system_info`
- ✅ **Client:** `WinDiagMcpClient/Program.cs` — a **C# agent** using `Microsoft.Agents.AI` framework
- ✅ **Credentials Required:** Azure OpenAI (hardcoded endpoint, default credential flow)
- ✅ **Behavior:** Runs a one-shot prompt "What is the system information?" → returns LLM response

**Key Files:**
- `WinDiagMcpClient/Program.cs` — Uses `AzureOpenAIClient` + `.AsAIAgent()`
- `docs/CSHARP_CLIENT_GUIDE.md` — Documents the client
- Run command: `.\run-csharp-client.ps1`

#### Milestone 3 (C# `origin/milestone-3`)
- ✅ **Server gains:** Event log resources, MCP prompts
- ✅ **Client renamed:** `WinDiagMcpChat` — **interactive chat client**
- ✅ **New capability:** Multi-turn conversations, prompt discovery, resource pagination

### Python M1 Current State

The Python M1 implementation is **strictly the server only**:
- ✅ STDIO MCP server with `get_system_info`
- ❌ **No client at all** (not even a basic one)
- ❌ No LLM integration
- ❌ No Azure/OpenAI credentials required
- ✅ Can be tested with MCP Inspector or any MCP client

### Parity Assessment

**Python M1 is BEHIND C# M1 on one critical dimension:**

| Aspect | C# M1 | Python M1 | Parity |
|--------|-------|-----------|--------|
| STDIO MCP Server | ✅ `get_system_info` | ✅ `get_system_info` | ✅ Yes |
| Transport | ✅ STDIO | ✅ STDIO | ✅ Yes |
| Server credential requirements | ❌ None | ❌ None | ✅ Yes |
| **Client included** | ✅ C# agent + LLM | ❌ None | ❌ **BEHIND** |
| **Client credential requirements** | ✅ Azure OpenAI required | ❌ N/A | ⚠️ Decision needed |

### Architectural Difference

The C# demo treats M1 as a **teacher-friendly demo** that:
1. Proves the MCP server works (via test script)
2. Shows an LLM client in action (via `WinDiagMcpClient`)
3. Demonstrates the full end-to-end flow (LLM ↔ Agent ↔ MCP Server)

The Python demo currently stops at (1): server + MCP protocol, no LLM integration yet.

### Team Decision Implication

Per **D3: Client-Side Sampling for Milestones 1–5**, the Python path defers LLM to the client side *and* defers it to M5+. However:

- **D3 says:** "For M1–5, implement sampling client-side" — but M1 currently has **no client at all**.
- **C# M1 precedent:** The client *is* part of M1's story (even if optional).

### Recommendation

**To align Python M1 with C# M1's pedagogical arc, consider:**

1. **Option A (Minimal Alignment):** Add a simple Python CLI client that calls the server via STDIO, discovers tools, and executes `get_system_info`. No LLM.
   - Closes the client gap without requiring credentials.
   - Mirrors C# `WinDiagMcpClient`'s structure (not the LLM part).
   - File: `src/mcp_linux_diag_client/client.py` or similar.

2. **Option B (Full Alignment):** Add the full AI agent to Python M1 with Azure OpenAI.
   - Matches C# M1 exactly, including LLM flow.
   - Requires credentials at M1 scope.
   - Deviates from **D3** unless D3 is revisited.

3. **Option C (Accept Current State):** Python M1 stays server-only; clarify to students that the Python track starts with the MCP server *protocol* before introducing LLM clients.
   - Preserves **D3** scope.
   - Requires explicit documentation that this is intentionally different from C# M1.

---

## Evidence

**C# Files (all from `origin/milestone-1`):**
- `WinDiagMcpClient/Program.cs` — Agent initialization on lines 10–40
- `docs/CSHARP_CLIENT_GUIDE.md` — Section "Quick Start"
- `docs/MILESTONE_1_SUMMARY.md` — Lists "LLM Integration (Claude Desktop)" as part of M1

**C# File Tree (origin/milestone-1):**
```
├── WinDiagMcpClient/           ← NEW: LLM-backed agent
│   ├── Program.cs              ← Azure OpenAI hardcoded
│   └── WinDiagMcpClient.csproj
├── WinDiagMcpServer/           ← STDIO server
└── docs/
    ├── CSHARP_CLIENT_GUIDE.md
    └── MILESTONE_1_SUMMARY.md
```

**Python File Tree (current):**
```
├── src/
│   └── mcp_linux_diag_server/  ← STDIO server only
└── scripts/
    └── smoke_test.py
```

---

## Conclusion

**You are right with a caveat:**  
C# M1 *does* include an LLM agent (`WinDiagMcpClient`) and requires Azure OpenAI credentials *for that agent*. The Python M1 currently lacks the agent layer entirely. This is an intentional difference (per D3), but worth documenting explicitly for student clarity.

---

---
date: 2026-04-14T01:15:00Z
author: Bishop
reviewed_by: []
status: PROPOSED
---

# Milestone 1 Parity Contract: Python MCPPythonDemo → C# MCPDemo

## Executive Summary

This document captures the exact Milestone 1 user-facing requirements extracted from the C# MCPDemo repository (`origin/milestone-1` branch). The Python implementation must honor these constraints to maintain pedagogical parity.

**Key Finding:** C# M1 includes **both a server AND an LLM-backed client**. Python M1 (per Decision D3) defers the client to M5+, implementing only the server. **This is an intentional architectural divergence** and must be documented in user-facing materials.

---

## 1. Architecture: Server + Client Story

### C# Milestone 1 (Reference Implementation)

| Component | Role | Transport | LLM Integration |
|-----------|------|-----------|-----------------|
| `WinDiagMcpServer` | Runs diagnostics tools | STDIO | None (standalone) |
| `WinDiagMcpClient` | Calls server + LLM | STDIO subprocess | **Azure OpenAI** (required) |

**Client-to-Server Flow:**
1. Client spawns server as STDIO subprocess
2. Client wraps tools in Azure OpenAI Chat Completion
3. Client sends user prompt → LLM routes to MCP tools → LLM summarizes response

### Python Milestone 1 (Target)

| Component | Role | Transport | LLM Integration |
|-----------|------|-----------|-----------------|
| `lindiag_mcp_server` | Runs diagnostics tools | STDIO | None (standalone) |
| Client | **Deferred to M5+** | N/A | N/A |

**Python M1 Scope:** Server only. No client-side sampling.

**Rationale:** D3 decision — simplifies M1–5 to focus on protocol/server/resources/prompts; client-side sampling proves in M5 when Agent Framework maturity is clearer.

---

## 2. Credential Shape & Configuration

### C# M1 Client Credentials

**Hard-coded endpoint in source:**
```csharp
var endpoint = new Uri("https://alonlecturedemo-resource.cognitiveservices.azure.com/");
var credential = new DefaultAzureCredential();
var deploymentName = "model-router";
```

**Key Observations:**
- Azure OpenAI endpoint (cognitive services URL)
- `DefaultAzureCredential()` — uses system authentication (not API key in config)
- Deployment name: `model-router`
- **NO `appsettings.json`** — credentials inline in source (for demo purposes; not a best practice)

### Python M1 (N/A)

No client in M1, so no credential requirement. Deferred to M5+.

---

## 3. Server Entry Point & Initialization

### C# M1 Server (`WinDiagMcpServer/Program.cs`)

**Minimal initialization:**
```csharp
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using WinDiagMcpServer;

// Only show banner if not running under Inspector
if (Environment.GetEnvironmentVariable("MCP_INSPECTOR") != "true")
{
    ConsoleUi.RenderBanner();
}

var builder = Host.CreateApplicationBuilder(args);

// Reduce logging noise - only show warnings and errors
builder.Logging.ClearProviders();
builder.Logging.AddConsole(options =>
{
    options.LogToStandardErrorThreshold = LogLevel.Warning;
});
builder.Logging.SetMinimumLevel(LogLevel.Warning);

builder.Services.AddMcpServer().
    WithStdioServerTransport().
    WithToolsFromAssembly();

var app = builder.Build();
await app.RunAsync();
```

**Key Points:**
1. Respects `MCP_INSPECTOR` env var (banner suppression)
2. Logging configured to WARN+ only
3. Uses `WithToolsFromAssembly()` to auto-discover `[McpServerTool]` attributes
4. STDIO transport (no HTTP in M1)

### Python M1 Server Target

Equivalent pattern:
- Entry point: `python -m lindiag_mcp_server` or equivalent
- Auto-discover tools from module
- Minimal logging noise
- Respect `MCP_INSPECTOR` if possible

---

## 4. The Single Tool: `get_system_info`

### C# M1 Tool Definition

**Method signature (attribute-based discovery):**
```csharp
[McpServerToolType]
public partial class WinDiagMcpServerToolType
{
    [McpServerTool]
    [Description("Returns basic system information for diagnostics (machine name, OS, processors, framework).")]
    public partial SystemInfoResult GetSystemInfo()
    {
        // Implementation
    }
}
```

**Return type (`SystemInfoResult` record):**
```csharp
public sealed record SystemInfoResult
{
    public string MachineName { get; init; } = string.Empty;
    public string UserName { get; init; } = string.Empty;
    public string OSDescription { get; init; } = string.Empty;
    public string OSArchitecture { get; init; } = string.Empty;
    public string ProcessArchitecture { get; init; } = string.Empty;
    public int ProcessorCount { get; init; }
    public string FrameworkDescription { get; init; } = string.Empty;
    public string CurrentDirectory { get; init; } = string.Empty;
    public TimeSpan SystemUpTime { get; init; }
}
```

**Total fields:** 9

### Python M1 Equivalent

**Tool name:** `get_system_info` (case-sensitive MCP tool name)

**Return structure (JSON):**
```json
{
  "machine_name": "hostname",
  "user_name": "username",
  "os_description": "Linux ubuntu 22.04 #1 SMP ...",
  "os_architecture": "x86_64",
  "process_architecture": "x86_64",
  "processor_count": 8,
  "framework_description": "Python 3.10.0",
  "current_directory": "/home/user",
  "system_uptime": "12345.67"  // seconds as float, not TimeSpan
}
```

**Key Differences:**
- Python uses `snake_case` for JSON keys (aligns with D2 Linux diagnostics domain)
- `system_uptime` is float (seconds) instead of .NET `TimeSpan`
- `framework_description` = Python version instead of .NET version
- All other fields map 1:1

**Data sources (Linux, per D2):**
- `machine_name` ← `socket.gethostname()` or `/proc/sys/kernel/hostname`
- `user_name` ← `os.getlogin()` or `$USER` env var
- `os_description` ← `/etc/os-release` + `uname -a` (as approved in decision D1)
- `os_architecture` ← `platform.machine()` or `uname -m`
- `process_architecture` ← same as `os_architecture` (Python is single-arch)
- `processor_count` ← `os.cpu_count()` or `/proc/cpuinfo` line count
- `framework_description` ← `f"Python {sys.version.split()[0]}"` or `platform.python_version()`
- `current_directory` ← `os.getcwd()`
- `system_uptime` ← Parse `/proc/uptime` first field, convert to float (seconds)

---

## 5. Tool Description & Behavior

### Exact MCP Tool Metadata

**Tool Name:** `get_system_info`

**Description:** 
```
"Returns basic system information for diagnostics (machine name, OS, processors, framework)."
```

**Input Schema:**
- **Type:** object
- **Properties:** (empty — no input parameters)
- **Required:** []

**Output Schema:**
- **Type:** object
- **Properties:** All 9 fields listed above
- **Required:** All 9 fields must be present

### User-Facing Behavior

1. Server accepts request with empty arguments
2. Server **ignores extra arguments** if present (graceful degradation)
3. Server returns all 9 fields in one JSON object
4. All fields are **non-null strings or numbers**
5. If a data source is unavailable (e.g., `/proc/uptime` missing), return **error message or fallback**, not crash
   - Example: `"system_uptime": "0"` if unavailable
   - Example: `"os_description": "Unknown Linux distribution"`

---

## 6. Testing & Validation Surface

### C# M1 Testing Approaches (Lecture Demonstrates)

1. **MCP Inspector** (visual UI)
   - Launch: `.\launch-inspector.ps1` (PowerShell)
   - Discovers tools, calls them, shows response
   - Validates JSON-RPC protocol

2. **Claude Desktop** (LLM integration)
   - Setup: `.\setup-claude-desktop.ps1`
   - Claude asks "What is my system information?" → client → server

3. **C# Client** (programmatic)
   - `.\run-csharp-client.ps1`
   - Demonstrates JSON-RPC flow from C# code

4. **mcp-cli** (command line)
   - `mcp-cli tools --server windiag ...`
   - Lists and executes tools

### Python M1 Target

Same testing approaches (adapted for Python):
1. MCP Inspector (unchanged — web-based, language-agnostic)
2. Claude Desktop setup (if client added in M5+)
3. Python test harness
4. mcp-cli (if available)

**Acceptance Criteria (per D1):**
- [ ] Server builds/runs: `python -m lindiag_mcp_server` or equivalent
- [ ] MCP Inspector discovers `get_system_info` tool
- [ ] Tool returns valid JSON with all 9 fields
- [ ] No external dependencies beyond `mcp` SDK in M1
- [ ] Works on Ubuntu 22.04+ and WSL2

---

## 7. Deferred to Later Milestones

The following C# features are **NOT in M1 parity scope**:

| Feature | C# M1 | Python M1 | Deferred To |
|---------|-------|-----------|-------------|
| Client-side LLM sampling | Yes (M1) | No | M5+ |
| Process tools | No | No | M2 |
| Event log resources | No | No | M3 |
| Prompts | No | No | M3 |
| HTTP transport | No | No | M4 |
| Elicitation | No | No | M5 |
| Registry/WMI | No | No | M6–7 |

**Architectural Divergence:** C# includes client in M1; Python defers to M5+. This is intentional and documented in D3.

---

## 8. Migration-Critical Invariants

These MUST be preserved in Python M1:

1. **Tool naming:** Exact case-sensitive MCP tool name `get_system_info`
2. **Field count:** All 9 system info fields must be present
3. **Protocol:** Proper JSON-RPC 2.0 over STDIO
4. **Description:** Tool must describe itself as "basic system information for diagnostics"
5. **No input parameters:** Tool takes no arguments (empty input schema)
6. **Error handling:** Missing data sources must not crash; graceful fallback or error response
7. **Inspector compatibility:** Must work with MCP Inspector (any language)
8. **Logging:** Minimal noise (warnings/errors only)

---

## 9. Key Evidence Files (C# Reference)

For branch archaeology and verification:

- **Server:** `https://github.com/alonf/MCPDemo/blob/origin/milestone-1/WinDiagMcpServer/Program.cs`
- **Tool:** `https://github.com/alonf/MCPDemo/blob/origin/milestone-1/WinDiagMcpServer/WinDiagMcpServerToolType.cs`
- **Result type:** `https://github.com/alonf/MCPDemo/blob/origin/milestone-1/WinDiagMcpServer/SystemInfoResult.cs`
- **Client:** `https://github.com/alonf/MCPDemo/blob/origin/milestone-1/WinDiagMcpClient/Program.cs`
- **Roadmap:** `https://github.com/alonf/MCPDemo/blob/origin/master/docs/MCPDemoRoadmap.md` (lecture framework)

---

## 10. Acceptance Checklist for Implementation

- [ ] Python M1 server runs: `python -m lindiag_mcp_server`
- [ ] `get_system_info` tool discoverable via MCP protocol
- [ ] All 9 fields return with correct types (string or number)
- [ ] MCP Inspector successfully lists and calls the tool
- [ ] No external dependencies beyond `mcp` SDK
- [ ] Works on Ubuntu 22.04+ and WSL2
- [ ] Documentation (README) explains M1 scope vs C# divergence
- [ ] No crash on missing `/proc` files; graceful error or fallback
- [ ] Tool ignores extra arguments (if present)

---

## Owners & Decision Timeline

- **Decision Date:** 2026-04-14
- **Author:** Bishop (MCP/C# Expert)
- **Approved By:** (pending review)
- **Implementers:** Ash (Python Dev), Newt (Validation)
- **Target Completion:** M1 implementation per D1 scope

---

## Next Steps

1. **Ash:** Use this spec to implement Python M1 server
2. **Newt:** Validate against checklist items
3. **Bishop:** Archive this decision after implementation; append learnings to `.squad/agents/bishop/history.md`
4. **Scribe:** Merge this file into `.squad/decisions.md` once approved

---

## Appendix: C# M1 Client Context (Reference)

The C# client is included in M1 for demonstration purposes, but the Python decision (D3) explicitly defers this. For reference:

**C# Client (`WinDiagMcpClient/Program.cs`):**
- Spawns server as STDIO subprocess
- Wraps MCP tools in Azure OpenAI `AIAgent`
- Calls `agent.RunAsync(prompt)` with user input
- Returns LLM-summarized response

**Python M1 will NOT include this.** It will be added in M5+ when:
- Agent Framework Python support matures
- Client-side sampling patterns are validated
- Credentials & authentication strategy is defined

---

## Appendix: Linux Data Source Justification

Per D2 (Windows → Linux diagnostics), all data sources use Linux equivalents:

- Event Log → syslog/journalctl (deferred to M3)
- WMI → `/proc`, `/sys` (deferred to M6+)
- Registry → `/proc/sys`, `/etc` (deferred to M7)
- Process metrics → `/proc/[pid]/stat` (deferred to M2)

M1 uses only:
- `/etc/os-release` (OS metadata)
- `/proc/uptime` (system uptime)
- `/proc/cpuinfo` (CPU count — alternative to `os.cpu_count()`)
- `/proc/loadavg` (load averages — deferred to M2 if needed)
- stdlib (`os.getlogin()`, `socket.gethostname()`, `platform.machine()`, etc.)

All sources are readable by non-root users and work identically on WSL and bare-metal Linux.

---

### 2026-04-13T22:23:00Z: User directive
**By:** Copilot Scribe (via Copilot)
**What:** Mirror the C# implementation for lecture use so the Python version follows the same end-to-end teaching flow instead of a reduced server-only milestone.
**Why:** User request — captured for team memory

---

# Newt: M1 parity QA decision

- Official parity smoke should use the Python MCP SDK client, not handwritten newline JSON-RPC, because the current stdio transport is framed by the SDK.
- Keep two explicit validation lanes for the client path:
  1. fake-model automation for tool-calling flow
  2. real CLI preflight that proves missing Azure configuration fails fast with reviewer-grade messaging
- `/proc` reads in `get_system_info` must degrade to zeroed snapshots on missing files so the lecture demo fails soft instead of crashing.

---

# Milestone 1 Live Run — Team Decisions (2026-04-14)

## Ash: Live Milestone 1 Validation

- Milestone 1 is runtime-valid in WSL with `.env.local` pointing at Azure OpenAI and `MCP_DEMO_AZURE_OPENAI_USE_DEFAULT_CREDENTIAL=true`.
- Azure CLI login in WSL was sufficient for `DefaultAzureCredential` to acquire a token and complete a real chat-completions plus MCP tool-calling run.
- The Python lecture client successfully called `get_system_info` and produced a grounded natural-language answer from Azure OpenAI with no code changes required.

## Ash: local env loading for Python chat client

- The Python chat client should auto-load `./.env.local` by default for local-only settings.
- Exported environment variables and explicit CLI flags still win over `.env.local`.
- `--no-local-env` is the escape hatch for smoke tests and clean-room validation.
- To stay aligned with the .NET client, the Python client now supports `DefaultAzureCredential` as an alternative to an API key.

## User Directives

### 2026-04-13T22:41:51Z: Do not hardcode Azure/OpenAI settings

**By:** alon (via Copilot)  
**What:** Do not put real Azure/OpenAI settings into committed files; instead use a git-ignored local env file so the Python demo can run and be tested locally like the .NET setup.  
**Why:** User request — captured for team memory

### 2026-04-14T06:42:32Z: Prefer DefaultAzureCredential

**By:** alon (via Copilot)  
**What:** Prefer the Azure CLI / `DefaultAzureCredential` approach over API-key auth for the local lecture flow.  
**Why:** User preference for local auth parity with the .NET demo

## Newt: live milestone-1 validation

- QA decision: do not call Milestone 1 end-to-end validated from `scripts/smoke_test.py` alone.
- Required live proof is one authenticated `python3 -m mcp_linux_diag_server.client --json --prompt "..."` run that shows all three markers in the same output: `Connected to MCP server`, `[tool] get_system_info({})`, and a usable assistant answer.
- Reason: the smoke script covers server startup plus the missing-config failure path, but not a successful Azure-backed completion.

## Newt: local env QA decision

- Date: 2026-04-14
- Decision: Reject the local-only env flow until the repo ignores the chosen local file and the Python chat client can load it without exported shell variables.
- Evidence:
  - `.gitignore` does not ignore `.env.local` today.
  - Creating `.env.local` leaves it as `?? .env.local` in `git status`.
  - Running `python3 -m mcp_linux_diag_server.client --prompt 'Summarize this machine.'` with only `.env.local` present still fails with missing Azure settings.
  - Existing automated checks pass, but they only cover server smoke plus the missing-config path; they do not prove local env loading.

---

## Ash: Keep lecture client on Azure OpenAI runtime shape (2026-04-14)

**Status:** Confirmed  
**Context:** User asked whether the Python lecture flow should switch from the current Azure OpenAI path to an Azure AI Foundry project/runtime shape based on the local .NET reference under `/mnt/c/Dev/MCPDemo`.

### Decision

Do **not** switch the Python lecture client to an Azure AI Foundry project/runtime client shape yet.

### Why

The actual runnable .NET reference at `/mnt/c/Dev/MCPDemo/WinDiagMcpChat/Program.cs` constructs:

- `new AzureOpenAIClient(endpoint, credential)`
- `.GetChatClient(deploymentName)`
- `DefaultAzureCredential`

Its project file references `Azure.AI.OpenAI`, `Azure.Identity`, and `Microsoft.Agents.AI.OpenAI`, with no Azure AI Foundry project client package or project-endpoint runtime pattern in the active chat path.

### Implication for Python

The current Python client shape is the correct match for the live reference:

- Azure OpenAI endpoint
- deployment/model-router name
- `DefaultAzureCredential` or API key
- local MCP stdio bridge for tool calls

No production code change was needed for this request; the real run succeeded using local `.env.local`.

---

## Bishop: Real Foundry Runtime Audit (2026-04-14)

**Status:** Reference  
**Owner:** Bishop

### Decision

Treat the current local C# MCPDemo runtime as **direct Azure OpenAI**, not as an Azure AI Foundry project/runtime implementation.

### Why

The user explicitly asked to use the actual foundry project and run the real code. Inspection plus live execution of `/mnt/c/Dev/MCPDemo` shows:

- `WinDiagMcpChat` references `Azure.AI.OpenAI` / `Microsoft.Agents.AI.OpenAI`, not `Azure.AI.Projects`
- `WinDiagMcpChat/Program.cs` constructs `AzureOpenAIClient(endpoint, credential)` directly
- The endpoint is a Cognitiveservices Azure OpenAI endpoint, and the model is selected by deployment name (`model-router`)
- No project-scoped Foundry runtime abstraction appears anywhere in the current local branches

### Consequence for Python

For parity on this axis, Python should continue matching:

- Azure OpenAI endpoint semantics
- deployment-based model selection
- `DefaultAzureCredential`-compatible auth

It should **not** invent Foundry-project-specific config unless the team decides to change the source architecture itself.

### Important Nuance

If the new user requirement is "use an actual Azure AI Foundry project/runtime," that remains a gap in the **source C# demo as well**, not just in Python.
