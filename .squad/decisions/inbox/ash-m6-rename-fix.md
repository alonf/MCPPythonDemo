# Ash: M6 rename fix

**Date:** 2026-04-14  
**Status:** Implemented

## Decision

Rename the Milestone 6 diagnostics helper module from `m6_diagnostics.py` to `linux_diagnostics.py` and keep milestone labels out of Python module filenames.

## Details

- Updated the tracked module path under `src/mcp_linux_diag_server/tools/`
- Repointed package exports and test imports to `mcp_linux_diag_server.tools.linux_diagnostics`
- Updated the squad sampling skill note so team references match the new module path

## Why

- Milestone labels belong in branch/docs context, not in long-lived Python import paths
- Domain-based filenames make later maintenance and cross-milestone reuse less awkward
