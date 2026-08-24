# Risk Policy

## Green: automatic planning

- Read metadata and bounded text snippets from allowlisted roots.
- Produce indexes, candidate lists, reports, drafts, validation plans, and patches inside the run root.
- Run deterministic tests against staged artifacts.

## Yellow: isolated pilot only

- Launch local Codex in `workspace-write` against a staging directory.
- Propose code or document changes as patches.
- Run repository tests that have been explicitly listed in a TaskSpec.

Yellow work requires explicit current-turn approval and `execution.enabled = true`. It never integrates into source roots.

## Red: refuse

- Delete, move, overwrite source files, push, merge, deploy, publish, send messages, purchase, alter billing, credentials, permissions, or production data.
- Use API keys, Credits, Auto top-up, provider fallback, Cloud Task, or undocumented account APIs.
- Read `.env`, `auth.json`, keychains, SSH/GPG keys, browser stores, cookies, tokens, financial, health, client, or other excluded sensitive paths.
- Continue after a billing, quota, authentication, sandbox, permission, or hard-stop uncertainty.

## Time gates

- `hard_stop_at = reset_at - safety_buffer`.
- Safety buffer must be at least ten minutes; default fifteen.
- Less than sixty minutes before hard stop: plan-only mode.
- Less than twenty minutes before hard stop: refuse to begin.
- At hard stop: create `STOP_NOW`, stop dispatch, send SIGINT to the process group, then SIGTERM, then SIGKILL after bounded grace periods.
- One window per run. `reset_at` belongs to the replenishment cycle the run sits in, not
  to an outer weekly reset. v0.1 neither waits out a replenishment nor resumes a run that
  has started tasks; exhaustion mid-window ends the run as `quota_exhausted`.

## Honest claims

The watchdog proves only that the local process group was signalled and observed stopped. It cannot prove a server stopped processing, prevent already-incurred usage, inspect the account credit balance, or disable Auto top-up. Those remain user-side assertions.
