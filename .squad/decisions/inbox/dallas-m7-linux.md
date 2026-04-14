# Milestone 7: Linux Safety Rule Set for `/proc` and `/sys` Snapshot Enforcement

**Author:** Dallas (Linux Diagnostics Expert)  
**Date:** 2026-04-14  
**Status:** DECISION  
**Scope:** Allowed-roots validation, traversal/symlink escape prevention, resource paging for M7 implementation

---

## Executive Summary

Python Milestone 7 introduces **snapshot-based proc/sys access with allowed-roots enforcement**, replicating the C# Registry Roots Service pattern for Linux filesystems. This document codifies the security rules for:

- Default allowed `/proc` and `/sys` roots (conservative, world-readable)
- Path traversal and symlink escape prevention  
- Forbidden file classes (unsafe for untrusted snapshot access)
- Environment caveats (WSL, containers, permission errors)
- Pagination and snapshot resource constraints

---

## 1. Allowed Roots: Default and Dynamic

### 1.1 DEFAULT ALLOWED ROOTS (Hard-Coded)

These roots are **always** safe for non-root snapshot reads in normal Linux environments:

#### System Diagnostics

- `/proc/cpuinfo` (exact)  
- `/proc/loadavg` (exact)  
- `/proc/meminfo` (exact)  
- `/proc/uptime` (exact)  
- `/proc/version` (exact)  
- `/proc/stat` (exact) – System CPU/interrupt stats  
- `/proc/pressure/` (prefix) – Memory/CPU/IO pressure metrics  

#### System Configuration

- `/proc/sys/fs/` (prefix) – Filesystem limits  
- `/proc/sys/kernel/` (prefix) – Kernel tuning parameters  
- `/proc/sys/vm/` (prefix) – Virtual memory settings  
- `/etc/os-release` (exact) – OS identification (world-readable standard)

#### Cgroup Resources

- `/sys/fs/cgroup/cpu.max` (exact)  
- `/sys/fs/cgroup/memory.current` (exact)  
- `/sys/fs/cgroup/memory.max` (exact)  

#### Network Diagnostics

- `/proc/net/tcp` (exact)  
- `/proc/net/udp` (exact)  

#### Process-Specific (with PID validation)

- `/proc/self/stat` (exact) – Own process CPU/memory snapshot  
- `/proc/self/status` (exact) – Own process metadata  
- `/proc/self/cmdline` (exact) – Own process command line  
- `/proc/[PID]/stat` (pattern: `/proc/\d+/stat`) – **Only if PID is alive and readable**  
- `/proc/[PID]/status` (pattern: `/proc/\d+/status`) – **Only if PID is alive and readable**  
- `/proc/[PID]/cmdline` (pattern: `/proc/\d+/cmdline`) – **Only if PID is alive and readable**  

### 1.2 DYNAMIC ALLOWED ROOTS (User Elicitation)

When a snapshot tool is asked for a path **not** in the default allow-list, the tool SHALL:

1. **Check** if the path is in the allow-list  
2. **If blocked:** Raise `PathNotAllowedError` with:
   - The requested path  
   - The list of currently allowed roots  
   - Guidance: "Call `request_proc_access` to request permission."  
3. **If user calls** `request_proc_access(path, reason)`:
   - Use **elicitation** to ask the user for approval (MCP sampling or user input)  
   - If approved: **Add the path prefix to the allow-list** (in-memory, session-scoped)  
   - If denied: Return user's decision  
4. **Retry** the snapshot tool with the updated allow-list

**Design:** Elicitation is **mandatory** (even though we cannot actually modify `/proc` permissions like Windows Registry). This enforces intentional access and user awareness of reading system-level data.

---

## 2. Path Validation Rules

### 2.1 NORMALIZATION AND ESCAPING

Every requested path **SHALL**:

1. **Normalize:** Apply `os.path.normpath()` to convert slashes and remove `.` references  
2. **Reject if contains `..`:** Any path with `..` directory traversal is forbidden immediately  
   - Error: "Path traversal detected: {path}"  
3. **Reject if contains placeholders:** Patterns like `[pid]`, `[PID]`, `*` are forbidden  
   - Error: "Placeholder or pattern not allowed; provide concrete path"  
