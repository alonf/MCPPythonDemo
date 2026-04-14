---
date: 2026-04-14
author: Newt
status: DECISION
scope: Milestone 7 re-review after forbidden-path fix
---

# M7 Re-review: approved after forbidden-path short-circuit

## Decision

- Approve the revised Milestone 7 worktree.
- Forbidden proc/sys classes now reject before snapshot creation, before elicitation, and before allowlist expansion.
- `request_proc_access` remains limited to eligible-but-not-yet-allowed roots.

## Evidence run

- `python3 -m unittest tests.test_proc_snapshots tests.test_m7_http -q`
- `python3 -m unittest discover -s tests -q`
- `python3 scripts/smoke_test.py`
- Direct helper checks:
  - `validate_proc_snapshot_path("/proc/kcore", require_allowed_root=False)` raises `ValueError`
  - `ProcRootsService.instance().add_allowed_root("/proc/kcore")` raises `ValueError`

## Release impact

- Current worktree is ready to commit/publish.
- `master` and `milestone-7` currently point at the same commit, so `master` may safely carry the same final code as `milestone-7` once the reviewed worktree changes are committed.
