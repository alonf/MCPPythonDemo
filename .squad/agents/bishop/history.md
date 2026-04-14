# Project Context

- **Owner:** alon
- **Project:** Python Linux Diagnostics demo migrated from the C# MCPDemo repo and lecture
- **Stack:** Python, MCP, Microsoft Agent Framework, Linux diagnostics, `/proc`, Git branches
- **Created:** 2026-04-13T21:30:48.993Z

## Learnings (2026-04-14T01:15Z M1 Parity Extraction)

### C# Milestone 1 Architecture & Credentials

**Finding:** C# M1 contains BOTH `WinDiagMcpServer` (STDIO, single tool) AND `WinDiagMcpClient` (LLM-backed, Azure OpenAI).

**Evidence:**
- `WinDiagMcpServer/Program.cs`: STDIO MCP server with `WithToolsFromAssembly()` auto-discovery
- `WinDiagMcpClient/Program.cs`: Spawns server as subprocess, wraps tools in Azure OpenAI `AIAgent`
- Client hard-codes: `endpoint = "https://alonlecturedemo-resource.cognitiveservices.azure.com/"`
- Client uses: `DefaultAzureCredential()` (system auth, no config file), `deploymentName = "model-router"`
- No `appsettings.json` (credentials inline for demo; not best practice)

**Tool: `get_system_info` (9 fields):**
1. `MachineName` (string)
2. `UserName` (string)
3. `OSDescription` (string)
4. `OSArchitecture` (string)
5. `ProcessArchitecture` (string)
6. `ProcessorCount` (int)
7. `FrameworkDescription` (string — .NET version)
8. `CurrentDirectory` (string)
9. `SystemUpTime` (TimeSpan — converted to float seconds for Python)

**Tool Metadata:**
- Tool name: `get_system_info` (case-sensitive MCP name)
- Input schema: empty (no parameters)
- Description: "Returns basic system information for diagnostics (machine name, OS, processors, framework)."

**Architecture Decision:**
- C# includes client in M1 for end-to-end LLM flow demonstration
- Python defers client to M5+ (D3 decision) — M1 is server-only
- This is intentional architectural divergence, not a gap
- Decision written to `.squad/decisions/inbox/bishop-m1-parity-spec.md`

**Python M1 Linux Data Source Mapping (per D2):**
| Field | Python Source | Method |
|-------|----------------|--------|
| machine_name | `socket.gethostname()` | stdlib |
| user_name | `os.getlogin()` | stdlib |
| os_description | `/etc/os-release` + `platform.system()` | file + stdlib |
| os_architecture | `platform.machine()` | stdlib |
| process_architecture | `platform.machine()` | stdlib (same as OS arch) |
| processor_count | `os.cpu_count()` | stdlib |
| framework_description | `f"Python {sys.version.split()[0]}"` | stdlib |
| current_directory | `os.getcwd()` | stdlib |
| system_uptime | `/proc/uptime` (first field, float) | file read |

All sources are non-root-readable, work on WSL and bare-metal.

---

## Learnings (2026-04-14 Update)

### M1 LLM Agent Parity Discovery

**Question:** Does C# M1 require an LLM?  
**Answer:** Yes. C# M1 includes `WinDiagMcpClient` (LLM-backed agent) + Azure OpenAI integration. Python M1 currently has only the server (intentional per D3).

**Evidence:**
- C# `origin/milestone-1` contains: `WinDiagMcpClient/Program.cs` (uses `Microsoft.Agents.AI` + Azure OpenAI)
- C# `origin/milestone-3` upgrades to: `WinDiagMcpChat/` (interactive chat client)
- Python M1: Server only, no client
- D3 rationale: Defers client-side sampling to M5+; M1–5 focus on server/resources/prompts

**Pedagogical implications:**
- C# students see full end-to-end LLM flow in M1 (client → agent → server)
- Python students see protocol/server first, LLM integration later
- Both approaches are valid; requires explicit documentation of the difference

**Decision written to:** `.squad/decisions/inbox/bishop-m1-llm-parity.md`

---

## Earlier Learnings

