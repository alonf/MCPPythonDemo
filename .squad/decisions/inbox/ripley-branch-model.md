# Ripley: Branch model alignment for public milestones

## Decision

Use the existing public Milestone 1 baseline commit for `milestone-1`, and keep both `milestone-2` and `master` on the squad-enabled follow-up state that adds only squad-operational support files.

## Why

- This matches the C# demo naming model for the active branches at this point in the lecture arc.
- It preserves a clean public M1 teaching snapshot on `milestone-1`.
- It gives the squad a ready-to-work `milestone-2` branch without pulling in Milestone 2 feature implementation.
