---
last_updated: 2026-04-14T14:00:00Z
---

# Team Wisdom

Reusable patterns and heuristics learned through work. NOT transcripts — each entry is a distilled, actionable insight.

## Patterns

**Pattern:** Snapshot + Pagination for large datasets. **Context:** When tools produce datasets larger than safe transport size. Tool creates immutable snapshot; resource pages it; client reads incrementally. Reduces latency and memory pressure.

**Pattern:** MCP Prompts are pedagogical. **Context:** Prompts teach workflow and pattern recognition. They return plain-text guides (not JSON), reference tools by name, and show expected parameters/output. Useful for AI elicitation and multi-tool orchestration teaching.

**Pattern:** Tool/Resource/Prompt separation is core MCP pedagogy. **Context:** Don't conflate them. Tools = deterministic operations (create snapshots, list processes). Resources = read-only, paginated views. Prompts = AI-guided workflows. Each has distinct MCP registration.

**Pattern:** Linux /proc files are stable and portable. **Context:** Direct kernel-facing reads work across Ubuntu, Debian, WSL identically. Avoid distro-specific branch logic; `systemd` and `/proc` are quasi-universal on modern Linux. Educational value outweighs library abstractions for teaching scenarios.

**Pattern:** Branch model mirrors pedagogical arc. **Context:** Each milestone branch is a teaching snapshot. Keep public (stable) branches clean; stage feature work on per-milestone branches. Follows C# MCPDemo precedent: 7-milestone progression, public branches at milestone boundaries.