- The source of truth for the migration is the C# MCPDemo repository plus the lecture PDF under `docs/`.
- Branch structure matters because the new demo should mirror the branch ideas, not just the final code.
- MCPDemo milestone branches are behavioral snapshots, not a clean linear ancestry; only `milestone-7` is directly carried into `master`, so branch summaries should come from `docs/MCPDemoRoadmap.md` plus per-branch file diffs, not tip commit subjects alone.
- Final C# architecture on `master` is centered on `WinDiagMcpServer/` with `Infrastructure/`, `Tools/{EventLog,Process,Registry,SystemInfo,Wmi}/`, `Resources/{EventLog,Registry}/`, `Prompts/{EventLog,Registry,Wmi}/`, and `Services/RegistryRootsService.cs`; `WinDiagMcpChat/Program.cs` is the companion HTTP MCP client with prompt/resource/elicitation/sampling support.
- Migration-critical invariants to preserve: tool/resource/prompt separation, snapshot resource URIs with pagination (`eventlog://snapshot/{id}`, `registry://snapshot/{id}`), HTTP `/mcp` plus API key behavior from milestone 4 onward, explicit elicitation before destructive actions, server-side guardrails around sampling-generated WMI queries, and allow-listed roots for privileged data access.
- Key evidence files: `docs/MCPDemoRoadmap.md`, `README.md`, `WinDiagMcpServer/Program.cs`, `WinDiagMcpServer/Tools/Process/McpServerProcessToolType.cs`, `WinDiagMcpServer/Tools/EventLog/McpServerEventLogToolType.cs`, `WinDiagMcpServer/Resources/EventLog/McpServerEventLogResourceType.cs`, `WinDiagMcpServer/Tools/Wmi/McpServerWmiToolType.cs`, `WinDiagMcpServer/Tools/Registry/McpServerRegistryToolType.cs`, `WinDiagMcpServer/Services/RegistryRootsService.cs`, and `WinDiagMcpChat/Program.cs`.
- `alonf/MCPDemo` is a cumulative milestone repo: `milestone-1` (STDIO + `get_system_info`), `milestone-2` (process inspection), `milestone-3` (event log resources/prompts + chat client), `milestone-4` (ASP.NET Core HTTP `/mcp` + API key), `milestone-5` (kill-process elicitation), `milestone-6` (sampling-backed WMI), `milestone-7` (registry roots/resources); `master` is essentially `milestone-7` plus demo GIFs under `docs/`.
- Migration-critical server files are `WinDiagMcpServer/Program.cs`, `WinDiagMcpServer/Tools/Process/McpServerProcessToolType.cs`, `WinDiagMcpServer/Tools/EventLog/McpServerEventLogToolType.cs`, `WinDiagMcpServer/Resources/EventLog/McpServerEventLogResourceType.cs`, `WinDiagMcpServer/Tools/Wmi/McpServerWmiToolType.cs`, `WinDiagMcpServer/Tools/Registry/McpServerRegistryToolType.cs`, `WinDiagMcpServer/Services/RegistryRootsService.cs`, and client file `WinDiagMcpChat/Program.cs`.
- The C# design preserves a strong MCP pattern: tools collect data, singleton in-memory storages hold snapshots, resources page those snapshots, and prompts orchestrate multi-tool workflows.
- Important repo drift exists: docs/prompts still mention tool names like `get_all_processes`, `get_process_info`, `read_registry_key`, `list_registry_keys`, and `get_top_cpu_processes`, while current source methods are centered on `GetProcessList`, `GetProcessById`, `CreateRegistrySnapshotAsync`, and `RequestRegistryAccessAsync`.
- The lecture PDF at `docs/Season_of_AI_5_MCP.pdf` explicitly points at `https://github.com/alonf/MCPDemo` and its slide outline covers MCP concepts, Inspector, official C# SDK, Tools demo, Resources demo, and the “Big-7” structure, so the repo is the concrete lecture artifact rather than a separate example.


---

## Learnings (2026-04-14T01:35Z M1 Parity Correction: Source Branch is NOT Server-Only)

### CRITICAL CORRECTION: GitHub alonf/MCPDemo:milestone-1 Includes LLM-Backed Client

Previous Claim (Incorrect): 'C# M1 is server-only.'  
Corrected Truth: 'C# M1 includes both WinDiagMcpServer (STDIO) and WinDiagMcpClient (Azure OpenAI LLM agent).'

Evidence (Raw Code Inspection):

