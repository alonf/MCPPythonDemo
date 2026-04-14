---
name: branch-alignment-publish
description: Publish a final milestone so master and the milestone branch share one commit without rewriting history.
source: "earned (2026-04-14 M7 publish)"
---

# Branch Alignment Publish

## Use when

- A repo keeps milestone branches during development
- The final milestone should become the exact `master` state
- You need both branch names to end on one identical commit

## Method

1. Verify the reviewed worktree is approved and tests are green before publication.
2. Commit the final changes on the checked-out branch with the required trailers.
3. Align the sibling branch with an ff-only move or merge so both refs point at the same descendant commit.
4. Push both branches normally; do not rewrite history and do not force-push.
5. Confirm the worktree is clean and both branches resolve to the same SHA.

## Why it works

This keeps the teaching history intact while eliminating needless divergence at the end of the arc. Students can inspect either branch name and see the same final code.