4. **Reject if symlink escapes allowlist:** After calling `os.path.realpath()`:  
   - If the **resolved real path** does not start with an allowed root, reject  
   - Error: "Resolved path {real_path} is not within allowed roots"  
   - **Caveat:** Only trust `realpath()` on stable mounted filesystems; `/proc` symlinks can be volatile  

### 2.2 PID VALIDATION (Process-Specific Paths)

For patterns like `/proc/[0-9]+/{stat,status,cmdline}`:

1. **Extract PID** from the path using regex `^/proc/(\d+)/(stat|status|cmdline)$`  
2. **Check if alive:** Call `Path(f"/proc/{pid}/stat").is_file()`  
   - If the file exists, the PID is currently alive  
   - If the file does not exist, raise: "PID {pid} is not found or has exited"  
3. **Catch race conditions:** Between PID validation and actual read, the process may exit  
   - This is acceptable; let the read fail naturally with `FileNotFoundError`

---

## 3. Forbidden File Classes

The following file types **SHALL NEVER** be snapshots, regardless of user request or elicitation:

### 3.1 DANGEROUS SPECIAL FILES

- `/proc/kcore` – Entire kernel memory image; **privilege escalation risk**  
- `/proc/kmem` – Kernel memory; **deprecated, privilege escalation risk**  
- `/proc/mem` – Physical memory; **deprecated**  
- `/proc/sysvipc/` (prefix) – System V IPC; **contains shared memory segments**  
- `/sys/class/gpio/` (prefix) – GPIO device control; **hardware interaction risk**  
- `/sys/class/pwm/` (prefix) – PWM device control; **hardware interaction risk**  
- `/sys/kernel/debug/` (prefix) – Debug interfaces; **unstable kernel internals**  

### 3.2 RATIONALE

These files are:

- **Non-portable:** May not exist in all Linux distributions or kernel versions  
- **Privilege-escalation vectors:** Require root or special capabilities  
- **State-mutating:** Reading may trigger side effects (e.g., device state changes)  
- **Container-hostile:** Inaccessible in standard container environments  

### 3.3 ENFORCEMENT

When a path matches a forbidden pattern:

- **Raise immediately:** `ForbiddenPathError` before validation attempts  
- **Do not elicit:** Elicitation cannot override forbidden paths  
- **Error message:** "Path is forbidden for security reasons: {path}"  

---

## 4. Environment-Specific Caveats

### 4.1 WSL (Windows Subsystem for Linux)

**Detection:** Check `/proc/version` for "microsoft" string (case-insensitive)

**Implications:**
- `/proc/meminfo` reflects **guest memory**, not Windows host  
- `/proc/stat` reflects **guest CPU**, not Windows host  
- PID namespace is **isolated** from Windows processes  
- `/sys/fs/cgroup/` may be **missing or empty** (no native cgroups in WSL 1)

**Mitigation:** User should be notified:  
> "WSL guest environment detected; readings reflect the Linux guest, not the Windows host."

---

### 4.2 Containers (Docker, Kubernetes, LXC)

**Detection:** Check `/proc/self/cgroup` for markers: `docker`, `containerd`, `kubepods`, `lxc`

**Implications:**
- `/proc` is **filtered** to show only container's PID namespace  
- PIDs outside container are **not visible**  
- `/sys/fs/cgroup/` reflects **container resource limits**, not host  
- `/etc/os-release` may reflect **container base image**, not host OS  

**Mitigation:** User should be notified:  
> "Container cgroup markers detected; readings reflect the current container namespace."

---

### 4.3 Permission Errors

**Scenario:** Non-root user requests `/proc/[OTHER_PID]/cmdline`

**Behavior:**
- **Do NOT reject preemptively** based on current UID  
- **Attempt read;** if `PermissionError` is raised during snapshot creation:  
  - Catch the error  
  - Return a partial snapshot with `"_error": "Permission denied for [path]. Try /proc/self/... or world-readable source."`  
  - Include `details.permission_error = True`

**Rationale:** ptrace_scope and LSM rules vary; let the kernel decide.

---

### 4.4 Ephemeral procfs State

**Race conditions:**
- Process exits between `/proc` list and individual file read  
- `/proc/[pid]/` subdirectory structure changes during snapshot  
- `/proc` mount points can be **redone** or **remounted**  

