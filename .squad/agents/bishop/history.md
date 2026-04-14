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
