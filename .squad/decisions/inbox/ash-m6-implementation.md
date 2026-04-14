# Ash: Milestone 6 Python implementation

**Date:** 2026-04-14  
**Status:** Implemented

## Decision

Implement Python Milestone 6 as a two-phase sampling workflow around a constrained Linux diagnostics query.

## Details

- Public tool: `troubleshoot_linux_diagnostics`
- Teaching shape preserved from C#: sample for a query, validate on the server, execute deterministically, then sample for a summary
- Exact Linux adaptation: the sampled query is a single safe `PATH` or `PATH | grep FIELD` line over an allowlisted `/proc` or `/sys` source
- Python SDK adaptation: the lecture client advertises sampling by supplying `sampling_callback` to `ClientSession`, which is the Python equivalent of the C# sampling handler pattern

## Why

- Keeps the parity-critical protocol/teaching flow intact without introducing arbitrary shell execution
- Leaves the server as the authority over every sampled request
- Fits the current Python MCP SDK surface cleanly
