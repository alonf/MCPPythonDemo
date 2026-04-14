# Newt: Final M7 review gate

- **Date:** 2026-04-14
- **Outcome:** Reject

## Why

- The published validation lane is green: `python3 -m unittest discover -s tests -q` passed and `python3 scripts/smoke_test.py` passed.
- The implementation still misses a parity-critical safety rule from the confirmed M7 target: forbidden proc/sys paths are supposed to reject before elicitation or allowlist expansion.
- Repro evidence from the current worktree:
  - `validate_proc_snapshot_path("/proc/kcore", require_allowed_root=False)` succeeds.
  - `ProcRootsService.instance().add_allowed_root("/proc/kcore")` succeeds.
  - `validate_proc_snapshot_path("/proc/kcore")` then succeeds.
- That means a client could approve `/proc/kcore` via `request_proc_access`, which violates the M7 forbidden-path contract rather than enforcing it.

## Reviewer decision

- Do **not** commit/publish this as final Milestone 7 yet.
- Do **not** copy this exact uncommitted state onto `master` yet.
- Next revision author should be **Dallas**, because the required fix is about enforcing the Linux safety boundary that M7 is supposed to teach.
