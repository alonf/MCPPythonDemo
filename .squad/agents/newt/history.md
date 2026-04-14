# Project Context

- **Owner:** alon
- **Project:** Python Linux Diagnostics demo migrated from the C# MCPDemo repo and lecture
- **Stack:** Python, MCP, Microsoft Agent Framework, Linux diagnostics, `/proc`, Git branches
- **Created:** 2026-04-13T21:30:48.993Z

## Learnings

- QA must validate both the migrated Python behavior and the lecture-driven branch progression.
- Linux diagnostics scenarios need positive and negative coverage because system state varies across machines.
- The Python parity repo now validates three concrete lanes: MCP stdio smoke (`tests/test_m1_smoke.py`), `/proc` fallback behavior (`tests/test_system_info.py`), and chat-client parity/missing-config handling (`tests/test_client.py` and `scripts/smoke_test.py`).
- `src/mcp_linux_diag_server/tools/system_info.py` needed graceful degradation for missing `/proc/uptime`, `/proc/loadavg`, and `/proc/meminfo`; zero-valued fallbacks keep the demo alive instead of crashing.
- The current lecture client lives in `src/mcp_linux_diag_server/client.py` and expects Azure settings via `MCP_DEMO_AZURE_OPENAI_*` (with Azure aliases accepted in docs), so QA should always test the missing-config path explicitly.
- The lecture client does load `.env.local` by default, and `tests/test_client.py` now covers file parsing plus env-file precedence; QA should still exercise `--no-local-env` so missing-config guardrails do not silently regress.
- Live M1 validation in WSL works via `.env.local` plus `MCP_DEMO_AZURE_OPENAI_USE_DEFAULT_CREDENTIAL=true`; no extra shell export was needed once Azure CLI auth existed locally.
- The cleanest proof of a true end-to-end lecture run is the single-prompt client trace from `src/mcp_linux_diag_server/client.py`: `Connected to MCP server`, then `[tool] get_system_info({})`, then a model-written JSON answer.
- `scripts/smoke_test.py` is still a preflight smoke, not a live-auth smoke: it proves server startup and the client's missing-config guardrail, but not a successful Azure-backed completion.

---

## Team Updates (2026-04-13T22:03:56Z Orchestration)

### M1 Scope & Architecture (Ripley)
- STDIO server + single get_system_info tool defined
- Clear boundaries: stdlib + /proc/uptime only (M1 scope)
- Deferred: psutil (M2), journalctl (M3), HTTP (M4)

### M1 Linux Data Sources (Dallas)
- /etc/os-release, /proc/cpuinfo, /proc/meminfo, /proc/loadavg specified
- Confirmed no WSL-specific code; works identically WSL and bare-metal
- Error handling: graceful degradation pattern established

### M1 Validation Approach (Newt)
- **Completed:** Concrete test harness with JSON-RPC smoke tests (4 core + 6 edge cases)
- Provided Python test runner code (test_m1_server.py)
- QA sign-off checklist ready for implementation verification
- Expected response schemas fully specified

### M1 Implementation (Ash)
- STDIO server + get_system_info tool complete and packaged
- All 9 required fields with graceful error handling
- Tests and documentation finished

**Status:** M1 validation artifacts ready. Awaiting Ash implementation to run tests.

## 2026-04-13T22:36:32Z: M1 Parity QA Validation Complete

- Validated Python M1 parity flow end-to-end with server plus client
- Test coverage: fake-model automation lane for tool-calling flow; real CLI preflight for Azure validation
- Fixed proc fallback bug: get_system_info now degrades to zeroed snapshots on missing files (soft failure)
- QA Decision: Official smoke tests use Python MCP SDK client, not handwritten JSON-RPC
- Status: Approved for production; ready for M1 closure


---

## Team Updates (2026-04-14T07:15:48Z — Milestone 1 Live Run Sign-Off)

### Ash: Live M1 Validation Complete ✅

- Confirmed M1 works end-to-end in WSL with Azure CLI login + `.env.local`
- Python client successfully called `get_system_info` via MCP and received Azure OpenAI response
- No code changes needed; auth flow proven ready for lecture use
- Key evidence: single authenticated run showing `Connected to MCP server` + `[tool] get_system_info({})` + usable LLM answer

### Newt: QA Sign-Off ✅

- Independently validated Ash's live run output
- All three required markers present in single output stream
- Approved M1 for production lecture demonstration
- Caveat noted: smoke test covers server startup + missing-config paths, not live Azure success (now proven separately)
