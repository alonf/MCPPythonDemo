---
name: parity-audit
description: Separate migration-critical behavior from wrapper ergonomics when comparing implementations.
source: "earned (2026-04-14 client complexity audit)"
---

# Parity Audit

## Use when

- A migrated implementation looks "more complex" than the reference
- You need to tell whether that complexity is required for behavioral parity or just convenience/portability work

## Method

1. Inspect the reference branch's runnable entrypoints, not just summaries.
2. Identify the **behavioral contract**:
   - transport
   - server/client split
   - LLM involvement
   - tool exposure/orchestration
   - credential model
3. Mark everything in the target implementation as either:
   - **parity-critical**
   - **ergonomic/portability add-on**
4. Explain any extra complexity in human terms: "hidden by the original SDK" vs "new convenience layer".

## Example from this repo

- **Parity-critical:** Python tool-schema translation + tool-call loop, because C# M1 uses `AsAIAgent(... tools: [.. tools])`.
- **Extra ergonomics:** `.env.local`, CLI overrides, env alias lookup, API-key fallback, interactive chat polish.
