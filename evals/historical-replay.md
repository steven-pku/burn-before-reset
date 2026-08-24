# Historical replay cases

## Gate failures

1. Missing `reset_at` must fail config validation.
2. Reset timestamp without timezone must fail.
3. Safety buffer below ten minutes must fail.
4. Unknown/false billing assertion must fail.
5. API key present during execution must fail.

## Boundary failures

1. Output root overlapping a source root must fail.
2. Symlink escape, `.env`, `auth.json`, key material, and excluded fragments must not enter the index.
3. Invalid Codex JSONL must not be treated as a session.
4. A frozen queue changed after creation must fail hash validation.

## Runtime failures

1. Deadline guard must stop a spawned worker and child in the same process group.
2. Billing/auth text from a Worker must stop the run without retry or fallback.
3. Empty candidate set must remain empty and end normally.
4. Completed status requires a non-empty artifact and finalized report.

These cases map to automated tests under `tests/` and are replayed on every full test run.
