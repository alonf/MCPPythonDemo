---
date: 2026-04-14T16:45:00Z
author: Bishop
phase: Milestone 5 Analysis
status: Complete
---

# C# Milestone 5 → Python Milestone 5 Feature Delta Analysis

## Executive Summary

**C# Milestone 5** introduces **destructive process termination with mandatory user confirmation** via MCP elicitation protocol. This is a major pedagogical shift: from read-only tools (M1–4) to a write operation that requires **explicit user consent** before execution.

**Parity-critical scope:** One new tool (`KillProcess`) + elicitation flow + result marshaling.  
**Optional enhancements:** Client-side prompt discovery and resource pagination ergonomics (nice-to-have, not blocking).  
**Package updates:** NuGet version bumps only; no architectural changes.

---

## Detailed Delta

### 1. New Server Tool: `KillProcessAsync`

**Location (C#):** `WinDiagMcpServer/Tools/Process/McpServerProcessToolType.cs` (lines ~130–300)

**Method Signature:**
```csharp
public async Task<KillProcessResult> KillProcessAsync(
    McpServer server,
    int? processId = null,
    string? reason = null,
    CancellationToken cancellationToken = default)
```

**Core Behavior:**
1. **Validate client capability:** Checks `server.ClientCapabilities?.Elicitation?.Form` — throws if unsupported
2. **Two-stage elicitation:**
   - **Stage 1 (if no processId provided):** Show top-5 CPU consumers via form selection elicitation; user picks one from dropdown
   - **Stage 2 (mandatory):** Request typed confirmation phrase (`CONFIRM PID {pid}`) to prevent accidental kills
3. **Process termination:** Call `process.Kill(true)` (graceful tree kill on Windows)
4. **Result marshaling:** Return typed `KillProcessResult` with status (terminated/cancelled/not-found/failed)

**Pedagogical Goal:** Teach MCP elicitation pattern — server-initiated dialogs to gather user intent before destructive actions.

### 2. New Result Type: `KillProcessResult` (record)

**Location (C#):** `WinDiagMcpServer/Tools/Process/KillProcessResult.cs` (new file)

**Fields:**
- `ProcessId` (int)
- `ProcessName` (string)
- `Status` (string): "terminated" | "cancelled" | "not-found" | "failed"
- `Message` (string): human-readable outcome
- `Reason` (string?): optional user-provided rationale

**Factory Methods:**
- `Success(processId, processName, reason)`
- `Cancelled(message)`
- `NotFound(processId)`
- `Failed(processId, processName, errorMessage)`

### 3. New Supporting Type: `ProcessCpuUsage` (class)

**Location (C#):** `WinDiagMcpServer/Tools/Process/ProcessCpuUsage.cs` (new file)

**Fields:**
- `ProcessId` (int)
- `ProcessName` (string)
- `WorkingSet` (long): memory in bytes
- `CpuPercent` (double): computed during elicitation

**Purpose:** Encapsulates top-CPU process metadata for form elicitation dropdown population.

### 4. Elicitation Helper Methods (C#)

Three private async methods in `McpServerProcessToolType`:

- **`SampleTopCpuProcessesAsync(take, cancellationToken)`:** Captures process snapshots before and after a 750ms delay; calculates CPU % via time-delta sampling; returns top N by CPU then RAM
- **`ElicitProcessSelectionAsync(server, cancellationToken)`:** Builds MCP elicitation form with ProcessCandidate options; user selects one; returns chosen `ProcessCandidate`
- **`ElicitConfirmationAsync(server, processCandidate, cancellationToken)`:** Builds text-input form requesting typed confirmation phrase; validates exact match (case-insensitive)

**Critical Details:**
- CPU sampling: `(cpuDelta.TotalMilliseconds) / (interval.TotalMilliseconds * processorCount) * 100`
- Confirmation phrase: case-insensitive comparison; must match exactly
- Timeout handling: 5-second wait for process exit after `Kill(true)`

### 5. Client Enhancements (C# M5)

**WinDiagMcpChat/Program.cs** gains:

- **Internal function: `ReadMcpResource(resourceUri)`** — reads MCP resource URLs with pagination support (query param extraction)
- **Internal function: `GetMcpPromptContentAsync(promptName, argumentsJson)`** — retrieves named prompts from server
- **AI instructions upgrade:** Detailed workflow guidance on prompt discovery, resource pagination, form elicitation response handling
- **Prompt discovery:** Fetches available prompts on startup; populates agent instructions with prompt list for context
- **Session management:** `agent.CreateSessionAsync()` for multi-turn history (MAF 1.1.0+ feature)

**Rationale:** Clients need to understand how to **trigger** and **handle** elicitation responses; prompt discovery teaches pipeline orchestration.

### 6. Program.cs (Server) Changes

**File:** `WinDiagMcpServer/Program.cs` — minimal change

Added import:
```csharp
using WinDiagMcpServer.Resources.EventLog;
```

(This was probably missing in M4 but required for M5 due to assembly scanning. No functional impact.)

### 7. Package Upgrades (Both Projects)

**NuGet versions bumped:**
- `ModelContextProtocol`: 0.5.0-preview.1 → 1.2.0
- `ModelContextProtocol.AspNetCore`: 0.5.0-preview.1 → 1.2.0
- `Microsoft.Agents.AI.OpenAI` (MAF): 1.0.0-preview → 1.1.0
- `Azure.AI.OpenAI`: 2.7.0-beta.2 → 2.9.0-beta.1
- `Azure.Identity`: 1.18.0-beta.2 → 1.21.0

**Breaking change in MAF 1.1.0:**
- `CreateAIAgent()` → `AsAIAgent()` (extension method)
- `GetNewThread()` → `CreateSessionAsync()`
- Added: `using OpenAI.Chat`

---

## Parity-Critical Invariants for Python M5

### Must Implement

1. **`kill_process` Tool**
   - Async method, accepts optional `process_id` and optional `reason`
   - Returns typed `KillProcessResult` (dict with fields: `process_id`, `process_name`, `status`, `message`, `reason`)
   - Enforces **two-stage elicitation** if no PID provided; **mandatory confirmation** if PID is given
   - Status values must match: `"terminated"`, `"cancelled"`, `"not-found"`, `"failed"`

2. **Elicitation Protocol Support**
   - Server must check `ClientCapabilities.Elicitation?.Form` (or equivalent in Python SDK)
   - If unsupported, raise error: `"Client does not support elicitation. A client that can fulfill form elicitation is required for killProcess."`
   - Form elicitation must use **server-side `ElicitAsync()` call** with `RequestedSchema` containing form options

3. **Top-CPU Process Sampling**
   - Capture process snapshots (PID, name, working set, total CPU time) at T0
   - Delay 750ms
   - Capture snapshot at T0 + 750ms
   - Calculate CPU % per process: `(cpu_delta_ms) / (750ms * core_count) * 100%`
   - Rank by CPU % descending, then RAM descending
   - Return top 5 as form options

4. **Confirmation Workflow**
   - After user selects process, request typed confirmation: `CONFIRM PID {pid}`
   - Comparison must be case-insensitive
   - Only proceed if exact phrase match + action="accept"

5. **Process Termination**
   - Use OS-native kill (Linux: `signal.SIGTERM` or `kill -15`, then check/wait)
   - Log reason if provided
   - Return `KillProcessResult.Success()` on clean exit, `Failed()` if exception

### Optional Enhancements

1. **Client-side Prompt Discovery** (deferred to M6+)
   - Python client can fetch prompt list on startup
   - Display in instructions for multi-tool orchestration

2. **Resource Pagination Ergonomics** (already in M3+)
   - Client should parse `?limit=N&offset=M` from resource URIs
   - Handle pagination loop for large snapshots

---

## Mapping to Linux Diagnostics

### ProcessCandidate ↔ Linux Process Data

| C# Field | Linux Source | Method |
|----------|--------------|--------|
| `ProcessId` | PID from `/proc` or `os.popen('ps')` | Direct |
| `ProcessName` | Process name from `/proc/[pid]/comm` | File read |
| `WorkingSet` | RSS from `/proc/[pid]/status` | File parse |
| `CpuPercent` | Time delta: `/proc/[pid]/stat` `utime + stime` | Sampling |

### Sampling Logic (750ms interval)

```
T0: {pid1: utime+stime=100, pid2: utime+stime=50, ...}
Wait 750ms
T1: {pid1: utime+stime=200, pid2: utime+stime=60, ...}
Δcpu_pid1 = 200-100 = 100ms
cpu%_pid1 = (100ms / 750ms / num_cpus) * 100
```

### Termination

- Use `signal.SIGTERM` (equivalent to Windows "graceful kill")
- Wait 5 seconds for process exit
- Fallback to `signal.SIGKILL` if not exited

---

## MCP Elicitation in Detail (C# Implementation Reference)

### Form Elicitation Schema (Process Selection)

```csharp
var schema = new RequestSchema
{
    Properties = {
        ["process"] = new TitledSingleSelectEnumSchema {
            Title = "Process",
            Description = "Select the process you want to terminate.",
            OneOf = [
                { Const = "1234", Title = "firefox (PID 1234) • CPU 45.2% • RAM 512 MB" },
                { Const = "5678", Title = "chrome (PID 5678) • CPU 32.1% • RAM 1.2 GB" },
                ...
            ]
        }
    }
};

var response = await server.ElicitAsync(
    new ElicitRequestParams {
        Message = "Select one of the top CPU consumers to terminate. Only a handful are shown for safety.",
        RequestedSchema = schema
    },
    cancellationToken);

// response.Action = "accept" | "reject"
// response.Content = { "process": "<selected_pid>" }
```

### Text Confirmation Schema

```csharp
var schema = new RequestSchema
{
    Properties = {
        ["confirmation"] = new StringSchema {
            Title = "Confirmation Phrase",
            Description = "Type 'CONFIRM PID 1234' to confirm termination.",
            MinLength = 16  // length of "CONFIRM PID 1234"
        }
    }
};

// User must type exact phrase to proceed
```

---

## No Breaking Changes to Existing Tools

- `get_system_info`: Unchanged
- `get_process_list`: Unchanged
- `get_process_by_name`: Unchanged
- `get_process_by_id`: Unchanged
- Event log tools: Unchanged
- Resources: Unchanged
- Prompts: Unchanged

---

## Integration Notes

### Python MCP SDK Considerations

1. **Elicitation API:** Ensure Python `mcp` SDK version supports server-side `elicit()` or equivalent
2. **Async/await:** `KillProcessAsync` is async; Python should use `async def`
3. **ClientCapabilities check:** Python server will receive client capabilities in handshake; check for elicitation form support
4. **Cancellation:** Use Python `asyncio.CancelledError` equivalently

### Client (Optional M5 Enhancement)

If Python client is enhanced in M5:
- Parse `/mcp/prompts` endpoint to list available workflows
- Display in instructions for LLM context
- Support form elicitation response parsing

---

## Validation Strategy

### Acceptance Tests

1. **Tool discovery:** Inspector/CLI shows `kill_process` tool with correct parameters
2. **No elicitation client:** Server rejects call with appropriate error
3. **Process selection:** Form elicitation shows top 5 CPU processes; user selects one
4. **Confirmation:** Text form requests confirmation phrase; typo fails; exact match succeeds
5. **Termination:** Process exits cleanly; result status = "terminated"
6. **Cancellation:** User rejects elicitation at any stage; status = "cancelled"
7. **Not found:** Invalid PID returns status = "not-found"
8. **Error handling:** Permission denied / race condition returns status = "failed" with message

---

## Decision: Parity Required?

**YES — FULLY PARITY-CRITICAL**

The `kill_process` elicitation workflow is **the pedagogical core of M5**: it teaches MCP clients that servers can drive workflows, not just respond to requests. Skipping this would miss the conceptual progression that C# M5 demonstrates.

**Slight divergence OK:** Linux-specific process sampling (use `/proc` instead of Win32 APIs) and signal semantics (SIGTERM vs graceful tree kill) are acceptable as long as behavior is equivalent.

---

## Learnings for Scribe

- M5 is the **first destructive operation** in the series; elicitation enables safe LLM automation
- CPU sampling requires time-delta calculation; must be fast (750ms) to avoid user wait
- Confirmation phrase must be exact (case-insensitive) to prevent accidental kills
- Client enhancements (prompt discovery, pagination) are ergonomic but not blocking for core M5
- MAF 1.1.0 breaking changes (`AsAIAgent`, `CreateSessionAsync`) affect C# client startup code but not server protocol

---

## Files Modified in C# M5

**Server:**
- `WinDiagMcpServer/Program.cs` (+1 import)
- `WinDiagMcpServer/Tools/Process/McpServerProcessToolType.cs` (~170 lines added: `KillProcessAsync`, elicitation helpers, sampling)
- `WinDiagMcpServer/Tools/Process/KillProcessResult.cs` (NEW: ~60 lines)
- `WinDiagMcpServer/Tools/Process/ProcessCpuUsage.cs` (NEW: ~25 lines)
- `WinDiagMcpServer/WinDiagMcpServer.csproj` (version bumps only)

**Client:**
- `WinDiagMcpChat/Program.cs` (~7KB added: prompt discovery, internal resource/prompt functions, elicitation-aware instructions)
- `WinDiagMcpChat/WinDiagMcpChat.csproj` (version bumps only)

**Total added lines:** ~250 (server) + ~500 (client) = ~750 lines; mostly elicitation orchestration and prompt discovery.

---

## Recommendation

Implement M5 as a **full parity milestone**. The elicitation pattern is central to MCP pedagogy and cannot be deferred without losing the conceptual thread.

**Timeline estimate:** 2–3 days (assuming Linux process inspection utilities are battle-tested).

**Risk factors:**
- Async elicitation timeout handling
- Process CPU calculation precision (750ms sampling may vary by machine load)
- Permission denied handling (non-root kill attempts)

**Mitigation:** Comprehensive test harness with mock elicitation client to validate form schema and response parsing before live testing.

