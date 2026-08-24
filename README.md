# Burn Before Reset 🔥

[![tests](https://github.com/OWNER/burn-before-reset/actions/workflows/tests.yml/badge.svg)](https://github.com/OWNER/burn-before-reset/actions/workflows/tests.yml)

**Don’t burn tokens. Burn down your backlog.**

Burn Before Reset turns expiring local Codex subscription quota into useful, reviewable work, then hard-stops the local process group before a user-supplied reset deadline.

It indexes only sources you explicitly allow, builds a traceable candidate list, freezes a bounded queue, checkpoints every task, and produces one Morning Report. Token use is a constraint, not a KPI.

## Current status

**Public candidate. Not proven safe for unattended use.**

Lifecycle is `candidate`. Three real Codex tasks have run end to end through the product adapter across two source types, and the deadline guard has been observed killing a live Codex process group, so `PROMOTION_GATE` is satisfied at 3 of 3. Nothing here is installed globally, and `verified` is still not claimed: that also requires a decision about installation targets.

Read that as: the safety machinery is tested, the happy path has been exercised, and the hard stop has actually fired once against a real process — all on small, non-sensitive sources in `safe` mode, under supervision. `balanced` mode has never run for real. The default path is plan-only, and it should stay that way until you have watched `--execute` behave on your own sources. See [VALIDATION.md](VALIDATION.md) for the full gate ledger and the risks that remain open.

## Safety model

- User supplies an absolute reset timestamp with timezone.
- Default hard stop is fifteen minutes before reset; values below ten minutes are rejected.
- Execution becomes mechanically plan-only inside sixty minutes of the hard stop.
- Unknown Credits balance, unknown Auto top-up state, API-key environment variables, or billing/rate-limit errors fail closed.
- Environment variables that could supply a key or redirect the endpoint are withheld from the Worker and listed in `DROPPED_ENV.txt`. Proxy variables are kept: they change the network route, not the billed account.
- Billing and auth failures are read from the Worker's diagnostics, never from the artifact it wrote. An artifact that merely discusses pricing or rate limits is still delivered.
- Planner never modifies source roots, and reads Git status without touching the repository index.
- No delete, push, merge, deploy, publish, message, purchase, credential change, provider fallback, or Cloud Task.
- A supervised watchdog controls the local worker process group; guard loss or unconfirmed shutdown fails the task.
- The queue freezes before execution; empty queues stop instead of inventing work.
- Worker prompts omit source snippets and treat locator metadata as untrusted data, not instructions.
- Rehashed queues still reject unsafe task IDs and deliverable traversal; runtime task roots are rebound to configured sources and the current run directory.
- Only a completed Worker `agent_message` that passes every safety check is promoted into `artifacts/`; failed output stays diagnostic.

Important: Codex's standard sandbox constrains writes but does not provide a repository-specific read allowlist. Until stronger OS-level confinement is validated, use `plan` for sensitive data and treat `--execute` as an isolated pilot.

## Quick start

Requires Python 3.11+, Git, and a locally authenticated Codex CLI.

```bash
cp examples/config.example.toml config.local.toml
python3 scripts/bbr.py validate-config --config config.local.toml
python3 scripts/bbr.py plan --config config.local.toml
```

Review the generated `RUN_PLAN.md`, `CANDIDATES.jsonl`, and frozen `QUEUE.json` before any Worker run.

Execution is deliberately double-gated:

```bash
python3 scripts/bbr.py run --config config.local.toml --execute
```

The command still refuses unless `execution.enabled = true` and every safety assertion passes.

## Exit codes

`run` reports whether the queue was worked to the end, not merely whether the process survived. Wrap it accordingly.

| Code | Meaning |
|---|---|
| `0` | The queue was exhausted with no failed task. This is the only success. |
| `1` | The run stopped early. Read `STOP_REASON`: `deadline_guard` and `drain_window` are correct, designed stops with work left over; `billing_or_auth_error`, `source_mutation_detected`, `guard_failure`, and `stop_unconfirmed` are not. |
| `2` | The command refused before doing anything: a gate failed, the config was rejected, or `--execute` was missing. |

A `1` from a deadline stop means "ran out of time as designed", so treat it as an incomplete run rather than a fault, and read `MORNING_REPORT.md` before deciding.

## What v0.1 does

- Strict preflight and deadline computation.
- Deterministic, allowlisted Markdown/session/repository indexing.
- Candidate extraction and value/risk scoring.
- Immutable frozen queue and atomic run state.
- Sequential local Codex Worker adapter with JSONL capture.
- Supervised deadline watchdog, confirmed-stop receipts, checkpoints, stop reason, and Morning Report even on ordinary Worker exceptions.
- Dry-run and fake-worker integration tests.

## What it does not do

- Read quota/reset data from undocumented endpoints.
- Guarantee server-side billing behavior.
- Use API keys, paid Credits, provider fallback, or cloud jobs.
- Mutate original Vaults or repositories.
- Integrate patches, open PRs, create remotes, or push.

## Repository layout

```text
SKILL.md                 Agent workflow and activation gate
scripts/bbr.py           Local CLI entry point
src/burn_before_reset/   Deterministic runner
references/              Risk, task contract, adapters, research
task-packs/              Bounded candidate-generation recipes
schemas/                 Task and run-state contracts
tests/                   Unit and integration tests
examples/                Safe configuration example
.agents/skills/          Skill discovery for Codex CLI
.claude/skills/          Skill discovery for Claude Code
```

Both skill directories hold a symlink back to the repository root, so a session started
inside this checkout finds `SKILL.md` with no global install. The two exist because the
agents look in different places: Codex reads `.agents/skills/`, Claude Code reads
`.claude/skills/` in the working directory and every parent up to the repository root.
Git checkouts on Windows without symlink support materialise them as text files
containing `../..`; the CLI and the tests are unaffected.

## Which agents can run this

The Skill file itself is portable — plain `SKILL.md` with `name` and `description`
frontmatter — and both Codex CLI and Claude Code discover it from this checkout.

**The worker is not portable.** v0.1 shells out to `codex exec`, and that is the only
model adapter. So under Claude Code you get the full activation gate, the deadline
arithmetic, planning, the frozen queue, and the receipts, but `--execute` still needs
Codex CLI installed and logged in. A Claude Code adapter is v0.3 work, not a promise
made here. Since plan-only is the default path anyway, this is less limiting than it
sounds — but read it before assuming "works with my agent" means "runs with my agent".

See [SECURITY.md](SECURITY.md) before enabling execution and [research-2026-08-24.md](references/research-2026-08-24.md) for the evidence and competitor comparison.

## License

MIT.