**Mitigation:**
- **Accept races:** Snapshot creation is not atomic  
- **Document in resource:** Include `details.race_warnings` listing any skipped entries  
- **Truncate gracefully:** If snapshot exceeds size limits, truncate and set `truncated: True` in pagination metadata

---

## 5. Snapshot Resource Paging and Constraints

### 5.1 RESOURCE URI SCHEME

- **Scheme:** `proc://snapshot/{snapshotId}`  
- **With paging:** `proc://snapshot/{snapshotId}?limit={limit}&offset={offset}`

Example:
```
proc://snapshot/abc123def456
proc://snapshot/abc123def456?limit=100&offset=0
```

### 5.2 DEFAULT AND MAXIMUM LIMITS

- **Default limit:** 50 entries per page  
- **Maximum limit:** 500 entries per page  
- **If user requests limit > 500:** Silently cap to 500  
- **If user requests limit ≤ 0:** Raise error  

### 5.3 PAGINATION METADATA

Every resource response SHALL include:

```json
{
  "snapshot_id": "abc123",
  "path": "/proc/meminfo",
  "created_at_utc": "2026-04-14T12:34:56Z",
  "line_count": 1250,
  "lines": [...],
  "pagination": {
    "total_count": 1250,
    "returned_count": 50,
    "limit": 50,
    "offset": 0,
    "has_more": true,
    "next_offset": 50
  },
  "details": {
    "environment_notes": ["Container cgroup markers detected"],
    "permission_error": false,
    "race_warnings": []
  }
}
```

### 5.4 STORAGE LIFETIME

- **In-memory storage:** Session-scoped (`_ProcSnapshotStore.instance()`)  
- **Thread-safe:** All snapshots protected by `Lock`  
- **Lifetime:** Snapshots persist until the server terminates or `clear_proc_snapshots()` is called  
- **No disk persistence:** Each server restart clears all snapshots  

### 5.5 RESOURCE SIZE AND TRUNCATION

- **Max lines per snapshot:** 10,000 (configurable)  
- **Max bytes per snapshot:** 2 MB (configurable)  
- If either limit is exceeded during read:  
  - Truncate the snapshot  
  - Set `truncated: True` in response  
  - Document in `details.truncation_reason`  

---

## 6. Two Public MCP Tools

### 6.1 `create_proc_snapshot`

**Signature:**
```python
async def create_proc_snapshot(
    path: str,
    filter_text: str | None = None,
    max_lines: int | None = None
) -> ProcSnapshotSummary
```

**Behavior:**
1. Validate `path` against allowed roots (see §2, §3)  
2. If blocked: Raise `PathNotAllowedError` with suggestion to call `request_proc_access`  
3. Read the file at `path` (up to `max_lines`)  
4. Parse structured formats if applicable (e.g., `/proc/meminfo` → key-value pairs)  
5. Create an in-memory snapshot  
6. Return `ProcSnapshotSummary` with `resource_uri: proc://snapshot/{id}`

**Error cases:**
- `PathNotAllowedError` – Path not in allow-list  
- `ForbiddenPathError` – Path is explicitly forbidden  
- `FileNotFoundError` – Path does not exist  
- `PermissionError` – Non-root cannot read  
- `IsADirectoryError` – Path is a directory, not a file  
- `ValueError` – Parsing failed (malformed data)

---

### 6.2 `request_proc_access`

**Signature:**
```python
async def request_proc_access(
    path: str,
    reason: str | None = None
) -> dict[str, bool | str]
```

**Behavior:**
1. Check if `path` is **already** allowed (return `{"already_allowed": True}`)  
2. Check if `path` matches forbidden patterns (raise `ForbiddenPathError`)  
3. Use **elicitation** to present the request to the user:
   ```
   User requests access to: {path}
   Reason: {reason or "Not provided"}
   
   Allowed roots: {current_roots}
   
   Approve? (yes/no)
   ```
4. If approved: Add path prefix to allow-list and return `{"approved": True}`  
5. If denied: Return `{"approved": False, "reason": "User denied"}`

**Error cases:**
- `ForbiddenPathError` – Path is explicitly forbidden  
- `ValueError` – Elicitation failed or user did not respond

---

## 7. Integration with M6 Sampling

**No changes to M6 sampling infrastructure.** M6's `validate_linux_diagnostic_query()` and `read_linux_diagnostic()` remain unchanged.

