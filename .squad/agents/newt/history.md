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
- M5 reviewer pass criteria are now concrete: full `python3 -m unittest discover -s tests -q` plus `python3 scripts/smoke_test.py` must both pass, and `tests/test_m5_http.py` must prove both the no-elicitation failure path and a real confirmed subprocess termination path.
- Current M5 branch state matches the documented target that was claimed: `kill_process` is advertised, HTTP auth/session flow still works, prompts/resources remain reachable, and the lecture client exposes prompt/resource helper tools plus local terminal elicitation handling.
- Regression note: full-suite output is noisy because some client tests intentionally print `[tool] ...` and elicitation prompts, but the suite still completed cleanly (53 tests passing); treat the noise as cosmetic, not a blocker.
- M6 acceptance cannot be inferred from a green M5 regression suite alone; parity review must first prove the branch actually advertises the new M6 surface (`troubleshoot_linux_diagnostics` plus client sampling support) before existing smoke results matter.
- Current `milestone-6` branch still points at the M5 publication commit (`393f278`) and the docs still mark Milestone 6 as planned, so reviewer-grade QA should reject immediately on missing feature surface even when `python3 -m unittest discover -s tests -q` and `python3 scripts/smoke_test.py` both pass.
- For M6 specifically, required evidence must include negative guardrail checks around sampling-generated proc queries (allowlist, traversal/metacharacters, retry-on-invalid output) because those are the parity-critical safety claims, not optional hardening.
- Current M6 candidate is no longer "still M5": the server now advertises `troubleshoot_linux_diagnostics`, the client wires sampling callbacks, the roadmap/docs claim M6 complete, and targeted tests cover allowlist rejection plus retry-then-success.
- QA still cannot accept M6 unless the published smoke lane agrees with the implementation contract; this branch's `scripts/smoke_test.py` still feeds JSON (`{"path": ...}`) into a validator that now only accepts `PATH` or `PATH | grep FIELD`, so the documented smoke command fails even though the unit suite is green.
- Final M6 re-review passed once the smoke harness sampled the real contract (`/proc/...` or `/proc/... | grep FIELD`); acceptance evidence is now concrete: `python3 -m unittest discover -s tests -q` passed with 60 tests and `python3 scripts/smoke_test.py` completed green with the diagnostics lane exercising `troubleshoot_linux_diagnostics`.
- Reviewer-grade M6 acceptance depends on both parity surface and runnable proof: tool discovery, prompt discovery, client sampling support, validation/retry coverage, and the published smoke command must all agree on the same sampling callback contract.
- Rename-only follow-ups still need runnable proof: verify the milestone-labeled module path is gone from live code (`src/`, `tests/`, `scripts/`, docs/skills), confirm the domain-based import path loads through package exports, and rerun the full M6 regression lane (`python3 -m unittest discover -s tests -q` plus `python3 scripts/smoke_test.py`) before accepting the branch state.
- M7 QA should use one HTTP integration suite to prove both the new sandbox surface (`create_proc_snapshot`, `request_proc_access`, `proc://snapshot/...`) and additive safety guarantees, while still asserting the M3-M6 tools/prompts/resources remain discoverable as an unchanged subset.
- Green M7 regression lanes are not enough for sign-off unless QA also probes a known-forbidden proc/sys target (for example `/proc/kcore`) and proves the server rejects it before allowlisting or elicitation; the current implementation still lets that path normalize and be added as an allowed root.
- Dallas's forbidden-path revision closes the actual M7 gap only when three lanes agree: direct helper calls reject `/proc/kcore`, HTTP `request_proc_access` never reaches elicitation for that path, and the published regression commands (`python3 -m unittest discover -s tests -q` plus `python3 scripts/smoke_test.py`) still stay green.

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
