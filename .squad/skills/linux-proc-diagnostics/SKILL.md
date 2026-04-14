# Linux /proc Diagnostics Parsing Skill

**Author:** Dallas (Linux Diagnostics Expert)  
**Date:** 2026-04-14  
**Purpose:** Reliable parsing of Linux /proc interfaces for diagnostics tools, MCP servers, and system monitoring.

## Overview

Linux `/proc` and `/sys` are the primary sources of system diagnostics data. Unlike Windows WMI (object-oriented), 
these are raw, ephemeral, text-based kernel interfaces. This skill documents the patterns for safe, robust parsing.

## Core Principle

> **/proc is the truth layer.** Always read fresh. Cache strategically. Handle races gracefully.

## Key Files & Formats

### System-Level Diagnostics

**`/proc/meminfo`** - Memory usage (read-only, always available)
```
MemTotal:       8167848 kB
MemFree:        2048576 kB
MemAvailable:   3145728 kB
Buffers:         102400 kB
Cached:         1024000 kB
...
```
**Pattern:** Key-value pairs, values in kB. Safe for non-root.

**`/proc/cpuinfo`** - CPU info (read-only, always available)
```
processor       : 0
vendor_id       : GenuineIntel
cpu family      : 6
...
```
**Pattern:** Colon-separated; processor lines repeat per core.

**`/proc/loadavg`** - Load average (read-only, always available)
```
0.45 0.52 0.48 2/412 12345
```
**Pattern:** 5 fields: 1m avg, 5m avg, 15m avg, tasks running/total, last pid. Always safe.

### Process-Level Diagnostics

**`/proc/[pid]/stat`** - Process CPU/memory snapshot (ephemeral, permission-guarded)
```
12345 (bash) S 1 12345 12345 0 -1 4218880 15234 0 0 0 234 12 0 0 20 0 1 0 123456789 45678912 1234
```
**Pattern:** Space-separated fields; #1=pid, #2=comm, #3=state (S=sleeping, R=running, Z=zombie).
- Fields 13,14: utime, stime (jiffies)
- Field 23: vss (virtual set size)
- Field 24: rss (resident set size, in pages)

**Race condition:** PID may exit between listing `/proc` and reading `/proc/[pid]/stat`. Wrap in try/except.

**Permission:** Non-root can read own process; cannot read others' by default (depends on ptrace_scope).

**`/proc/[pid]/status`** - Process metadata (human-readable alternative to stat)
```
Name:   bash
State:  S (sleeping)
Tgid:   12345
Pid:    12345
PPid:   1
VmPeak:  45678 kB
VmSize:  40960 kB
VmRSS:   8192 kB
...
```
**Pattern:** Human-readable format. Same data as stat but easier to parse selectively.

**`/proc/[pid]/cmdline`** - Full command line (null-separated)
```
/bin/bash\0-i\0
```
**Pattern:** Null-terminated strings. Safe to read; may be empty for kernel threads.

**`/proc/[pid]/fd/`** - Open file descriptors (directory with symlinks)
```
lrwx------ 1 user user 64 Jan 1 00:00 0 -> /dev/pts/0
lrwx------ 1 user user 64 Jan 1 00:00 1 -> /dev/pts/0
lr-x------ 1 user user 64 Jan 1 00:00 3 -> /var/log/syslog
```
**Pattern:** Directory with numbered symlinks. Ownership reflects process owner.

**Race condition:** fds can appear/disappear during scan. List once; handle missing on individual read.

### Log Diagnostics

**`journalctl --json`** - Structured logs from systemd journal (preferred)
```json
{"MESSAGE":"error occurred","PRIORITY":3,"_PID":"12345"}
```
**Pattern:** One JSON object per line. Preserves timestamps, PIDs, priority levels.

**`/var/log/syslog`** - Text-based syslog (fallback)
```
Jan  1 00:00:01 hostname process[12345]: message text
```
**Pattern:** Space-separated; parse with regex or syslog parser library. Fragile across distros.

## Parsing Patterns

### Pattern 1: Safe /proc File Read with Fallback

```python
def read_proc_file(path, default=None):
    """Read /proc file; return default on permission error or race condition."""
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except (OSError, IOError) as e:
        # Permission denied, file deleted (race), etc.
        return default
```

**Why:** /proc files can disappear (PID exit), be unreadable (permissions), or change mid-read.

### Pattern 2: Scan /proc for List (with Race Tolerance)

```python
import os
import glob

def list_processes():
    """List all PIDs; tolerate races where PID directory vanishes."""
    pids = []
    for pid_dir in sorted(glob.glob('/proc/[0-9]*')):
        pid = int(os.path.basename(pid_dir))
        try:
            stat_path = os.path.join(pid_dir, 'stat')
            with open(stat_path) as f:
                # If we reach here, PID is still alive
                pids.append(pid)
        except (OSError, IOError):
            # PID exited between listing and reading; skip
            pass
    return pids
```

