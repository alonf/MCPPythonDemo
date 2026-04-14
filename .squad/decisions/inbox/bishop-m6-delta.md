# Bishop: Milestone 6 Parity-Critical Delta Analysis

**Decision by:** Bishop (MCP/C# Expert)  
**Date:** 2026-04-14  
**Status:** Complete Analysis for Implementation  

---

## Executive Summary

Milestone 6 in the C# MCPDemo introduces **sampling-assisted WMI troubleshooting**, replacing the previous generic "system health report" concept. The parity-critical delta consists of:

1. **`TroubleshootWithWmi(userRequest)` tool**: A new MCP tool that orchestrates a two-phase sampling workflow:
   - Phase 1: Sample an LLM to generate a safe WMI query from the user's natural-language request
   - Phase 2: Execute the query and sample the LLM again to summarize results back to the user

2. **Prompt guidance**: New `WmiTroubleshootingPrompt` directs agents toward the new tool

3. **Client-side sampling support**: The chat client now advertises `SamplingCapability` and implements `SamplingHandler` to let the server invoke the LLM on the client's behalf

4. **WQL validation guardrails**: Strict server-side checks prevent sampling-generated queries from using unsafe constructs (JOIN, UNION, GROUP BY, subqueries)

---

## The Feature: Sampling-Assisted WMI Troubleshooting

### Architecture (C# Milestone 6)

```
User Request (natural language)
  ↓
[MCP Tool: TroubleshootWithWmi]
  ├─ Phase 1: Sample LLM → "generate safe WQL query"
  │  (server provides constraints, retries on validation failure)
  │
  ├─ Validate WQL output (C# Wql class)
  │  Blocks: JOIN, UNION, GROUP BY, HAVING, ORDER BY, WITH, subqueries
  │  Requires: single SELECT line, starts with SELECT, no semicolons
  │
  ├─ Execute query via RunWmiQuery (internal tool, not exposed to MCP)
  │
  └─ Phase 2: Sample LLM → "summarize WMI results for user"
     (returns natural-language diagnosis)
```

### Why This Matters Pedagogically

- **Sampling is a bridge pattern**: The server calls out to the client's LLM (via MCP protocol) instead of embedding an LLM in the server itself.
- **Elicitation vs. Sampling**: M5 introduced elicitation (user approval for destructive actions); M6 adds sampling (LLM-as-a-subroutine for reasoning tasks).
- **Composability**: The same pattern extends to future domains (registry, event logs) — any data source can ask for sampling to guide query generation or result interpretation.

---

## Parity-Critical Code Elements

### 1. Tool Definition: `troubleshoot_with_wmi` 

**Type:** Async MCP tool (requires server-side coroutine)

**Input:**
```json
{
  "userRequest": "string (e.g., 'Show me disk space usage')"
}
```

**Output:**
```json
"string (natural-language diagnosis)"
```

**Behavior:**
- Accept user's natural-language problem description
- Loop up to 4 times (max retry attempts):
  - Send sampling request with base prompt + prior validation error
  - Validate WQL output strictly
  - If valid, break; if invalid, store error message and retry
- Execute the validated WQL query
- Send sampling request to summarize results
- Return summarized diagnosis

### 2. Sampling Protocol Requirements

The server must use `server.SampleAsync(CreateMessageRequestParams)` with:

```csharp
new CreateMessageRequestParams
{
    MaxTokens = 180,
    SystemPrompt = "You generate WQL only. Do not use tools. ...",
    Messages = [new SamplingMessage { Role = Role.User, Content = [...] }]
}
```

The client must:
- Advertise `SamplingCapability()` in its `ClientCapabilities`
- Register a `SamplingHandler` in `McpClientHandlers`
- The handler must accept `CreateMessageRequestParams` and return `CreateMessageResult`

### 3. WQL Validation (Server-Side Authority)

```
Input: Raw LLM output (may include markdown code fences, prose, etc.)

Sanitization:
  Remove: ```wql, ```sql, ``` (markdown artifacts)
  Trim whitespace

Parsing:
  Split by newlines, trim each line
  Must have exactly 1 line

Content Validation:
  Must start with SELECT (case-insensitive)
  Must not contain ; (semicolons)
  Must not contain: join, union, group by, having, order by, with, from (, select (
  
Output: Valid WQL query string or validation error message
```

**Why strict validation:** Sampling can hallucinate. The server is the authority and must refuse unsafe queries before execution.

### 4. Prompt Guidance: `TroubleshootComponent`

The new prompt does NOT appear in the C# M6 tool list (it's a passive resource). But its role is to guide agents toward `troubleshoot_with_wmi` instead of generic tools.

**Example output:**
```
You are a Windows Internals Specialist.
The user wants a deep inspection of: Logical Disks.

WORKFLOW:
1. DO NOT use the generic diagnose_system_health prompt.
2. DO NOT use standard process or event log tools.
3. You MUST use the TroubleshootWithWmi tool.
...
```

---

## Optional Convenience (Not Parity-Critical)

1. **Code organization (regions)**: The C# M6 chat client uses `#region`/`#endregion` for readability. This is optional in Python.

2. **NuGet package bump** (`System.Management` v10.0.1): Python has no WMI library in the same sense; equivalent is querying `/proc` and `/sys` files directly. Not a blocker.

3. **Infrastructure logging upgrade**: The C# diff shows a formatter update (`McpConsoleFormatter.cs`). This is logging infrastructure; optional in Python.

---

## Migration Strategy for Python Milestone 6

### Phase 1: Data Source Mapping

Unlike Windows WMI (which queries live system objects), Python M6 must adapt to Linux syscall/proc data sources. Possible approaches:

**Option A (Recommended): Direct `/proc` + `/sys` queries**
- Map user request → `/proc/sys/...` or `/proc/[pid]/...` file path + field
- Example: "Show me dirty pages" → read `/proc/meminfo` line "Dirty:"
- Allows sampling to generate file paths and field names (simpler than WQL)

**Option B: High-level data objects**
- Create internal Python objects (e.g., `MemoryStats`, `ProcessStats`, `DiskStats`)
- Sampling generates method calls or field paths on these objects
- More abstraction; less direct system access

**Option A is preferred** because it mirrors the pedagogical intent: the server asks the LLM to construct a query (in this case, a file path + field name instead of WQL), validates it, and executes it.

### Phase 2: Tool Implementation

```python
async def troubleshoot_with_proc_diagnostics(
    server: McpServer,
    user_request: str,
    cancellation_token: Optional[CancelToken] = None
) -> str:
    """
    Sampling-assisted diagnostics using /proc and /sys data sources.
    
    1. Sample LLM: "From /proc, suggest a file and field to read"
    2. Validate the suggestion (allowlist, permissions, path traversal checks)
    3. Read the file/field
    4. Sample LLM: "Summarize these findings for the user"
    5. Return summary
    """
```

### Phase 3: WQL Validation → Path/Field Validation

**Analogue to WQL constraints:**

```
Input: LLM-suggested data source
  Example: "/proc/meminfo | grep Dirty"
  Example: "/proc/sys/vm/swappiness"

Validation rules (allowlist):
  Allowed root paths:
    - /proc/meminfo (safe, world-readable)
    - /proc/[pid]/stat (safe, world-readable)
    - /proc/sys/vm/* (safe, world-readable)
    - /proc/net/* (safe, world-readable)
    - /proc/cpuinfo (safe, world-readable)
    - /etc/os-release (safe, world-readable)
  
  Forbidden patterns:
    - Path traversal: ..
    - Pipe to external commands: |
    - Shell metacharacters: ;, &, $(), ``, >
    
Output: Normalized path or error
```

### Phase 4: Client Sampling Handler

The Python client must:
- Import `SamplingCapability` from mcp SDK
- Advertise it in client capabilities
- Implement async `sampling_handler` that calls Azure OpenAI directly

---

## Key Learnings for Implementation

### 1. Sampling Differs from Elicitation

- **Elicitation (M5):** Server asks the user (via client UI) for a boolean or form input. Synchronous interaction with the human.
- **Sampling (M6):** Server asks the LLM (via client) for text generation. Async model inference.

Python client must handle both:

```python
class McpClientHandlers:
    elicitation_handler: Optional[async def(ElicitRequestParams) -> ElicitResult]
    sampling_handler: Optional[async def(CreateMessageRequestParams) -> CreateMessageResult]
```

### 2. Server is the Authority

The WML validation is **non-negotiable**. Even though the LLM generates queries, the server must validate before execution. This teaches:
- Servers should never blindly execute LLM output
- Guardrails are essential for untrusted input
- Retries are part of the normal flow

### 3. Prompt Role is Guidance, Not Enforcement

The prompt (`troubleshoot_with_wmi`) does not force the agent to use the tool. It provides context. The agent may ignore it. This is correct — the prompt is pedagogical, not a hard constraint.

---

## Roadmap Update for Python

**Current C# M6 Roadmap Entry (from MCPDemoRoadmap.md):**

```
### Milestone 6 – Sampling-assisted WMI troubleshooting ✅ COMPLETE

* Tool 1: `runWmiQuery(query, pageNumber, pageSize)` ✅ COMPLETE 
  *(internal only; not exposed as a public MCP tool)*
* Tool 2: `troubleshootWithWmi(userRequest)` ✅ COMPLETE
  1. Uses **sampling** to convert natural-language request → safe WML query
  2. Invokes `runWmiQuery` internally to collect data
  3. Calls sampling again to summarize WMI results

Teaching points:
* Sampling for LLM-as-a-subroutine (query synthesis + result summarization)
* Separation between data execution (deterministic tool) and reasoning (sampling steps)
* Demonstrating how elicitation (for missing parameters) and sampling (for AI reasoning) complement each other
```

**Python M6 (Adapted):**

```
### Milestone 6 – Sampling-assisted Linux diagnostics ⏳ PLANNED

* Tool 1: Internal `_query_proc_source(file_path, field_name)` 
  *(private; not exposed as a public MCP tool)*
* Tool 2: Public `troubleshoot_linux_diagnostics(user_request)` 
  1. Uses **sampling** to convert natural-language request → safe /proc path + field
  2. Validates path (allowlist check, no path traversal)
  3. Reads /proc/sys file and extracts field
  4. Calls sampling again to summarize results

Teaching points:
* Same as C#: sampling for LLM-as-a-subroutine pattern
* Elicitation (M5) + Sampling (M6) form a complete AI interaction model
* Domain-agnostic: Windows WMI → Linux /proc; pattern is reusable
```

---

## Non-Blockers: Pre-existing Drift

Python M6 will continue to adapt to Linux without waiting for 1:1 WMI parity:

- No registry (C# M7 feature) → `/proc/sys` + `/etc` substitution
- No event log (C# M3 feature, continued in M6) → journalctl (already in Python)
- No process kill elicitation (C# M5 feature, continued) → Already in Python M5

These are expected domain differences, not parity failures.

---

## Acceptance Criteria for Python M6

1. **Tool `troubleshoot_linux_diagnostics`** is discoverable via MCP tools/list
2. **Input validation:**
   - Accepts natural-language user request
   - Converts to safe /proc path via sampling (with validation)
3. **Execution:**
   - Reads /proc file and extracts field safely
   - Handles permission errors gracefully
4. **Output:**
   - Summarizes findings via sampling
   - Returns natural-language diagnosis
5. **Client sampling:**
   - Chat client advertises `SamplingCapability()`
   - `SamplingHandler` calls Azure OpenAI directly
   - Server can retry on validation failures
6. **Allowlist enforcement:**
   - Rejects path traversal attempts
   - Rejects shell metacharacters
   - Only reads from safe /proc/sys paths

---

## Evidence Files (C#)

- `WinDiagMcpServer/Tools/Wmi/McpServerWmiToolType.cs` (302 lines, 2 public/internal tools)
- `WinDiagMcpServer/Prompts/Wmi/WmiTroubleshootingPromptType.cs` (guidance prompt)
- `WinDiagMcpChat/Program.cs` (SamplingCapability + SamplingHandler)
- `docs/MCPDemoRoadmap.md` (M6 summary)
- Commits: `896d5fa`, `603ec2c`, `da628ad`

---

## Next Steps (Not This Task)

This analysis is inputs for implementation. Actual implementation will be done by Ash (Python Dev) or delegated. This decision captures:

1. **What the feature does** (sampling-assisted diagnostics)
2. **Why it matters** (elicitation + sampling = complete AI interaction model)
3. **How to adapt to Linux** (WQL → /proc paths, same validation pattern)
4. **How to implement in Python** (client SamplingHandler, server validation loop)

The implementation team should use this decision as a spec.