1. WinDiagMcpClient/Program.cs:
   - Imports: Azure.AI.OpenAI, Microsoft.Agents.AI (LLM framework)
   - Hard-codes: endpoint = https://alonlecturedemo-resource.cognitiveservices.azure.com/, deploymentName = model-router
   - Auth: DefaultAzureCredential() (system auth, no config file)
   - Spawns server as subprocess via StdioClientTransport
   - Wraps tools in AIAgent
   - Calls LLM: agent.RunAsync('What is the system information?')

2. WinDiagMcpServer/Program.cs:
   - STDIO server with WithToolsFromAssembly() auto-discovery
   - Single tool: get_system_info (9 fields)

Architectural Pattern: Client-side sampling + STDIO transport. This is an end-to-end LLM-integrated demonstration, not just protocol pedagogy.

Implication for Python M1: C# M1 teaches 'LLM-first learning'; Python M1 teaches 'Protocol-first learning'. This is intentional per D3 (Client-Side Sampling for M1–5).

Conclusion: Python M1 server-only approach is a deliberate architectural choice per D3, not incomplete parity.

Correction documented in: .squad/decisions/inbox/bishop-m1-corrected-branch-spec.md

## 2026-04-13T22:36:32Z: M1 Parity Analysis Complete

- Corrected parity spec from local source to GitHub alonf/MCPDemo:milestone-1 branch
- Confirmed C# M1 includes both server and LLM-backed client (not server-only as initially thought)
- Verified Python M1 server-only approach is intentional per D3 (client deferred to M5 plus)
- Decision outputs: bishop-m1-parity-spec.md, bishop-m1-corrected-branch-spec.md, bishop-m1-llm-parity.md
- Action: Python M1 documentation should clarify pedagogical divergence vs. C# M1

## Learnings (2026-04-14T11:00Z Real Foundry Audit)

### Current runnable C# path is direct Azure OpenAI, not Azure AI Foundry project runtime

**Question:** Does the actual local `/mnt/c/Dev/MCPDemo` runnable path use an Azure AI Foundry project/runtime abstraction?

**Answer:** No. The current chat/runtime path uses direct Azure OpenAI primitives and a Cognitive Services endpoint, not a Foundry project client/runtime abstraction.

**Evidence:**
- `WinDiagMcpChat/WinDiagMcpChat.csproj` references `Microsoft.Agents.AI.OpenAI`, `Azure.AI.OpenAI`, `Azure.Identity`, and `ModelContextProtocol` only. There is no `Azure.AI.Projects` or equivalent Foundry-project package.
- `WinDiagMcpChat/Program.cs` hard-codes `https://alonlecturedemo-resource.cognitiveservices.azure.com/`, creates `DefaultAzureCredential()`, then `new AzureOpenAIClient(endpoint, credential).GetChatClient("model-router")`.
- The same file wires MCP sampling through that `chatClient.AsAIAgent(...)`; it does not create or resolve a Foundry project, agent, or project-scoped runtime object.
- Repo-wide search across local branches found no `Foundry`, `AIProject`, or `Azure.AI.Projects` usage.

**Runtime observation:**
- Real run from WSL: `dotnet run --project WinDiagMcpChat/WinDiagMcpChat.csproj` starts the actual app, then fails before server launch because it tries to spawn `dotnet/dotnet` as a relative path on Linux. Even on that runnable path, the configured LLM route is still direct Azure OpenAI, not Foundry project runtime.

### Python status against that invariant

- `src/mcp_linux_diag_server/client.py` also uses direct Azure OpenAI (`openai.AzureOpenAI`) plus either API key or `DefaultAzureCredential`, with the same Cognitiveservices token scope.
- Local `.env.local` is configured for endpoint + deployment + API version + `MCP_DEMO_AZURE_OPENAI_USE_DEFAULT_CREDENTIAL`; no project-style Foundry config is present.
- Real run succeeded: `python3 -m mcp_linux_diag_server.client --json --prompt "What is the system information?"`, and the model called `get_system_info` successfully.

**Migration-critical invariant for this request:**
- Match **direct Azure OpenAI endpoint + deployment + DefaultAzureCredential-compatible auth**, not a Foundry project abstraction.
- If the user now specifically wants a Foundry-project-backed runtime, that is a **new requirement beyond current C# behavior**, and both C# and Python would need work for it.

---

## Team Updates (2026-04-14T08:00:28Z — Foundry Runtime Decision Closure)

### Foundry Runtime Verification ✅

