---
date: 2026-04-14
author: Dallas
status: DECISION
scope: Milestone 7 forbidden proc/sys path enforcement
---

# M7 Revision: Forbidden paths short-circuit before approval flow

Milestone 7's proc/sys sandbox now treats forbidden classes as a separate safety barrier from the allowlist.

## Decision

- Reject forbidden proc/sys paths **immediately after normalization**.
- Do this before any `stat()`, `realpath()`, snapshot creation, elicitation, or allowlist expansion.
- `request_proc_access` is only for paths that are outside the current allowlist **but still eligible** for read-only snapshotting.
- `ProcRootsService.add_allowed_root()` must refuse forbidden paths so approval flow bugs cannot silently widen the sandbox.

## Covered classes

- Exact: `/proc/kcore`, `/proc/kmem`, `/proc/mem`
- Prefixes: `/proc/sysvipc`, `/sys/class/gpio`, `/sys/class/pwm`, `/sys/kernel/debug`

## Why

These are category-level safety exclusions, not normal "blocked until approved" paths. Treating them as allowlist misses would let clients request approval for kernel memory, IPC internals, or hardware/debug surfaces, which violates the Milestone 7 teaching contract.

## Release note

Do not mirror Milestone 7 onto `master` until this forbidden-path guard is present **and** Newt clears the re-review.
