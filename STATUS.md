---
project_state: active
stage: public-candidate
health: amber
updated_at: 2026-08-25T00:20:00+08:00
next_action_owner: Steven
next_action: Replace the OWNER placeholder, create the public remote, and push v0.1.0.
blocked_by: ["`verified` also needs a decision on installation targets; PROMOTION_GATE itself is satisfied at 3/3.", "Kimi 3 terminal review was inconclusive because the local CLI produced file-watcher errors and no model output.", "The CI workflow has never executed on GitHub.", "`balanced` mode has never run against real Codex."]
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

## In progress

- None. The repository is ready to publish as a candidate.

## Blockers and risks

- Codex's documented sandbox provides write isolation, but not a project-specific read allowlist. The deterministic scanner is strict; worker read confinement is a known v0.1 limitation.
- Server-side Credits/Auto top-up state is user-asserted, not mechanically verified; the tool cannot guarantee zero server-side billing.
- Billing detection no longer reads the Worker's prose, so a quota failure reported only in the final message with a zero exit and no error event would not trip that specific check. See `SECURITY.md`.
- The `$id` fields in `schemas/*.json` and the CI badge in `README.md` carry an `OWNER` placeholder that must be replaced at publication.

## Verification

- `python3 -m py_compile scripts/bbr.py src/burn_before_reset/*.py`: PASS.
- `PYTHONPATH=src python3 -m unittest discover`: PASS, 49 tests, Python 3.14.7.
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

Replace `OWNER` in `schemas/*.json` and the README badge, create the public remote, and push `v0.1.0`.
