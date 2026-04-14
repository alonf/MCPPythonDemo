---
name: "branch-archaeology"
description: "How to reconstruct teaching progression when milestone branches are not clean linear ancestors"
domain: "repo-analysis"
confidence: "high"
source: "earned"
tools:
  - name: "github-mcp-server-list_branches"
    description: "Enumerates milestone branches to inspect"
    when: "When a repo uses milestone or lecture branches"
  - name: "github-mcp-server-get_file_contents"
    description: "Reads roadmap/docs and exact source files from specific refs"
    when: "When branch intent must be grounded in code and docs"
  - name: "bash"
    description: "Runs git diff, git show, and branch-containment checks locally"
    when: "When behavioral comparison is easier via git archaeology"
---

## Context
Use this when a repository has milestone-named branches but branch names or tip commits are not trustworthy indicators of the actual teaching progression.

## Patterns
- Start with the roadmap or lecture artifact (`docs/MCPDemoRoadmap.md` here) to learn the intended milestones.
- Verify each milestone by diffing the branch against the previous milestone and by reading the exact server/client files touched.
- Check branch containment (`git branch --contains <sha>`) before assuming milestones are linear ancestors.
- Prefer behavior over labels: summarize what tools, resources, prompts, transports, and safety mechanisms actually changed.
- Note documentation drift explicitly when README text lags behind the code.

## Examples
- In `alonf/MCPDemo`, `milestone-1` through `milestone-7` are best interpreted via roadmap plus file diffs; only `milestone-7` flows directly into `master`.
- `master` differs from `milestone-7` mostly by docs polish (`docs/Milestone-*.gif`) and minor solution metadata, so the runtime architecture is effectively the milestone-7 architecture.

## Anti-Patterns
- Assuming milestone branches form a strict ancestry chain without checking.
- Using only branch tip commit messages to infer milestone content.
- Treating README prose as authoritative when branch code and roadmap disagree.
