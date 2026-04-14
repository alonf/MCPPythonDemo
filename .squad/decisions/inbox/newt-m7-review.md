# Newt M7 QA Coverage Decision

## Context
Milestone 7 parity needs reviewer-grade proof for the new roots/snapshot model without weakening milestone 3-6 guarantees.

## Decision
Add a dedicated HTTP integration suite (`tests/test_m7_http.py`) that checks:
- advertisement of `create_proc_snapshot` and `request_proc_access`
- advertisement of `proc://snapshot/{...}` resource templates, including pagination parameters
- successful allowlisted snapshot creation plus resource reads
- blocked out-of-roots reads
- elicitation-backed access approval followed by successful snapshot creation
- rejection of traversal, symlink-escape, and similar unsafe path attempts
- additive regression coverage that M3-M6 tools, prompts, and syslog resources still remain discoverable

## Why
This keeps milestone parity claims executable in one place and gives implementation reviewers a single failure report that distinguishes “surface missing” from “surface present but unsafe.”