- **Local C# reference confirmed:** `/mnt/c/Dev/MCPDemo/WinDiagMcpChat/Program.cs` uses direct `AzureOpenAIClient(endpoint, credential)`, not Foundry project/runtime wrapper
- **Repo search complete:** No `Azure.AI.Projects` or project-scoped runtime found anywhere in active branches
- **Python alignment confirmed:** Client already uses same direct Azure OpenAI path
- **Live validation:** Ash's real run proves Python client works end-to-end with current architecture

### Decision Finalized

- **C# reference is not an Azure AI Foundry project/runtime implementation**
- **Python stays on direct Azure OpenAI shape** (currently correct)
- **No runtime architecture changes needed for M1–5**
- If user later requests true Foundry abstraction, that is a **new gap in both C# and Python**, not a correction

### Outcome

- Both teams aligned on Azure OpenAI path forward
- M1 lecture demonstration proven and validated
- No blocking changes to implementation roadmap

---

## Learnings (2026-04-14T13:45Z M3 Delta Analysis)

### C# Milestone-3 vs Milestone-2: Three Major Additions

**Finding:** M3 crystallizes MCP pedagogical progression with three key concepts:

1. **Event Log Snapshot Tool** (`create_event_log_snapshot`)
   - Parameters: logName (validated against whitelist), xPathQuery
   - Returns: resourceUri + snapshotId + eventCount
   - Stores immutable snapshots in singleton storage
   - Teaching: deterministic, parameterized data capture

2. **Resource URIs with Pagination** (`eventlog://snapshot/{id}?limit={int}&offset={int}`)
   - Handler reads from snapshot storage, applies pagination
   - Response includes: TotalCount, ReturnedCount, HasMore, NextOffset (always)
   - Defaults: limit=50, max=500, offset=0
   - Validation: limit > 0 and <= 500, offset >= 0
   - Teaching: immutable snapshots, client-orchestrated paging, large dataset handling

3. **MCP Prompts** (4 prompts for AI-guided workflows)
   - `AnalyzeRecentApplicationErrors(hoursBack=24)` — Event log error analysis
   - `ExplainHighCpu()` — Multi-tool correlation (processes + event logs)
   - `DetectSecurityAnomalies(hoursBack=24)` — Security-focused analysis
   - `DiagnoseSystemHealth(hoursBack=24)` — Comprehensive health report
   - Returns: plain text workflow guides with numbered steps
   - Teaching: multi-tool orchestration, pattern recognition, severity classification

4. **Chat Client** (Optional, not parity-critical for M3)
   - Demonstrates prompt discovery, resource pagination, Azure OpenAI integration
   - Python M3 can defer this to M4+

**Architecture Pattern Confirmed:**
- Program.cs: `.WithResourcesFromAssembly()` and `.WithPromptsFromAssembly()` registration
- Event log storage injected as singleton
- Logging upgraded: JSON console, stderr, respects MCP_LOG_LEVEL
- Project structure: Tools/, Resources/, Prompts/ folders (separation of concerns)

**Parity-Critical Mapping for Python M3:**
- Event Log Tool → journalctl/syslog with XPath-equivalent filtering
- Resource URI → `syslog://snapshot/{id}?limit={int}&offset={int}` (same pagination schema)
- Prompts → same 4 prompts, plain text, same parameters
- Storage → in-memory concurrent dict, same snapshot ID keying

**Migration Decision:** All three components parity-critical for M3; chat client deferred.

**Decision documented to:** `.squad/decisions/inbox/bishop-m3-delta.md` (comprehensive spec, 13.9KB)

---

## Learnings (2026-04-14T14:30Z M4 Delta Analysis: Transport Layer Transformation)

### C# Milestone 4 Core Delta: STDIO → HTTP Streaming

**Question:** What does C# M4 add to M1–3?  
**Answer:** Transport mechanism change only; no new server features.

**Evidence (Comparative Branch Inspection):**

1. **Host Framework Swap:**
   - M3: `Host.CreateApplicationBuilder(args)` → generic host, no HTTP
   - M4: `WebApplication.CreateBuilder(args)` → web-specific host with routing, middleware

2. **Transport Registration:**
   - M3: `.WithStdioServerTransport()` → STDIO pipes
   - M4: `.WithHttpTransport()` → HTTP streaming (MCP SDK handles details)

