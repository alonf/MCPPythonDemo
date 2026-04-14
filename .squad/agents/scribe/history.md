# Project Context

- **Owner:** alon
- **Project:** Python Linux Diagnostics demo migrated from the C# MCPDemo repo and lecture
- **Stack:** Python, MCP, Microsoft Agent Framework, Linux diagnostics, `/proc`, Git branches
- **Created:** 2026-04-13T21:30:48.993Z

## Core Context

Scribe tracks migration decisions, branch mapping, and lecture-derived constraints for the Python demo.

## Recent Updates

📌 Team initialized on 2026-04-13

📌 **M1–M3 implementation and validation complete** (2026-04-14T14:00Z)
- M3 branch pushed with full event log resources, prompts, snapshot pagination
- Agent histories consolidated with learnings

📌 **Milestone 4 planning & implementation complete** (2026-04-14T15:30Z)
- M4 branch created from clean M3 baseline (3b3c09e)
- HTTP transport layer implemented with API key authentication
- Dual-lane validation passed (raw HTTP + SDK)
- M4 decisions (D11–D14) merged to decisions.md
- Publication wrap-up phase active; no outstanding product changes

## Learnings

- The migration source of truth is the C# MCPDemo repository plus the lecture PDF under `docs/`.
- Scribe should preserve repo-analysis findings and anything that changes the migration plan.
- Transport-layer milestones (M4) are straightforward to port: adapt host framework (Host → WebApplication for C#, STDIO → FastAPI for Python), wire middleware, update tests.
- Constants centralization eliminates drift across test harnesses, config files, and client code.
- Dual-lane validation (raw HTTP + SDK coverage) catches transport regressions the abstraction layer can hide.
- Ephemeral port allocation prevents fixed-port collisions during parallel validation.
