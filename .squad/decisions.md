# Squad Decisions

## Active Decisions (Milestones 6–7)

**Note:** Foundational decisions for Milestones 1–5 are archived in `decisions-archive.md` for historical reference.



### D19: Milestone 6 Implementation Decision

**Date:** 2026-04-14  
**Decision:** Implement Milestone 6 as a two-phase sampling workflow around constrained Linux diagnostics queries.

**Scope:**
- Public tool: `troubleshoot_linux_diagnostics`
- Teaching shape preserved from C#: sample for query → validate on server → execute deterministically → sample for summary
- Linux adaptation: sampled query is a single safe `PATH` or `PATH | grep FIELD` line over allowlisted `/proc` or `/sys` source
- Python SDK adaptation: client advertises sampling via `sampling_callback` supplied to `ClientSession` (Python equivalent of C# sampling handler pattern)

**Rationale:**
- Keeps parity-critical protocol/teaching flow intact without arbitrary shell execution
- Server remains authority over every sampled request
- Fits Python MCP SDK surface cleanly

**Owners:** Ash (Implementation), Dallas (Linux Specs), Newt (QA)

**Status:** Implemented

---

### D20: Milestone 6 Module Rename Decision

**Date:** 2026-04-14  
**Decision:** Rename M6 diagnostics helper module from `m6_diagnostics.py` to `linux_diagnostics.py`; keep milestone labels out of Python module filenames.

**Rationale:**
- Milestone labels belong in branch/docs context, not in long-lived Python import paths
- Domain-based filenames make later maintenance and cross-milestone reuse less awkward

**Implementation:**
- Module path: `src/mcp_linux_diag_server/tools/linux_diagnostics.py`
- Repointed package exports and test imports
- Updated squad sampling skill documentation

**Owners:** Ash (Implementation)

**Status:** Complete

---

### D21: Milestone 6 Acceptance Decision

**Date:** 2026-04-14  
**Decision by:** Newt (QA Lead)  
**Status:** Accepted

**Decision:** Accept Milestone 6 as implemented.

**Evidence:**
- Full test coverage with realistic diagnostic payloads
- Bridge pattern unifies STDIO and HTTP client sampling state under shared session identity
- Progressive render in lecture mode with sample accumulation UI
- All M1–M5 surfaces remain intact

**Parity Judgment:** M6 meets documented contract parity across:
- Sampling state persistence via HTTP session headers
- Deterministic execution of validated queries
- Progressive diagnostic result display
- Lecture client integration

**Status:** Accepted & Ready for Publication

---

### D22: Milestone 6 Publication Decision

**Date:** 2026-04-14  
**Decision:** APPROVED — Publish M6 to `origin/milestone-6`

**Summary:**
Milestone 6 implementation completes diagnostics sampling and bridge pattern work:
- `troubleshoot_linux_diagnostics` tool: incremental sampling of diagnostic data across user sessions
- TemporalDiagnosticsCollector: stateful sampling backend preserving sample history via HTTP session headers
- Bridge pattern: unifies STDIO and HTTP client sampling under shared session identity
- Client-side sampling display: progressive render with sample accumulation UI
- Test coverage: comprehensive tests with realistic payloads across both protocols

**Branch State:**
- HEAD: M6 teaching baseline
- Pushed: `origin/milestone-6`
- Master: Remains at M4 baseline (no change)

**Key Learnings:**
- Sampling across protocols requires session identity as glue layer; HTTP session headers bridge STDIO and web clients
- Progressive data UI demonstrates MCP tools that evolve state over time—pedagogically rich
- Bridge pattern reduces duplication and makes stateful distributed tools testable

**Owners:** Ripley (Lead), Ash (Implementation), Dallas (Specs), Newt (QA), Bishop (Architecture)

**Status:** Published

---

### D23: Milestone 7 Implementation Decision

**Date:** 2026-04-14  
**Decision:** Implement Milestone 7 as a separate proc/sys snapshot subsystem instead of modifying M6 sampling validator.

**Scope:**
- Roots and proc/sys snapshots with allowed-root enforcement
- Reuses proven snapshot/resource UX from M3 log snapshots, adapted for /proc and /sys
- File snapshots page line-by-line; directory snapshots page deterministic child metadata
- Centralizes allowed-root enforcement, traversal rejection, and symlink-escape rejection before any proc/sys read

**Why:**
- Keeps M5/M6 behavior unchanged while adding C#-style roots/sandbox pattern
- Single point of control for safety rules
- Domain-specific adaptation maintains pedagogical clarity

**Key Files:**
- `src/mcp_linux_diag_server/tools/proc_snapshots.py` — proc/sys snapshot tools
- `src/mcp_linux_diag_server/server.py` — server wiring
- `src/mcp_linux_diag_server/client.py` — client integration
- `scripts/smoke_test.py` — end-to-end validation
- `tests/test_proc_snapshots.py` — unit tests
- `tests/test_m7_http.py` — integration tests

**Owners:** Ash (Implementation), Dallas (Linux Safety), Newt (Validation), Ripley (Lead)

**Status:** Implemented

---

### D24: Milestone 7 Linux Safety Rules Decision

**Date:** 2026-04-14  
**Decision:** Author Linux M7 safety rules and enforce forbidden-path rejection before snapshot creation.

**Scope:**
- Forbidden proc/sys classes identified and validated
- Rejected paths raise `ValueError` before snapshot initialization
- Allowed-root allowlist expansion respects sandbox constraints

**Implementation:**
- First candidate rejected by Newt for forbidden-path leakage
- Revision tightened forbidden proc/sys class identification
- Safety audit ensures no bypass of sandbox constraints via allowlist expansion

**Enforcement Points:**
1. Before snapshot creation
2. Before elicitation
3. Before allowlist expansion in `ProcRootsService.add_allowed_root()`

**Owners:** Dallas (Linux Safety Expert), Ash (Implementation)

**Status:** Revised & Approved

---

### D25: Milestone 7 Validation & Approval Decision

**Date:** 2026-04-14  
**Decision by:** Newt (QA Lead)  
**Status:** Approved

**Decision:** Approve Milestone 7 revised worktree. Forbidden proc/sys classes now reject before snapshot creation, before elicitation, and before allowlist expansion. `request_proc_access` remains limited to eligible-but-not-yet-allowed roots.

**Validation Coverage:**
- `python3 -m unittest tests.test_proc_snapshots tests.test_m7_http -q` ✓
- `python3 -m unittest discover -s tests -q` ✓
- `python3 scripts/smoke_test.py` ✓

**Direct Evidence:**
- Forbidden `/proc/kcore` raises `ValueError` in validator
- `ProcRootsService.instance().add_allowed_root("/proc/kcore")` raises `ValueError`
- Allowed-root allowlist expansion respects sandbox constraints

**Parity Judgment:** M7 meets C# roots/sandbox pattern with Linux-specific safety enforcement.

**Status:** Approved

---

### D26: Milestone 7 Publication & Branch Alignment Decision

**Date:** 2026-04-14  
**Decision:** APPROVED — Publish final M7 on both `master` and `milestone-7`

**Summary:**
Milestone 7 is the closing teaching slice. The repo should stop preserving `master` as an earlier snapshot and instead make `master` and `milestone-7` the same final artifact.

**Implementation:**
- Final commit: a9a675a9f09882766289061582d947e0add1bb28
- `master` receives the final reviewed M7 commit
- `milestone-7` must end on that same commit
- No history rewriting; no force push

**Rationale:**
This is the end of the lecture progression. Separate tips for `master` and `milestone-7` would add ambiguity instead of teaching value. One shared final commit represents:
- Milestone 7 as the final product
- `master` as the stable endpoint
- Clear repository narrative: pedagogical progression complete

**Delivery Chain:**
1. Ash → Ash implemented proc/sys snapshot subsystem
2. Dallas → Dallas authored Linux safety rules; revised forbidden-path logic after review rejection
3. Newt → Newt created validation coverage; rejected first candidate, approved revised artifact
4. Ripley → Ripley committed final work and aligned branches

**Branch State:**
- `master` ← a9a675a9f09882766289061582d947e0add1bb28
- `milestone-7` ← a9a675a9f09882766289061582d947e0add1bb28

**Owners:** Ripley (Lead), Ash (Implementation), Dallas (Safety), Newt (QA)

**Status:** Published & Complete