3. **Server Startup:**
   - M3: `await app.RunAsync()` → no port specified
   - M4: `await app.RunAsync("http://localhost:5000")` → explicit HTTP listener

4. **Route & Authentication:**
   - M3: (not applicable, STDIO has no routes)
   - M4: `app.MapMcp("/mcp")` + middleware validating `X-API-Key` header or `apiKey` query param

5. **Dependencies:**
   - M3: `Microsoft.Extensions.Hosting`
   - M4: `-Hosting` (removed), `+Microsoft.AspNetCore.App` (framework ref), `+ModelContextProtocol.AspNetCore`

6. **Tools & Resources (unchanged):**
   - M3 & M4 both have: `get_system_info`, `get_process_list`, event log tools, resources, prompts
   - No new tools, no behavioral changes to existing tools

**Code Size Impact:**
- Program.cs: 47 lines → 65 lines (+18, due to middleware + route setup)
- New file: McpConsoleFormatter.cs (117 lines, optional pedagogical enhancement)
- test-mcp-server.ps1: 60 → 200+ lines (HTTP POST logic replaces mcp-cli invocation)
- launch-inspector.ps1: 70 → 90 lines (process mgmt + HTTP endpoint passing)

**Architecture Pattern:**
- M1–3: "Protocol learner sees single tool, then resources, then prompts" (all via STDIO)
- M4: "Protocol learner now sees the *same features* delivered over HTTP instead of pipes"
- Pedagogical goal: Transport-independent protocol design

### Configuration & Test Script Implications

**Breaking Changes (M3 → M4):**
- `server_config.json` is removed (M4 uses code-driven config)
- `setup-claude-desktop.ps1`, `setup-claude-desktop.sh` removed (Claude Desktop requires integration update for HTTP)
- `mcp-cli` test approach abandoned in favor of native HTTP POST

**Test Pattern Shift:**
- M3: CLI-based (`mcp-cli tools`, `mcp-cli cmd`) via external process
- M4: HTTP POST with session ID tracking + SSE parsing
- Rationale: CLI tools abstract transport; HTTP requires understanding of stateless request/response cycles

**MCP Inspector Integration:**
- M3: `mcp-inspector -- dotnet run ...` (STDIO subprocess transport)
- M4: Server starts separately; inspector connects to `http://localhost:5000/mcp` with API key in header
- Implication: Instructor must explain multi-process debugging (server + inspector)

### Decision Extracted

**Parity-Critical for Python M4:**
1. HTTP listener on `/mcp` route
2. API key authentication (hardcoded `"secure-mcp-key"` for demo)
3. Session ID tracking via response headers
4. Test scripts that POST to `/mcp` with session ID
5. launcher script that separates server startup from inspector connection

**Optional Enhancements:**
1. Custom logging formatter with colored method names
2. PowerShell-to-Python helper function equivalents

**Not Goals:**
1. Claude Desktop setup (deferred to M5 after HTTP integration maturity)
2. Config files or environment-driven port binding (M5+)
3. Foundry project abstraction (M6+)

### Upstream Alignment

- C# M4 is transport-only; Python M4 should mirror this scope exactly
- No pedagogical divergence; both see "same protocol over different pipes"
- Migration risk: Low (straightforward FastAPI setup + middleware)

**Decision documented to:** `.squad/decisions/inbox/bishop-m4-delta.md` (16.6KB comprehensive spec with appendix)

---

## Learnings (2026-04-14T16:45Z M5 Delta Analysis)

### C# Milestone-5 vs Milestone-4: Elicitation + Destructive Operations

**Finding:** M5 introduces the first **write operation** protected by MCP elicitation protocol. This is pedagogically significant: M1–4 are read-only; M5 teaches how servers can request user confirmation before destructive actions.

**Evidence (Code Inspection):**

**New Server Tool: `KillProcessAsync`**
- Signature: `async Task<KillProcessResult> KillProcessAsync(McpServer server, int? processId = null, string? reason = null, CancellationToken cancellationToken)`
- **Stage 1 (if no PID):** Server calls `server.ElicitAsync()` with form schema listing top-5 CPU processes; user selects one
- **Stage 2 (mandatory):** Server calls `server.ElicitAsync()` again requesting confirmation phrase `CONFIRM PID {pid}`; user must type exactly to proceed
- **Stage 3 (execute):** `process.Kill(true)` (graceful Windows tree kill); log reason; return typed `KillProcessResult`