**Why:** Between `glob` and `open`, PID may exit. Silently skip these.

### Pattern 3: Parse /proc/[pid]/stat into Fields

```python
def parse_proc_stat(stat_line):
    """Parse /proc/[pid]/stat into usable fields."""
    # stat format: pid (comm) state ppid ...
    # comm can contain spaces and parens, so parse carefully
    fields = stat_line.split()
    pid = int(fields[0])
    comm = fields[1].strip('()')  # field 2 is wrapped in parens
    state = fields[2]
    ppid = int(fields[3])
    utime = int(fields[13])  # user time in jiffies
    stime = int(fields[14])  # system time in jiffies
    vss = int(fields[22])    # virtual size in bytes
    rss = int(fields[23]) * 4096  # RSS in pages → bytes
    return {'pid': pid, 'comm': comm, 'state': state, 'utime': utime, 'stime': stime, 'vss': vss, 'rss': rss}
```

**Why:** stat format is space-separated but fragile (comm can contain spaces). Use split + index.

### Pattern 4: Read /proc/[pid]/status for Human-Readable Fields

```python
def parse_proc_status(pid):
    """Read /proc/[pid]/status and extract key fields."""
    result = {}
    try:
        with open(f'/proc/{pid}/status', 'r') as f:
            for line in f:
                key, val = line.split(':', 1)
                key = key.strip()
                val = val.strip()
                if key in ['Name', 'State', 'VmPeak', 'VmSize', 'VmRSS']:
                    result[key] = val
    except (OSError, IOError):
        pass
    return result
```

**Why:** status is line-based, not fragile; safer than parsing stat.

### Pattern 5: Handle Permission Errors Gracefully

```python
def get_process_info(pid):
    """Get process info; return partial data if non-root."""
    info = {'pid': pid}
    
    # Try to read cmdline (may fail for other users' processes)
    try:
        with open(f'/proc/{pid}/cmdline', 'r') as f:
            info['cmdline'] = f.read().replace('\0', ' ').strip()
    except PermissionError:
        info['cmdline'] = '<permission denied>'
    except (OSError, IOError):
        return None  # PID likely exited
    
    # Read status (safer; usually readable)
    status = parse_proc_status(pid)
    info.update(status)
    
    return info
```

**Why:** Some files are readable only by process owner. Graceful fallback improves UX.

## Linux-Specific Gotchas

### 1. Jiffies vs Seconds

`/proc/[pid]/stat` uses jiffies (HZ ticks). Convert: `seconds = jiffies / os.sysconf('SC_CLK_TCK')`

### 2. Virtual vs Resident Memory

- **VmSize (VSS):** Total virtual memory allocated (includes swapped, unused pages).
- **VmRSS (RSS):** Physical RAM in use.
- Neither is "memory leak" directly; must track over time.

### 3. Namespace Isolation

Containers see filtered `/proc/[pid]/` (only own PID namespace). Host sees all.
**Implication:** /proc layout differs in container vs host.

### 4. cgroup v1 vs v2

Resource limits stored in `/sys/fs/cgroup/`. Format differs; use cgroup library if possible.

### 5. Ephemeral State

Never assume `/proc` state is consistent across two reads. Always cache snapshots for analysis.

## Testing Patterns

### Test 1: Non-Root Permission Errors

```bash
sudo python3 -c "
import os
# Run as non-root; read own process
pid = os.getpid()
print(open(f'/proc/{pid}/stat').read())
"
```

### Test 2: Detect Race Condition

```bash
python3 -c "
import os
pid = os.fork()
if pid == 0:
    os.execve('/bin/sleep', ['sleep', '0.001'], {})
else:
    # Parent reads PID's /proc between exit and reap
    try:
        open(f'/proc/{pid}/stat').read()
    except: pass
    os.waitpid(pid, 0)
"
```

### Test 3: Container Environment

```bash
docker run -it python:3.11 python3 -c "import os; print([x for x in os.listdir('/proc') if x.isdigit()])"
```

## Best Practices

1. **Always read fresh:** Don't cache `/proc` data across tool invocations.
2. **Snapshot for analysis:** M3 resource model: read once, store JSON, analyze offline.
3. **Handle races:** Wrap `/proc` reads in try/except; skip missing PIDs.
4. **Respect permissions:** Graceful fallback for non-root; document limitations.
5. **Cache at snapshot level:** Cache the snapshot file, not individual /proc reads.
6. **Test on multiple distros:** journalctl, cgroup formats vary; verify portability.

## References

- Linux man pages: `proc(5)`, `stat(2)`, `sysconf(3)`
- PSUtil library: Reference implementation for /proc parsing
- Kernel docs: /proc in linux kernel source
