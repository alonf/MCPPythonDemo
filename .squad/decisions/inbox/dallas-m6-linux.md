# Dallas: Milestone 6 Linux Diagnostics Guardrails

**Decision by:** Dallas (Linux Diagnostics Expert)  
**Date:** 2026-04-14  
**Status:** Specification — Ready for Implementation Review  

---

## Executive Summary

Milestone 6 introduces **sampling-assisted diagnostics**: the server asks an LLM (via client sampling) to generate a `/proc`-based query, validates it strictly server-side, reads the file, and asks the LLM to summarize. This decision locks down the Linux-specific data sources, validation rules, and container/permission edge cases that Ash must respect.

**Parity with C# M6:** The C# version validates **WQL queries** before WMI execution. Python M6 validates **file paths + field selectors** before `/proc` reads.

---

## Part 1: Best Linux Data Sources for M6

### Data Source Category: `/proc` and `/sys`

For sampling-assisted diagnostics, we expose **read-only system state** that the LLM can learn to navigate. The primary sources are:

#### Primary Sources (Always Safe, World-Readable)

| Path | Purpose | Use Case | Notes |
|------|---------|----------|-------|
| `/proc/meminfo` | Memory usage (total, free, available, buffers, cached) | "Show me memory pressure" | Fields: MemTotal, MemAvailable, MemFree, Buffers, Cached, SwapTotal, SwapFree |
| `/proc/cpuinfo` | CPU model, count, flags | "What CPUs do I have?" | Stable format; works on all architectures |
| `/proc/loadavg` | Load average (1m, 5m, 15m) | "Is the system under load?" | 5 space-separated fields; first 3 are load averages |
| `/proc/uptime` | System uptime in seconds | "How long has it been running?" | Two space-separated floats: uptime_seconds, idle_seconds |
| `/proc/stat` | CPU time accounting (user, system, idle, iowait, irq) | "How much time in each CPU state?" | First line is "cpu ..."; per-cpu lines follow |
| `/proc/net/tcp` | TCP socket state and connection tracking | "What TCP connections exist?" | Space-separated fields; shows local_addr, state, etc. |
| `/proc/net/udp` | UDP socket state | "What UDP connections exist?" | Same format as tcp |
| `/proc/version` | Kernel version, compiler, distro hints | "Which kernel version?" | Single line; can detect WSL/container |
| `/etc/os-release` | OS identity (NAME, VERSION_ID, PRETTY_NAME) | "Which OS am I on?" | Shell-like KEY=VALUE format; always available |
| `/proc/sys/vm/swappiness` | Swap aggressiveness | "How aggressive is swap?" | Single integer 0–100 |
| `/proc/sys/vm/dirty_ratio` | Dirty page ratio before writeback | "Dirty page thresholds?" | Single integer (percentage) |
| `/proc/pressure/` | PSI (Pressure Stall Info) — CPU, memory, IO pressure | "Is memory/CPU/IO pressure high?" | Per-cpu, memory, io; each line has avg10, avg60, avg300 |

#### Process-Specific Sources (Readable by Owner or Root)

| Path | Purpose | Constraint |
|------|---------|-----------|
| `/proc/[pid]/stat` | CPU time, memory, state for one PID | Readable by owner or root; respects namespace |
| `/proc/[pid]/status` | Detailed memory breakdown for one PID | Readable by owner or root |
| `/proc/[pid]/cmdline` | Command-line arguments for one PID | Readable by owner or root |
| `/proc/[pid]/fd/` | Open file descriptors | Readable by owner or root |

#### Secondary Sources (Availability Varies)

| Path | Purpose | Notes |
|------|---------|-------|
| `/proc/zoneinfo` | NUMA zone info | Advanced; not recommended for M6 |
| `/proc/buddyinfo` | Kernel memory allocator state | Advanced; not recommended for M6 |
| `/proc/slabinfo` | Kernel slab cache state | Requires root; advanced |
| `/proc/interrupts` | Interrupt counts | Useful for driver debugging |

### Why These Sources

