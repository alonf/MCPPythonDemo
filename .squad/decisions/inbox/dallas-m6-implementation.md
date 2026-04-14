# Dallas: M6 implementation revision notes

- Revised Milestone 6 sampling to use a single-line Linux target contract: `PATH` or `PATH | grep FIELD`.
- Server validation order is now: sanitize markdown/comments -> forbid shell syntax -> normalize path -> allowlist check -> concrete read -> summary sampling.
- Allowlist stays Linux-safe and world-readable by default (`/proc/meminfo`, `/proc/loadavg`, `/proc/stat`, `/proc/pressure/*`, `/proc/sys/*`, selected `/sys/fs/cgroup/*`, `/etc/os-release`, and guarded `/proc/[pid]/{stat,status,cmdline}`).
- Reads are intentionally bounded to short excerpts so `/proc` inspection remains cheap and explainable.
- WSL/container detection is informational only; no separate code path or privilege escalation was added.
- Regression expectation: later milestone prompts/tools are additive, so M1-M5 tests should verify preserved required surfaces without rejecting the new M6 prompt/tool set.
