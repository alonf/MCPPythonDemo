# Newt: Milestone 6 second review decision

**Date:** 2026-04-14  
**Status:** Reject current `milestone-6` candidate

## Decision

Do **not** accept the current Milestone 6 artifact yet.

## Why

The branch now contains real M6 work:

- `troubleshoot_linux_diagnostics` is exposed
- server-side sampling validation/retry logic exists
- the lecture client now supports sampling callbacks
- targeted M6 tests pass under `python3 -m unittest discover -s tests -q`

But the repo's documented smoke lane still fails:

- `python3 scripts/smoke_test.py` aborts in the M6 diagnostics step
- cause: `_smoke_sampling_callback()` returns JSON (`{"path": "/proc/meminfo", "field": "Dirty"}`) while `validate_linux_diagnostic_query()` now requires `PATH` or `PATH | grep FIELD`
- result: the tool retries four times, then returns validation failure text, and the smoke script raises `RuntimeError`

## Blocker

Milestone acceptance requires the repo's own regression/smoke commands to pass, not just the unit suite. Until the smoke harness is updated to match the implemented sampling contract and rerun green, this artifact stays rejected.

## Required reviser

Use **Ash** for the next revision, not Dallas. The blocker is now Python implementation/test alignment, not Linux source-selection design.