**CPU Sampling Logic (for elicitation form population):**
- T0: Capture {PID → {name, workingSet, utime+stime}} for all processes
- Wait 750ms
- T1: Re-capture same snapshot
- Calculate: `cpu% = (T1.time - T0.time) / (750ms * num_cores) * 100`
- Rank by CPU % desc, then RAM desc; return top 5

**Result Type: `KillProcessResult` (sealed record)**
- Factory methods: `Success(pid, name, reason)`, `Cancelled(msg)`, `NotFound(pid)`, `Failed(pid, name, errorMsg)`
- Status values: "terminated" | "cancelled" | "not-found" | "failed"

**Client Enhancements (M5):**
- New function: `ReadMcpResource(resourceUri)` — reads paginated resource URIs with ?limit=N&offset=M
- New function: `GetMcpPromptContentAsync(promptName, argumentsJson)` — fetches and expands named prompts
- Prompt discovery: Fetches available prompts on startup; includes in agent instructions for workflow context
- Session management: `agent.CreateSessionAsync()` for multi-turn history (MAF 1.1.0+)

**Package Changes:**
- MCP SDK: 0.5.0-preview.1 → 1.2.0 (stable release)
- MAF (Microsoft.Agents.AI): 1.0.0-preview → 1.1.0 (breaking: `CreateAIAgent` → `AsAIAgent`, `GetNewThread` → `CreateSessionAsync`)
- Azure.AI.OpenAI, Azure.Identity: beta bumps (non-breaking for demo)

**Architecture Pattern:**
- M1–4: "Protocol learner performs read-only operations" (all queries, no state changes)
- M5: "Protocol learner learns elicitation: server → client dialog before destructive actions"
- M6+: Sampling (WMI) and roots (registry access) deferred; M5 is purely elicitation pedagogy

### Parity-Critical Invariants for Python M5

**Must preserve:**
1. `kill_process` tool with two-stage elicitation (process selection form + confirmation text)
2. CPU% calculation via time-delta sampling (750ms interval)
3. Exact confirmation phrase matching (case-insensitive)
4. Result type with status field ("terminated", "cancelled", "not-found", "failed")
5. Client prompt discovery and form elicitation response handling

**Acceptable divergence:**
- Linux /proc sampling instead of Win32 APIs for CPU calculation
- SIGTERM instead of Windows graceful tree kill
- systemd journal API instead of Windows Event Viewer for process metadata

### Linux Process Data Mapping

| C# Source | Linux Equivalent | Python |
|-----------|------------------|--------|
| `Process.GetProcesses()` | `/proc/[pid]` or `psutil.process_iter()` | `psutil.process_iter()` |
| `process.ProcessName` | `/proc/[pid]/comm` | `p.name()` |
| `process.WorkingSet64` | `/proc/[pid]/status` line "VmRSS" | `p.memory_info().rss` |
| `process.TotalProcessorTime` | `/proc/[pid]/stat` fields utime+stime | `p.cpu_times().user + p.cpu_times().system` |
| `Process.Kill(true)` | `signal.SIGTERM` + wait + `signal.SIGKILL` | `p.terminate()` + wait + `p.kill()` |

### Pedagogical Arc

- **M1:** "Tools exist; MCP is a protocol for exposing them"
- **M2:** "Tools can be complex; let's paginate results"
- **M3:** "Resources and Prompts teach multi-tool workflows"
- **M4:** "Transport is orthogonal; same protocol, different pipes (HTTP)"
- **M5 ← HERE:** "Servers can drive conversations; elicitation prevents LLM accidents"
- **M6:** "Sampling refines decisions; server-side model-driven queries"
- **M7:** "Roots enforce guardrails; only safe branches of the system tree"

### Migration Risk Assessment

**Low risk:** Elicitation form schema is straightforward; MCP protocol is stable in 1.2.0.

**Medium risk:** CPU% calculation precision; 750ms sampling on variable-load systems may introduce jitter. Mitigation: test on 2- and 16-core machines; document margin of error.

**Medium risk:** Async cancellation handling; Python `asyncio.CancelledError` semantics differ slightly from C# `OperationCanceledException`. Mitigation: explicit timeout enforcement.

**Decision documented to:** `.squad/decisions/inbox/bishop-m5-delta.md` (13.4KB comprehensive analysis)
