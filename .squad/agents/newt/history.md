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
- Milestone 2 QA now covers process inspection in two lanes: mocked `/proc` unit checks for pagination/fallback behavior and SDK-driven stdio smoke tests against a real sleeper subprocess.
- `get_process_list` reaches clients as a top-level list wrapped under `structuredContent.result`; tests should normalize that MCP transport shape before asserting payload contents.
- Repro-safe live process validation on Linux/WSL works with `python3 -c 'import time; time.sleep(30)'`, which avoids privilege needs and gives stable PID-based assertions for list/by-id/by-name coverage.


---

## Team Updates (2026-04-14T13:00:00Z — Milestone 2 Delivery Complete)

### Milestone 2 Process Tools Delivered ✅

- **Ash:** Implemented Linux `/proc`-backed process tools on `milestone-2` branch
  - `get_process_list`: Full process enumeration with paging (default: 5 per page)
  - `get_process_by_id`: Per-PID detail snapshot with stat + status metrics
  - `get_process_by_name`: Filtered list with regex matching and paging
  - Updated server guidance and lecture client examples
  - No external dependencies added; `/proc` kept intentional to teach kernel diagnostics

- **Newt:** Comprehensive test coverage delivered
  - Unit tests (`tests/test_processes.py`): `/proc` parsing edge cases, fallback behavior, pagination cursor logic
  - Integration smoke (`tests/test_m2_smoke.py`): SDK-driven stdio validation against live sleeper subprocess
  - Full test suite passes: `python3 -m unittest discover -s tests -v` ✅
  - Smoke test passes: `python3 scripts/smoke_test.py` ✅

### Technical Achievements

- **Data source decision:** Linux `/proc` direct reads (not `psutil`) ratified in D6
- **Test strategy:** Dual lanes (unit + smoke) ratified in D7
- **Branch model:** `milestone-1` public, `milestone-2` squad-enabled ratified in D8
- **Documentation:** README/roadmap updated; M2 complete, M3+ deferred

### Decisions Merged to decisions.md

D6, D7, D8 from decision inbox merged:
- `decisions/inbox/ash-m2.md` → decisions.md (D6)
- `decisions/inbox/newt-m2-tests.md` → decisions.md (D7)
- `decisions/inbox/ripley-branch-model.md` → decisions.md (D8)
- Inbox files cleared

### Squad Status

- All agents reported completion
- Session log saved: `.squad/log/2026-04-14T13:00:00Z-milestone-2-delivery.md`
- Cross-agent history appended to agent files
- Ready for publication or M3 planning

---

## Team Updates (2026-04-14T13:50:00Z — Milestone 4 QA Validation)

### Milestone 4 HTTP Transport Validated ✅

- Added explicit M4 transport coverage in `tests/test_m4_http.py` for auth rejection, query-string auth, session-header enforcement, and end-to-end M1-M3 surface reachability over `/mcp`.
- Confirmed existing milestone smoke tests (`tests/test_m1_smoke.py`, `tests/test_m2_smoke.py`, `tests/test_m3_smoke.py`) now exercise the HTTP transport via a reusable free-port harness instead of stdio-only launch assumptions.
- Updated `scripts/smoke_test.py` to run raw HTTP checks plus SDK-backed HTTP checks on an ephemeral port, which avoids false failures from local port-5000 collisions.
- Validation result: `python3 -m unittest discover -s tests -v` passed (46 tests) and `python3 scripts/smoke_test.py` passed.
- Reviewer-grade issues found: none. The branch currently meets the M4 target claims that were exercised.
