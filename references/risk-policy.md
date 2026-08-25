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
- `reset_at` is the OUTER reset. The run rides inner replenishment windows: mid-run
  exhaustion pauses the run (probe-and-retry, bounded by the hard stop), it does not
  end it. Only a wait cut short — by the operator or the hard stop — or a run with
  `wait_for_replenish = false` ends early over quota.

## Honest claims

The watchdog proves only that the local process group was signalled and observed stopped. It cannot prove a server stopped processing, prevent already-incurred usage, inspect the account credit balance, or disable Auto top-up. Those remain user-side assertions.
