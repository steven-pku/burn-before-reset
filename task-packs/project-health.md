# Task Pack · Project Health

Use for one allowlisted Git repository.

## Candidate signals

- Dirty worktree, explicit TODO/FIXME, documented but unverified behavior, test gaps, or README/implementation drift.

## Output

Produce an audit and, only in an approved balanced pilot, a patch candidate inside staging. Never branch, commit, push, merge, deploy, or modify the source repository.

## Validation

- Findings cite repository-relative files.
- Tests are reported as run, failed, or skipped with exact reason.
- Source snapshot remains unchanged.