**M7 operates independently:**
- M6 tools remain sampling-based (optional client capability)  
- M7 tools are imperative (user calls directly)  
- Both can coexist; no conflict  

---

## 8. Testing Strategy

### 8.1 Unit Tests

- **Path validation:**
  - ✅ Reject `..` traversal  
  - ✅ Reject placeholders (`[pid]`, `*`)  
  - ✅ Accept normalized `/proc/self/stat`  
  - ✅ Accept concrete PID if alive  

- **Allowed roots:**
  - ✅ Accept default roots  
  - ✅ Reject non-default roots until elicitation  
  - ✅ Forbidden paths always reject  

- **Paging:**
  - ✅ Correct `next_offset` calculation  
  - ✅ Handle `limit > max` gracefully  
  - ✅ Handle `offset >= total_count`  

### 8.2 Integration Tests

- **Snapshot creation:**
  - ✅ Read `/proc/meminfo` and create snapshot  
  - ✅ Verify resource URI returned  
  - ✅ Verify pagination works  

- **Environment detection:**
  - ✅ Detect WSL from `/proc/version`  
  - ✅ Detect container from `/proc/self/cgroup`  
  - ✅ Include in resource `details`  

### 8.3 Edge Cases

- **Race condition:** Process exits between PID validation and snapshot  
  - Behavior: Snapshot creation fails with `FileNotFoundError`; document as acceptable  
- **Permission error:** Non-root user requests restricted `/proc/[OTHER_PID]/stat`  
  - Behavior: Snapshot includes `permission_error: True` in details  
- **Empty or malformed files:** Read `/proc/[pid]/cmdline` for kernel thread  
  - Behavior: Return empty string (not an error)  

---

## 9. Decision & Owners

**DECISION:** Python M7 SHALL implement allowed-roots enforcement for `/proc` and `/sys` with:
- Default safe-root allowlist (system diagnostics, own process, cgroup resources)  
- Strict path traversal/symlink/placeholder validation  
- Forbidden file class enforcement (kcore, kmem, gpio, etc.)  
- Environment detection (WSL, containers, permissions)  
- Two public tools (`create_proc_snapshot`, `request_proc_access`)  
- Paged resource API (`proc://snapshot/{id}?limit=N&offset=M`)  
- Elicitation-gated dynamic root approval

**OWNERS:**
- **Ash (Python Dev):** Implementation in `src/mcp_linux_diag_server/tools/proc_snapshots.py`  
- **Dallas (Linux Expert):** This decision document and path validation rules  
- **Bishop (Parity Auditor):** Verify C# M7 parity in resource formats and tool behavior

**LINK TO IMPLEMENTATION:** `.squad/skills/linux-proc-diagnostics/SKILL.md` (updated with M7 patterns)

---

## Appendix: Security Rationale

### Why Forbidden Paths?

- **`/proc/kcore`:** Maps entire kernel memory; root-only, 99% of nodes should reject read attempts  
- **`/proc/sysvipc/`:** Shared memory segments can be modified by IPC operations  
- **`/sys/class/gpio/`, `/sys/class/pwm/`:** Exported as sysfs interfaces; reading can reconfigure hardware  
- **`/sys/kernel/debug/`:** Unstable kernel internals; format varies across kernel versions

### Why Elicitation for Dynamic Roots?

- **Intentionality:** User knows they're requesting system data; no silent expansions  
- **Audit trail:** Elicitation prompt is logged (in theory) for compliance  
- **Parity with C# M7:** Registry roots also use elicitation even though we can't modify Registry permissions  

### Why Session-Scoped Storage?

- **No persistence:** Server restart resets allow-list (security reset)  
- **No disk write:** Avoids `/tmp` or other filesystem interaction  
- **Thread-safe:** Locks protect concurrent access  
- **Scalable:** In-memory dict is O(1) lookup  

---

## References

- **Linux man pages:** `proc(5)`, `sysfs(5)`, `namespaces(7)`, `cgroups(7)`  
- **Kernel docs:** Linux kernel proc documentation  
- **Parity:** C# `RegistryRootsService` and `RegistrySnapshotResource` patterns  
- **M6 foundation:** `linux_diagnostics.py` validation patterns  

---

**END OF DECISION DOCUMENT**
