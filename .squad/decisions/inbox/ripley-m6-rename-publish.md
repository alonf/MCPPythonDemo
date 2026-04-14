# Ripley: M6 Rename Correction Published

**Date:** 2026-04-14  
**Status:** Published to origin/milestone-6

## Decision

Accepted and published the M6 rename correction on `milestone-6` branch:
- Module `m6_diagnostics.py` renamed to `linux_diagnostics.py`
- All import paths updated in package __init__.py, test suite, and squad skill documentation
- No breaking changes to public tool/resource/prompt interfaces

## Publication Details

**Commit:** e75c18b ("Correct Milestone 6 module naming: rename m6_diagnostics to linux_diagnostics")
- Staged: all 6 supporting files + the rename
- Validated: all 60 unit tests + smoke test pass
- Pushed to origin/milestone-6

**Reviewer approval:** Newt (M6 acceptance on 2026-04-14 after validation)

**Branch strategy:** master remains pinned at M4 baseline (992058e). M6 naming correction isolated to `milestone-6` branch as intended.

## Why This Works

- **Naming pattern:** Long-lived Python modules use domain names, not milestone labels
- **Zero footprint:** Correction happens after M6 implementation was completed and published; prior commits unchanged
- **Test validation:** Full M6 contract parity verified post-rename
- **Clean split:** Decision records (ash-m6-rename-fix.md, newt-m6-rename-review.md) ready for inbox merge during decision consolidation pass

## Learning

This correction exemplifies the importance of code naming hygiene in teaching projects. Milestone labels belong in branch names and docs, not in permanent Python paths. The team caught this during acceptance review—right time to fix before the module becomes part of the stable teaching arc.
