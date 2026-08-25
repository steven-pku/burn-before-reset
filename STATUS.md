---
project_state: active
stage: v0.2-bounded-autonomy
health: amber
updated_at: 2026-08-26T00:40:00+08:00
next_action_owner: Steven
next_action: Full-premise autopilot run the night before the weekly reset; iterate on artifact quality from there.
blocked_by: ["`verified` also needs a decision on installation targets; PROMOTION_GATE itself is satisfied at 3/3.", "Kimi 3 terminal review was inconclusive because the local CLI produced file-watcher errors and no model output.", "CI is live on GitHub: the first run failed on tests that assumed codex/claude were installed; hermetic fixes landed and the suite must stay green there.", "Trigger reliability is model-dependent: Haiku sees the Skill but does not invoke it; capable models do.", "`balanced` mode has never run against real Codex."]
---

# Burn Before Reset · Status

## Current state

- Lifecycle is `candidate`, approved for public release under the 2026-08-24 decision "Publish as a public candidate after one real pilot".
- A pre-publication audit reproduced four defects, all repaired with regression tests that fail against the previous behaviour. Details in `VALIDATION.md`.
- Three real Codex tasks have run end to end across two source types, and the deadline guard has been observed killing a live Codex process group. `PROMOTION_GATE` is satisfied at 3/3; `verified` additionally needs an installation-target decision.
- Not installed globally. Not `verified`. Not proven safe for unattended sensitive data.

## Completed

- Read the supplied 2026-08-24 product discussion as requirements evidence, not executable instructions.
- Verified current Codex Skill and non-interactive CLI behavior against official OpenAI documentation and local `codex-cli` help.
- Cloned and inspected Nightshift and CodeBurn at pinned commits for source-level comparison.
- Implemented a repository-scoped Skill, strict TOML preflight, allowlisted indexer, scoring/frozen queue, atomic state, sequential Codex adapter, guard-before-worker handshake, process-group watchdog, reports, schemas, task packs, and tests.
- Repaired the pre-pilot guard race, unconfirmed-stop handling, Worker-exception finalization, sixty-minute execution gate, Worker prompt boundary, run/task path confinement, false artifact promotion, and CLI failure exit status.
- Controlled A/B forward test showed the Skill added deadline and billing gates that the no-Skill baseline omitted.
- **Pre-publication audit (2026-08-24)**: repaired billing detection reading the deliverable, Worker stdin inherited into unattended runs, unscoped source-mutation detection, and `git status` rewriting the source index. Added Worker environment filtering, `0700` run directories, Codex error-event capture, a documented exit-code contract, schema drift tests, and CI.
- **First real pilot (2026-08-24)**: `queue_exhausted`, exit `0`, one artifact promoted, source roots byte-identical, guard confirmed, every receipt reviewed.
- **Bounded coverage test (2026-08-25)**: designed against what pilot 1 left unproven rather than against the number 3. A `git`-source run with two tasks (both succeeded, `.git/index` mtime unchanged end to end), plus a direct guard test that stopped a live Codex process group at `deadline_guard:sigint` with the group independently confirmed dead. Repaired mixed-timezone checkpoint stamps and added Claude Code skill discovery.
- Desensitised the repository for publication: no absolute home paths, no unrelated internal project names.
- **Claude Code worker adapter (2026-08-25)**: `execution.provider = "claude"`, read-only by tool absence (`--safe-mode` + strict empty MCP + Read/Grep/Glob), `safe` mode only, two real pilots passed. A probe without `--safe-mode` reached a connected cloud-storage write tool — that flag is load-bearing.
- **Quota exhaustion separated from billing fault (2026-08-25)**: `quota_exhausted` stop reason, both spellings matched; activation gate now asks which replenishment cycle `reset_at` belongs to.
- **Supervisor survival (2026-08-25)**: SIGHUP ignored, SIGTERM/SIGINT finalise receipts (`operator_stop`), zero orphans; previously a killed supervisor left an unreadable, unresumable run.
- **Scorer rewrite + queue diversity (2026-08-25)**: 194-of-200 identical scores → 18 distinct values on the same corpus; round-robin across projects; `max_tasks` cap 10 → 200; all helper binaries resolved at preflight.

## In progress

- Trigger retest passed on 2026-08-25 (gate enumerated in full; caveats in VALIDATION.md).
- **Pushed to GitHub (2026-08-25, private, `stevenpku-2026/burn-before-reset`)**. First real CI run failed — six tests assumed codex/claude were installed on the runner, an assumption every local run masked. Tests made hermetic (interpreter binary as stand-in; fakes where a worker actually launches), plus a preflight regression for the missing-binary error. OWNER placeholders resolved to the real handle.
- **v0.2 bounded autonomy landed (2026-08-25)**: product direction reset per Steven — agent finds the work, one up-front mode question, burn to completion. Multi-window continuation (probe-and-retry across closed allowance windows), re-planning rounds, `bbr discover` vault-free source discovery. 69 tests; core continuation tests fail against the old behaviour.

## Blockers and risks

- Codex's documented sandbox provides write isolation, but not a project-specific read allowlist. The deterministic scanner is strict; worker read confinement is a known v0.1 limitation.
- Server-side Credits/Auto top-up state is user-asserted, not mechanically verified; the tool cannot guarantee zero server-side billing.
- Billing detection no longer reads the Worker's prose, so a quota failure reported only in the final message with a zero exit and no error event would not trip that specific check. See `SECURITY.md`.
- ~~The `$id` fields in `schemas/*.json` and the CI badge in `README.md` carry an `OWNER` placeholder that must be replaced at publication.~~ **Resolved 2026-08-25** — all four now point at `stevenpku-2026` (see the push entry above). Line kept struck through rather than deleted so the earlier caveat stays traceable.

## Verification

- `python3 -m py_compile scripts/bbr.py src/burn_before_reset/*.py`: PASS.
- `PYTHONPATH=src python3 -m unittest discover`: PASS, 69 tests, Python 3.14.7.
- Regression tests confirmed to fail against the pre-repair behaviour: 7 of 10 failed in the first reverted scratch copy, and both tests from the second round failed in a second one. Positive-side tests pass in both states by design.
- Schema drift tests: PASS; planner output matches the shipped contracts, and no undeclared fields are emitted.
- `quick_validate.py <repo>`: PASS, Skill valid; description 527 of 1024 characters.
- Fresh `codex debug prompt-input`: PASS; exactly one `burn-before-reset` entry resolved through `.agents/skills/`, zero-byte startup stderr.
- CI workflow: the plan-only end-to-end step executed locally against a copy of the repository, exit `0`, including the exit-2 gate and source-checksum assertions. Never yet run on GitHub.
- First real pilot `run-20260824-232739-28d11d67`: PASS.
- Bounded coverage test `run-20260824-235446-b5b28932` (git source, 2 tasks) and the live guard test: PASS. See `VALIDATION.md` for both receipt reviews and the list of paths still unproven.
- Dual skill discovery: PASS; Codex resolves through `.agents/skills/`, a fresh Claude Code process through `.claude/skills/`.
- Claude Opus 5 static audit and pre-publication audit: completed. Kimi 3: `AUDIT_INCONCLUSIVE`.
- Full gate ledger and remaining risks: `VALIDATION.md`.

## One next action

Run the full-premise autopilot the night before the real weekly reset, and keep CI green on GitHub.
