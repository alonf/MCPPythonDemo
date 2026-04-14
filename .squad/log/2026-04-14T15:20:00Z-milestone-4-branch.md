# Milestone 4 Branch Creation & Delta Analysis

**Date:** 2026-04-14T15:20:00Z  
**Phase:** M4 Planning & Branch Setup

## Summary

Ripley created `milestone-4` branch from clean M3 baseline (commit 3b3c09e). Bishop completed comprehensive delta analysis from C# M4 implementation. Branch is ready for Ash's implementation work.

## Branch Setup Outcome

- **Branch point:** `origin/milestone-3` commit 3b3c09e "Consolidate Milestone 3 squad memory for Milestone 4"
- **Local branch:** Created and tracking origin
- **Status:** Clean worktree, ready for implementation
- **Key preservation:** All M3 squad memory and implementation included

## C# → Python M4 Delta Analysis (Bishop)

### Transport Architecture Shift
- **Old (M3):** STDIO protocol, `Host.CreateApplicationBuilder()`, implicit session (single stream)
- **New (M4):** HTTP streamable, `WebApplication.CreateBuilder()`, explicit session ID header tracking

### Parity-Critical Components
1. **HTTP Server:** FastAPI `/mcp` endpoint on configurable port
2. **API Key Middleware:** Validate `X-API-Key` header or `apiKey` query param
3. **Session ID Tracking:** Return `mcp-session-id` response header
4. **Streamable Transport:** MCP SDK handles automatic streaming; Python must support SSE parsing if needed
5. **Test Scripts:** Native HTTP POST validation (no mcp-cli dependency)
6. **Config:** `.vscode/mcp.json` updated for HTTP transport

### Optional Enhancements
- Custom logging formatter (color-coded method names) — pedagogical, not required
- Documentation polish explaining HTTP workflow

### Python M4 Scope
- **Core changes:** ~150–200 lines (FastAPI setup, middleware, session handling)
- **Optional logging:** ~100–150 lines
- **Tests:** Full dual-lane coverage (raw HTTP + SDK)
- **No new MCP features:** All M1–M3 tools/resources/prompts unchanged

## Decisions Ratified

- **D11:** M4 transport architecture (HTTP + API key + session ID)
- **D12:** Constants centralization for HTTP config
- **D13:** Dual-lane validation (raw HTTP + SDK coverage)
- **D14:** M4 branch model (from clean M3 baseline)

## Next Steps

Ash begins implementation: FastAPI setup, middleware, constants module, and test harness.

---

**Prepared by:** Scribe  
**For team:** Ash (implementation), Bishop (parity review), Newt (validation)
