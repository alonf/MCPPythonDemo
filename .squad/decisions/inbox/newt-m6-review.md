# Newt: Milestone 6 validation review

**Date:** 2026-04-14  
**Status:** Reject current `milestone-6` branch

## Reviewer-grade validation criteria

Milestone 6 is acceptable only if all of the following are true:

1. `tools/list` advertises a public M6 tool for sampling-assisted Linux diagnostics (`troubleshoot_linux_diagnostics` or equivalent documented name).
2. The server implements a deterministic internal query step separate from reasoning, with validation that rejects unsafe sampling output (`..`, shell metacharacters, disallowed paths, multi-step commands).
3. The server retries sampling-generated queries after validation failures instead of executing unsafe output.
4. The tool can read an allowed proc/sys source and return a natural-language diagnosis produced through sampling.
5. The client advertises sampling capability and provides a sampling handler, not just tool-calling plus elicitation.
6. Tests/smoke coverage includes both happy path and failure path for the new sampling workflow.
7. Existing M1-M5 regression commands still pass.

## What I validated

- Read the M6 delta spec in `bishop-m6-delta.md`, current roadmap/docs, server/client code, and existing tests/smoke harness.
- Confirmed current branch tip is still commit `393f278`, the same published Milestone 5 baseline.
- Ran:
  - `python3 -m unittest discover -s tests -q`
  - `python3 scripts/smoke_test.py`

## Result

Regression baseline is green, but **Milestone 6 is not implemented on this branch**.

Concrete blockers:

1. No M6 tool is exposed: current tool surface is still `get_system_info`, process tools, `kill_process`, and `create_log_snapshot`.
2. No server-side sampling-assisted diagnostics flow exists.
3. No proc-query allowlist/validation layer for sampling output exists.
4. No retry loop for invalid model-generated queries exists.
5. No client sampling capability/handler exists; client code currently supports tool calling and elicitation only.
6. No M6-focused automated tests exist.
7. Docs (`README.md`, `docs/MCPDemoRoadmap.md`) still describe M6 as planned, which matches the code and contradicts any acceptance claim.

## Revision owner

Reject M6 as currently implemented. Recommend **Dallas** for revision, since the blockers are dominated by Linux data-source mapping and safety validation for sampling-generated proc/sys queries. After Dallas lands the implementation, send it back to QA for a fresh acceptance pass.