1. **Stable kernel interfaces:** `/proc` is a stable, documented interface since Linux 2.0. Format changes rarely, and educational value outweighs library abstractions.
2. **Cross-distro parity:** These files exist identically on Ubuntu, Debian, CentOS, WSL, and containerized Linux. No distro-specific branches needed.
3. **Non-root readable:** Most primary sources are readable by all users; no privilege escalation needed for teaching.
4. **LLM-learnable:** File paths and field names are human-readable; the LLM can plausibly generate valid `/proc` paths after a few examples.

---

## Part 2: Server-Side Allowlist and Validation Rules

### Validation Architecture

```
LLM Output (raw text, possibly with markdown)
  ↓
[Sanitization: remove markdown artifacts]
  ↓
[Parsing: extract file path and optional field name]
  ↓
[Allowlist Check: is this path + field allowed?]
  ↓
[Permission Check: can we read this?]
  ↓
[Safe Read: read file, extract field]
  ↓
Return field value or error message
```

### Sanitization Rules

The LLM may return wrapped output. Strip these **before** validation:

```
Remove from the raw string:
  - ```bash, ```sh, ```linux, ```proc (markdown code fence markers)
  - ``` (closing fence)
  - Leading/trailing whitespace
  - Comments (lines starting with #)
```

**Example input from LLM:**
```
```bash
/proc/meminfo | grep MemAvailable
```
```

**After sanitization:**
```
/proc/meminfo | grep MemAvailable
```

### Path Parsing Rules

After sanitization, extract the **file path** and optional **field selector**:

```
Pattern 1: "/proc/meminfo | grep MemAvailable"
  → file_path = "/proc/meminfo"
  → field = "MemAvailable"

Pattern 2: "/proc/sys/vm/swappiness"
  → file_path = "/proc/sys/vm/swappiness"
  → field = None (read entire file)

Pattern 3: "/proc/[pid]/stat"
  → REJECT (contains [pid] placeholder; not a real path)

Pattern 4: "/proc/meminfo?lines=10"
  → file_path = "/proc/meminfo"
  → field = None (query params ignored, file read entire)
```

**Parsing Algorithm:**
1. Split by `|` (pipe); take the **first segment** only
2. Trim whitespace
3. If result contains `grep`, extract the grep word:
   ```
   "/proc/meminfo | grep MemAvailable" → field = "MemAvailable"
   ```
4. Otherwise, file_path is the entire first segment

### Allowlist: Permitted File Paths

**TIER 1 (Always Safe, No Restrictions):**
```
✓ /proc/meminfo
✓ /proc/cpuinfo
✓ /proc/loadavg
✓ /proc/uptime
✓ /proc/stat
✓ /proc/version
✓ /proc/net/tcp
✓ /proc/net/udp
✓ /etc/os-release
✓ /proc/sys/vm/swappiness
✓ /proc/sys/vm/dirty_ratio
✓ /proc/sys/vm/dirty_background_ratio
✓ /proc/sys/fs/file-max
✓ /proc/sys/kernel/pid_max
✓ /proc/pressure/* (any subdirectory under /proc/pressure/)
```

**TIER 2 (Conditional):**
```
✓ /proc/[pid]/stat (if pid is a valid, running PID and owned by caller or root)
✓ /proc/[pid]/status (if pid is valid, running, and owned by caller or root)
✓ /proc/[pid]/cmdline (if pid is valid, running, and owned by caller or root)
```

**TIER 3 (Forbidden):**
```
✗ /proc/sys/kernel/modules (kernel module state; risky)
✗ /proc/kcore (raw kernel memory; always forbidden)
✗ /proc/kmem (kernel memory; always forbidden)
✗ /proc/mem (userspace memory; always forbidden)
✗ /proc/sysvipc/* (IPC state; permission-sensitive)
✗ Anything under /sys/class/gpio or /sys/class/pwm (hardware control)
✗ Any path with ".." (path traversal attempt)
✗ Any path outside /proc or /sys or /etc (guard against symlink attacks)
```

### Forbidden Patterns (Content-Level Validation)

Even if the path is whitelisted, reject the LLM output if it contains:

```
✗ Pipes (|) — Only first segment before pipe is used; reject if more complex
✗ Semicolons (;) — Shell command separator
✗ Backticks (`) — Command substitution
✗ $(...) — Command substitution
✗ && or || — Logical operators
✗ > or >> or < — Redirection
✗ && (background operator)
✗ Newlines (except in multiline /proc reads for the same field)
```

**Enforcement:** If the raw LLM output (post-sanitization) contains any of these, reject with:
```
"Validation failed: path contains forbidden characters. Allowed: /proc and /sys read-only operations only."
```

### Allowlist: Field Names

If the LLM suggests a field via `grep`, validate that the field exists in the expected file:

```
/proc/meminfo valid fields:
  MemTotal, MemFree, MemAvailable, Buffers, Cached, SwapTotal, SwapFree, 
  Dirty, Writeback, AnonPages, Mapped, Shmem, KReclaimable, Slab, ...

/proc/cpuinfo valid fields:
  processor, vendor_id, cpu family, model, model name, stepping, cores, ...

/proc/stat valid fields:
  cpu, cpu0, cpu1, ... (cpu line and per-cpu lines)

/proc/sys/vm/* valid fields:
  (integer values, no field parsing needed)

/proc/pressure/* valid fields:
  avg10, avg60, avg300 (for each section: some/cpu, some/memory, etc.)
```

**Field Validation:** If a field is suggested (via grep) but doesn't exist, return:
```
"Field not found in file. Try one of: [valid fields]"
```

### Permission Checks (Linux-Specific)

Before reading, verify permissions:

```python
1. Try to open(file_path, 'r')
2. If PermissionError:
   - Check if root: escalate? (NO — demo server runs as regular user)
   - Return: "Permission denied. Try a world-readable source like /proc/meminfo"
3. If FileNotFoundError:
   - Return: "File not found. Verify the path and try again."
4. If IsADirectoryError:
   - Return: "Path is a directory, not a file. Provide a specific file."
```

---

## Part 3: Container, WSL, and Permission Quirks (Parity-Critical)

### Container Detection and Behavior

**Symptom:** `/proc/self/cgroup` shows `docker`, `lxc`, `systemd-nspawn`, or `kubelet` markers.

**What LLMs Might Not Know:**
1. Container root (UID 0) != host root; no privilege escalation possible
2. Process namespace isolation: `ls /proc` only shows container's own PID namespace
3. `/proc/meminfo` shows **container's memory limit**, not host memory
4. `/sys/class/thermal/` may not exist (no access to hardware)

**M6 Server Responsibility:**
- Do NOT escalate to root (it won't help in containers)
- Gracefully handle `PermissionError` (regular behavior)
- Document in results: "This is a container; system metrics reflect the container, not the host."
- Do NOT try to read `/sys` files that require root (e.g., `/sys/kernel/debug`, `/sys/class/gpio`)

**Test Coverage:** Validation must pass on:
- Bare-metal Linux
- WSL2
- Docker container (as non-root)
- Kubernetes pod (as non-root)

### WSL2-Specific Behavior

**Quirk 1: Interop Processes**
- Windows processes are visible in `/proc` (with `[interop]` marker in state)
- Trying to kill them via SIGTERM/SIGKILL is unpredictable
- For M6, this is not a blocker (we're only **reading** `/proc`)

**Quirk 2: `/proc/version` Contains "microsoft" or "WSL"**
```
WSL2: "... microsoft ... WSL2"
Bare-metal: "... #1 SMP ... GNU/Linux"
```
Use this to detect WSL if needed for diagnostics logging.

**Quirk 3: `/proc/meminfo` Reports WSL2's Allocated Memory**
- Not the host's memory (which may be larger)
- This is correct for the container/namespace scope; no special handling needed

**Quirk 4: `/proc/net/tcp` Shows WSL2's Socket Namespace**
- No visibility to host networking
- Correct behavior; no special handling needed

**M6 Server Responsibility:**
- No WSL-specific code paths (all sources work identically)
- Document if WSL2 is detected (informational only)
- Do not assume WSL == root access (it doesn't)

### Permission Model (Non-Root Safety)

**As Non-Root User (uid=1000):**
```
✓ Can read:
  - /proc/meminfo, /proc/cpuinfo, /proc/loadavg, /proc/uptime
  - /proc/stat, /proc/version, /proc/net/tcp
  - /etc/os-release
  - /proc/pressure/* (if kernel is 5.0+)

✗ Cannot read:
  - /proc/[pid]/stat (where pid is owned by another user)
  - /proc/[pid]/status (where pid is owned by another user)
  - /proc/kcore, /proc/kmem
  - /sys/class/gpio, /sys/class/pwm
  - /proc/slabinfo, /proc/modules (requires root)

✓ Can read (own process):
  - /proc/self/stat
  - /proc/self/status
  - /proc/self/cmdline
  - /proc/[self_pid]/fd (own file descriptors)
```

**M6 Behavior:**
- If LLM suggests `/proc/[pid]/stat` for another user's process → PermissionError → Graceful error
- If LLM suggests `/proc/kcore` → PermissionError → Graceful error
- Do NOT escalate; return "Permission denied" and suggest alternatives

### Path Traversal and Symlink Attacks

**Attack 1: Path Traversal**
```
Input: "/proc/meminfo/../../../etc/passwd"
After normalization: "/etc/passwd"
Result: NOT in allowlist → REJECT
```

**Attack 2: Symlink to Sensitive File**
```
Attacker creates: /tmp/test_symlink → /proc/kcore
Input: "/tmp/test_symlink"
Result: Not in /proc or /sys → REJECT
```

**M6 Server Responsibility:**
1. **Normalize paths:** Use `os.path.normpath()` to resolve `..` and `.`
2. **Whitelist by prefix:** After normalization, check if path starts with one of:
   - `/proc/`
   - `/sys/`
   - `/etc/os-release` (exact match)
3. **Reject if not in allowlist:** Even if the file is world-readable, reject if not explicitly allowed

**Code Pattern:**
```python
import os

def validate_path(raw_path: str) -> tuple[bool, str]:
    """Validate path against allowlist."""
    # Sanitize
    normalized = os.path.normpath(raw_path)
    
    # Check for traversal
    if ".." in normalized:
        return False, "Path traversal detected"
    
    # Whitelist check
    if not (normalized.startswith("/proc/") or 
            normalized.startswith("/sys/") or 
            normalized == "/etc/os-release"):
        return False, f"Path not in allowlist: {normalized}"
    
    # Check forbidden patterns
    if any(forbidden in normalized for forbidden in ["/kcore", "/kmem", "/mem", "/gpio"]):
        return False, "Path contains forbidden keyword"
    
    return True, normalized
```

### Namespace Isolation Edge Cases

**Edge Case 1: PID Namespace**
- `/proc/[pid]/stat` in a container shows container-local PIDs
- PID 1 in a container is the container's init, not the host's systemd
- This is correct; no special handling needed

**Edge Case 2: Mount Namespace**
- The `/proc` filesystem is namespace-local
- `/proc/mounts` shows the container's mounts, not the host's
- Correct behavior

**Edge Case 3: User Namespace**
- UID 0 in a container may not be UID 0 on the host (unprivileged containers)
- Reading `/proc/[host_pid]/stat` will fail with PermissionError
- This is correct; gracefully handle

**M6 Server Responsibility:**
- Do NOT special-case namespaces; let permission errors propagate naturally
- Document: "This server respects kernel namespace isolation. Cross-namespace access requires root."

---

## Part 4: Retry and Error Handling (Sampling Loop)

Ash must implement this retry pattern (from Bishop's M6 spec):

```python
async def troubleshoot_linux_diagnostics(server, user_request: str):
    """Sampling-assisted /proc diagnostics with retries."""
    
    max_retries = 4
    validation_errors = []
    
    for attempt in range(max_retries):
        # Phase 1: Sample LLM to suggest a /proc path
        prompt = f"""
        User request: {user_request}
        Previous validation errors: {validation_errors}
        
        Return a single valid Linux /proc or /sys file path to read.
        Example: /proc/meminfo
        Example: /proc/loadavg
        Do NOT return shell commands, pipes, or complex paths.
        Only the file path.
        """
        
        llm_output = await server.sample_async(prompt)
        
        # Sanitize
        path = sanitize_llm_output(llm_output)
        
        # Validate
        is_valid, normalized_path = validate_path(path)
        if not is_valid:
            validation_errors.append(f"Invalid path: {normalized_path}")
            continue
        
        # Phase 2: Try to read
        try:
            content = read_file_safe(normalized_path)
            
            # Phase 3: Sample LLM to summarize
            summary_prompt = f"""
            User asked: {user_request}
            We read: {normalized_path}
            Content: {content}
            
            Provide a concise summary for the user.
            """
            
            summary = await server.sample_async(summary_prompt)
            return summary
            
        except PermissionError as e:
            validation_errors.append(f"Permission denied: {e}")
        except FileNotFoundError as e:
            validation_errors.append(f"File not found: {e}")
    
    return f"Failed to retrieve diagnostics after {max_retries} attempts. Errors: {validation_errors}"
```

---

## Part 5: Teaching Value (Why These Constraints Matter)

### For Students

1. **Kernel Interfaces are Stable:** The `/proc` filesystem has been stable since Linux 2.0. It's a core kernel API, not a library hack.
2. **Namespace Isolation is Real:** Containers don't magically become the host. Permission errors are features, not bugs.
3. **LLMs Need Guardrails:** Even a capable LLM needs server-side validation. Blindly executing LLM output is a security antipattern.
4. **Cross-Platform Parity:** The same Linux diagnostics code works on bare-metal, WSL, and containers because `/proc` is portable.

### For Instructors

1. **Contrast with Windows:** C# M6 validates WQL (high-level query language). Python M6 validates file paths (low-level kernel interface). Same pedagogical pattern; different domains.
2. **Elicitation + Sampling:** M5 (elicitation) asks the user. M6 (sampling) asks the LLM. Both are critical for safe AI integration.
3. **Errors as Learning:** Non-root permission errors, namespace isolation, path validation failures are all *teaching moments*, not failures.

---

## Part 6: Implementation Checklist for Ash

- [ ] **Sanitization:** Remove markdown artifacts, comments, whitespace
- [ ] **Parsing:** Extract file path and optional field name from LLM output
- [ ] **Validation:** Check against allowlist; reject forbidden patterns
- [ ] **Permission Checks:** Gracefully handle PermissionError, FileNotFoundError
- [ ] **Retries:** Loop up to 4 times; accumulate validation errors for LLM feedback
- [ ] **Summary Sampling:** After reading, ask LLM to summarize for the user
- [ ] **Container Testing:** Verify on bare-metal, WSL2, and Docker container (non-root)
- [ ] **Error Messages:** Clear, actionable feedback for validation failures
- [ ] **Logging:** Record which /proc files were accessed (for audit/debugging)

---

## Part 7: Non-Blockers and Deferred Complexity

1. **Kernel Build Flags:** Some /proc files are missing on minimal kernels (e.g., /proc/pressure/ on older kernels). Handle gracefully with FileNotFoundError.
2. **Cgroup v1 vs v2:** /proc/cgroups format differs. For M6, use only the stable sources (meminfo, cpuinfo, loadavg).
3. **NUMA Systems:** /proc/zoneinfo is complex. Deferred to M7+; not recommended for M6.
4. **LSM (AppArmor, SELinux):** Some distributions restrict /proc reads even for world-readable files. Handle PermissionError gracefully.

---

## Part 8: Evidence and References

- **Linux Kernel Docs:** `/proc` filesystem interface (stable since 2.0)
- **Existing M5 Code:** `src/mcp_linux_diag_server/tools/processes.py` (permission-aware process reading)
- **Existing M5 Code:** `src/mcp_linux_diag_server/tools/system_info.py` (safe /proc/cpuinfo and /proc/meminfo reading)
- **C# M6 Reference:** Bishop's `bishop-m6-delta.md` (WQL validation pattern to adapt)
- **MCP Sampling:** Protocol supports server calling client LLM; implementation pattern from C# precedent

---

## Decision Record

**What This Locks Down:**
1. Sampling-assisted diagnostics **only** access `/proc`, `/sys`, `/etc/os-release` files
2. Server-side validation is **mandatory** before any file read
3. Path traversal, symlinks, and permission escalation are **forbidden**
4. Retries loop up to **4 times** with accumulated error feedback
5. Container, WSL, and non-root scenarios **must work without special code**

**What This Enables:**
1. Safe, LLM-guided exploration of Linux diagnostics
2. Clear, actionable error messages for validation failures
3. Cross-platform parity (bare-metal, WSL, containers)
4. Strong pedagogical model (sampling + guardrails = safe AI)

**Acceptance:** Ash (Python Dev) and Newt (Tester) sign off on implementation. This decision is final for M6.

---

**Next:** Implementation phase (Ash) with validation (Newt). No further Linux diagnostics design needed.
