# C# Milestone 7 → Python Parity Delta

**Date:** 2026-04-14  
**By:** Bishop (MCP/C# Expert)  
**Status:** ANALYSIS COMPLETE

---

## Executive Summary

C# `milestone-7` introduces **Registry Tools and Roots/Sandboxing Architecture** as a new domain, building on M6's sampling infrastructure without modifying it. The feature teaches:
- **Sandboxing model**: Allowed-roots enforcement via `RegistryRootsService`.
- **Resource paging**: Read-only registry snapshots via `registry://snapshot/{id}` URIs.
- **Elicitation-based access management**: Tool requests permission when accessing paths outside allowed roots.

This is a **structural/authorization pattern addition**, not a sampling or transport change. Python M7 must adapt the roots model to `/proc` and `/sys` filesystem paths while preserving the pedagogical intent.

---

## Exact Feature Delta (M6 → M7)

### NEW COMPONENTS ADDED

#### 1. **Registry Tool (Public API)**
- **Class:** `McpServerRegistryToolType`  
- **Methods (2 public MCP tools):**
  1. `CreateRegistrySnapshotAsync(server, hive, key, recursive?, maxDepth?, filter?, cancellationToken?)`
     - Creates a serialized snapshot of registry key + subkeys
     - Returns `registry://snapshot/{snapshotId}` URI
     - Validates path is within allowed roots; throws `InvalidOperationException` if not
  2. `RequestRegistryAccessAsync(server, hive, key, reason?)`
     - Uses **elicitation** to ask user for permission to access a specific registry path
     - Adds approved path to `RegistryRootsService`
     - Pattern: proactive request *before* attempted access fails

- **Validation:** Enforced by `RegistryRootsService.IsPathAllowed(hive, key)` using string prefix matching against allowed roots

#### 2. **Registry Resources (Read-Only)**
- **Class:** `McpServerRegistryResourceType`  
- **URI Templates:**
  - `registry://snapshot/{id}` – Gets full snapshot JSON
  - `registry://snapshot/{id}?limit={limit}&offset={offset}` – Paged snapshot (default limit: 50, max: 500)
- **Flattening:** Registry tree is flattened to deterministic order for pagination via `FlattenRegistryTree()`
- **Output Format:**
  ```json
  {
    "SnapshotId": "abc123",
    "Hive": "HKLM",
    "Key": "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
    "KeyCount": 100,
    "Keys": [...],
    "Pagination": { "TotalCount": 100, "HasMore": true, "NextOffset": 50, ... }
  }
  ```

#### 3. **Registry Roots Service (Enforcement)**
- **Class:** `RegistryRootsService`  
- **Default Allowed Roots (hardcoded):**
  ```
  HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall
  HKCU\Software\Microsoft\Windows\CurrentVersion\Run
  ```
- **API:**
  - `SetAllowedRoots(IEnumerable<string>)` – Replace entire allow-list (admin config)
  - `AddAllowedRoot(string)` – Add single root (dynamic, via elicitation)
  - `IsPathAllowed(hive, key)` – Check if `hive\key` starts with any allowed root
  - `GetAllowedRoots()` – Return current allow-list

#### 4. **Storage & DTOs**
- `IRegistrySnapshotStorage` – Interface for persisting snapshots
- `RegistrySnapshotStorage` – In-memory `ConcurrentDictionary<id, RegistrySnapshotEntry>`
- `RegistrySnapshotEntry` – Record: `(Hive, Key, JsonContent)`
- `RegistryKeyDto` – Tree structure: `{ Name, Values: Dict<string,string>, SubKeys: List<RegistryKeyDto> }`

#### 5. **Prompt**
- **Class:** `RegistryTroubleshootingPromptType`  
- **Method:** `TroubleshootRegistry(taskDescription)`
- **Content:** Workflow instructions that explicitly guide users to:
  1. Identify the registry key needed
  2. **Proactively call `request_registry_access` if the key is outside default allowed roots**
  3. Call `create_registry_snapshot`
  4. Use `read_resource` to inspect the snapshot

#### 6. **DI Registration (Program.cs)**
```csharp
builder.Services.AddSingleton<IRegistrySnapshotStorage, RegistrySnapshotStorage>();
builder.Services.AddSingleton<RegistryRootsService>();
```

#### 7. **TestRoots Project**
- Standalone console app testing `RegistryRootsService` logic
- Demonstrates default-root behavior and dynamic root configuration
- Not part of the server; purely educational validation tool

### MODIFIED COMPONENTS

#### 1. **WinDiagMcpChat/Program.cs**
- Added notification handler for `notifications/progress`
- Added tool discovery debug output (lists all tools on startup)
- No sampling/capability changes (M6 infrastructure reused)

#### 2. **WinDiagMcpServer/Tools/Process/**
- **MemoryUsage.cs**: Added XML doc comments (documentation only, no logic change)
- **ProcessesInfoResult.cs**: Changed `new()` to `[]` (C# 12+ style, no logic change)

#### 3. **Roadmap Documentation (docs/MCPDemoRoadmap.md)**
- Updated M7 entry from placeholder to complete spec
- Noted completion of registry tools and roots enforcement

---

## Parity-Critical Behavior (MUST HAVE)

1. **Allowed-Roots Pattern**
   - Tool must check if requested path is in allow-list **before execution**
   - If blocked: Throw/raise exception with clear message showing currently allowed roots
   - If user requests new access: Use **elicitation** to ask permission and add to allow-list dynamically

2. **Resource Snapshots**
   - Tool execution returns a resource URI (e.g., `proc://snapshot/{id}`)
   - Resource supports read-only access via `read_resource` MCP protocol
   - Snapshots persist in-memory (session-scoped)

3. **Paging**
   - Resource URIs support `?limit=N&offset=M` query parameters
   - Default limit: 50, max: 500
   - Return pagination metadata: `TotalCount`, `HasMore`, `NextOffset`

4. **Prompt Workflow**
   - Guides user to **proactively request access** if needed key is outside allowed roots
   - Prompts do NOT wait for tool failure; they anticipate restrictions

5. **Two Public MCP Tools**
   - `create_registry_snapshot` (in Python: `create_proc_snapshot` or similar)
   - `request_registry_access` (in Python: `request_proc_access` or similar)

---

## Python Adaptation Notes

| C# Concept | Windows Mapping | Python Equivalent |
|---|---|---|
| Registry hive | `HKLM`, `HKCU`, etc. | N/A (use absolute paths) |
| Registry key path | `Software\Microsoft\...` | `/proc/meminfo`, `/sys/class/...` |
| Allowed-roots check | String prefix match `HKLM\Software\...` | Path traversal check + allowlist (e.g., `/proc/`, `/sys/class/`) |
| Snapshot format | Hierarchical registry tree (DTO) | Flat key-value pairs or structured JSON from /proc file |
| Paging strategy | Tree flattening (depth-first or breadth-first) | Line-based or JSON array paging |

### Critical Constraints for Python
1. **No command execution**: Sampling must NOT call shell; only read static `/proc` and `/sys` files.
2. **Path allowlist must be strict**: No `..` traversal, no symlink following.
3. **Elicitation remains mandatory** for requesting new paths (even though Python cannot alter /proc permissions like Windows Registry).
4. **Resource URI naming**: Use `proc://snapshot/{id}` or similar (not `registry://`).

---

## Optional/Non-Critical Changes

1. Exact code organization (`#region` markers)
2. Process tool documentation strings (added in M7 but no logic)
3. Chat client tool-listing debug output
4. Test project structure (TestRoots is isolated)
5. NuGet package version updates in M7 commits

---

## Key Constraints for Team

1. **M6 Sampling Infrastructure**: M7 does NOT modify or depend on sampling changes. Sampling remains optional for Python M7 unless already implemented in M6.
2. **Elicitation Reuse**: Python M7 must use the elicitation pattern from M5 (or M6, if present) to request new paths.
3. **Resource Protocol**: Registry resources are MCP resources (not tools). Python must register them with `read_resource` support.
4. **No Breaking Changes to M6**: Registry feature is purely additive; all M6 tools and prompts remain unchanged.

---

## Decision

**DECISION:** Python M7 shall implement allowed-roots enforcement for `/proc` and `/sys` paths with two public tools (`read_proc_snapshot`, `request_proc_access`) and one read-only resource type (`proc://snapshot/{id}`), preserving the pedagogical sandbox model while adapting to Linux filesystem structure.

**OWNERS:**
- Ash (Python Dev) – Implementation
- Dallas (Linux Diagnostics Expert) – Path validation rules
- Bishop (Pattern Verification) – Parity audit

**LINK TO IMPLEMENTATION:** `.squad/skills/parity-audit/SKILL.md` (if created for M7)

---

## Appendix: Commit Archaeology

| Commit | Purpose |
|---|---|
| `a1c7423` | Complete Milestone 7: Registry Roots, Logging Improvements, and WMI Fix |
| `ed1b87a`, `7ef46d7` | Merge milestone-6 into milestone-7 (conflict resolution) |
| `15b0a95` | Fix registry snapshot resources for paged reads |
| `8d76675` | Implement registry snapshot paging |
| `da3d8e4` | Improve Registry prompt to proactively request access for restricted roots |
| `74788f8` | Migrate from STDIO to Streamable HTTP (underlying transport) |
| `7ef46d7` | Standardize error handling in Registry tools |
| `614b98b` | Upgrade NuGet packages to latest stable releases |

All registry-specific commits are from M7; no registry code exists in M6.
