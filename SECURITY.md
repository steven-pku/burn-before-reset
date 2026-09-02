# Security Policy

Burn Before Reset is a local automation prototype, not a billing-control product.

## Supported boundary

- Local CLI workers only: Codex CLI, or Claude Code in `safe` mode.
- The Claude worker's read-only guarantee is tool absence, not denial: it is launched with `--tools Read,Grep,Glob` as a closed allowlist, `--restricted` (which removes the code-running tools and WebFetch and ignores user/project settings — the documented tool-removal flag; `--safe-mode` alone leaves built-in tools in place), `--safe-mode`, and an empty strict MCP map. Without `--safe-mode` a probe reached a connected cloud-storage write tool, so that flag is load-bearing. `--safe-mode` is not listed in the published CLI reference, so it is treated as an observed capability rather than a stable contract: preflight parses `claude --help` and refuses the run if it — or any other flag the worker command depends on — is not advertised. Dropping the flag and relying on `--tools` alone is not a fallback; that reopens the MCP write-tool exposure.
- The Claude worker's READ scope is its working directory plus the granted source roots — Read/Grep are unprompted in the cwd and `--add-dir` only ever widens it. The worker is therefore pinned to the empty staging directory as cwd; it is not confined to the allowlist the deterministic indexer uses, and a tool it attempts without a grant fails the task (`PermissionDenied`) rather than merely being logged.
- The deadline guard is per-task. Between tasks, during replenishment waits, and during re-planning, the outer hard stop is enforced by the supervisor's own checks (bounded sleeps, per-task dispatch checks), not by an independent watchdog process. A wait or re-index cannot launch work past the hard stop, but the supervisor process itself may outlive it briefly.
- For the Codex worker in `balanced` mode, "no external actions" rests on the Codex sandbox plus the Worker prompt; this repository adds no mechanical network/push gate of its own beyond the sandbox flag it passes. Treat that claim as sandbox-strength, not proof.
- The supervisor ignores SIGHUP (an overnight run survives its launching session ending) and turns SIGTERM/SIGINT into a clean stop that still finalises every receipt (`operator_stop`).
- Deterministic indexing reads only configured roots and rejects secret-like files.
- Source roots are never modified by the planner. Git status is read with `--no-optional-locks`, so indexing a repository does not rewrite its index.
- The Worker environment is filtered before launch. Variables that supply a credential or redirect the model endpoint are removed and recorded in `workers/<task>/DROPPED_ENV.txt`. `--ignore-user-config` only covers `$CODEX_HOME/config.toml`, so this closes the environment half of the same gate. Proxy variables are kept deliberately: they change how a request is routed, not which account is billed.
- Execution is disabled unless the user explicitly enables the pilot and confirms the billing gates.
- Execution is plan-only inside sixty minutes of the computed hard stop.
- The parent supervises both Worker and watchdog. Guard loss, descendant cleanup, or unconfirmed process-group shutdown fails closed and is recorded in the task result.
- Worker prompts exclude source snippets and bracket locator metadata as untrusted data. This narrows prompt-injection exposure but is not a complete content-security boundary.
- Frozen task IDs and deliverables are path-validated even when a queue hash is recomputed; runtime read/write roots must match the current configuration and run.
- Raw or failed Worker output is never promoted into the official artifact directory.
- The watchdog controls local processes only. It cannot cancel cloud tasks or reverse server-side usage.
- The tool holds no spend authority. It observes local time, exit codes, and provider refusal text — never the server-side quota pool, credit balance, or replenishment schedule — so it can only stop on the clock the user asserted (`reset_at`), on provider refusals, and on `execution.max_worker_calls_per_run`, an absolute per-run cap on worker launches (first attempts, quota retries, and re-planned rounds all count). It cannot promise that only expiring quota is burned; keeping auto top-up and paid credits disabled at the account is the user's half of that boundary.

## Two detection boundaries worth knowing

Billing and auth detection reads the Worker's stderr and its error events. It deliberately does **not** read the artifact the Worker produced. Scanning the deliverable for words like "billing" or "rate limit" discards correct work whenever the user's own notes discuss pricing — including this project's own documentation. The cost of that choice: a Worker that reports a quota failure only in prose, with a zero exit status and no error event, would not be caught here. The run's other gates still apply.

Quota-exhaustion matching is textual ("usage limit", "rate limit", both spellings). An org-level or proxy rate limit matches too and will be waited on as if the allowance could replenish; the wait is always bounded by the outer hard stop, but the label cannot distinguish those causes.

Source-mutation detection is scoped to the indexer's allowlist and reports the paths that moved. Watching the whole root instead reports every background write inside it, which makes a real boundary violation indistinguishable from a sync client. Read the named paths before treating the signal as a violation.

## Known limitation

Codex's standard `read-only` and `workspace-write` sandboxes constrain writes but do not provide a project-specific read allowlist. Until OS-level confinement is independently verified, do not run the execution pilot against sensitive home-directory data. Prefer `bbr plan` and review the frozen queue.

## Never supported

Do not use this project to bypass limits, buy Credits, enable auto top-up, switch to API-key billing, deploy, push, merge, message people, alter credentials, or modify production systems.

Report security issues privately to the maintainer before public disclosure. Do not include credentials, session transcripts, or private paths in a report.

## Source movement and attribution (since 0.3.0)

- A file that moved inside an allowlisted root is reported, always. It stops the run only when the worker that ran *could* have written that path: a `balanced` Codex worker anywhere, or any Codex worker for a source root that lives under the temp-directory family (`/tmp`, `/var/folders`, `$TMPDIR`). Read-only sandboxes commonly leave that family writable; this project has not probed the installed sandbox, so it treats those roots as writable to fail closed rather than to claim a fact. A Claude worker holds no write tool, so movement under its run is attributed to something else on the machine and named in the report.
- The Claude worker writes its own transcript under the user's session root, in a directory named after its cwd; that directory carries the run's name and is excluded from the snapshot, so a `claude_sessions` source does not report the run's own footprint as movement.
- Session roots and live project trees are written by other processes by design. Read the **Allowlisted files that moved** list with that in mind; it is the one place a real boundary violation would surface.

