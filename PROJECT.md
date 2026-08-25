# Burn Before Reset · Project Charter

## Mission

Turn expiring subscription quota into useful, reviewable work the agent finds on its own, ride the inner allowance windows, and hard-stop only at the outer reset. Burning the quota to completion is the goal; quota left unburned is the failure mode.

## Primary deliverable

- An open-source-ready repository-scoped Agent Skill named `burn-before-reset`.
- A deterministic Python runner that validates an absolute reset deadline, indexes only allowlisted sources, freezes a bounded task queue, checkpoints state, and hard-stops a local worker process group before reset.

## Success criteria

- Missing or unsafe deadline, billing assertion, source root, or output root fails closed.
- Dry-run planning produces traceable candidates, a frozen queue, state, checkpoints, and a morning report without changing source files.
- The deadline guard terminates a complete spawned process group in an integration test.
- Path traversal, secret-like files, and out-of-allowlist access are rejected by deterministic components.
- The Skill passes the bundled structural validator, unit/integration tests, historical replay, and an isolated forward test.
- Machine verification may pass while lifecycle remains `candidate`; promotion requires three real successful tasks and a separate approval.

## In scope

- Two local worker adapters: Codex CLI (sandboxed, `safe` or `balanced`) and Claude Code (`safe` only; read-only by tool absence).
- macOS and Linux; Python standard library only.
- User-supplied reset time with timezone and a minimum ten-minute buffer.
- Read-only indexing of explicitly allowlisted Codex/Claude session roots, Obsidian/Markdown roots, and Git repositories.
- `safe` planning and an explicitly enabled local execution pilot; sequential workers only.
- One up-front delegation question (review vs autopilot); no mid-flow approval gates in autopilot.
- Multi-window continuation (wait-and-retry across inner allowance resets) and re-planning rounds, bounded by the outer `reset_at`.
- Read-only source discovery (`bbr discover`) over session logs, repositories, and document trees; a note vault is never assumed.
- Frozen queue, atomic run state, checkpoints, JSONL events, stop marker, and morning report.
- Core task packs: workspace archaeology, thread recovery, project health, PRD sync, and Skill grooming.

## Out of scope

- Cloud tasks, API-key billing, paid Credits, automatic top-up, provider fallback, quota scraping, or undocumented account APIs.
- Deleting, moving, pushing, merging, deploying, publishing, messaging, purchasing, credential changes, or production/data-system mutation.
- Automatic Obsidian reorganization or writes to source roots.
- Guaranteed prevention of all server-side billing; the runner can only enforce local process and configuration gates.
- Global Skill installation, a `verified` lifecycle claim, or portable-Skill promotion in this phase. Public release is in scope as a `candidate` only, under the 2026-08-24 decision "Publish as a public candidate after one real pilot".

## Safety and approval boundaries

- Any destructive, paid, credential, external-facing, production, installation, symlink, remote-repository, or release action requires Steven's separate approval.
- The deterministic indexer never reads known secret files. The Codex worker uses Codex's own sandbox, whose read scope is broader than this runner's allowlist; therefore unattended execution remains an isolated pilot until stronger OS-level confinement is proven.
- Billing safety is assertion-based. Unknown credit balance, unknown auto-top-up state, an API key in the worker environment, or a billing/rate-limit error stops the run.

## Roles

- Steven: decisions and external approvals.
- Codex: approved internal execution, verification, and project-state maintenance.
