# Newt: M6 rename review

**Date:** 2026-04-14  
**Status:** Accepted

## Decision

Accept the Milestone 6 rename correction on `milestone-6`: the helper module now lives at `src/mcp_linux_diag_server/tools/linux_diagnostics.py`, and live imports/references were updated without breaking the M6 validation lanes.

## Evidence

- Verified the old code path `src/mcp_linux_diag_server/tools/m6_diagnostics.py` no longer exists.
- Verified package exports now import from `mcp_linux_diag_server.tools.linux_diagnostics`.
- Verified test imports now target `mcp_linux_diag_server.tools.linux_diagnostics`.
- Searched live repo surfaces and found `m6_diagnostics` only in historical squad notes, not in active product/test/docs paths under review.
- Ran:
  - `python3 -m unittest discover -s tests -q`
  - `python3 scripts/smoke_test.py`
  Both completed successfully.

## Low-risk cleanup

- Merge this acceptance note and Ash's rename note into the main decisions log when the publication bookkeeping pass happens.
