# Burn Before Reset · Decisions

Record only approved decisions or approved evidence-driven reversals. Append new entries; do not rewrite history to make the current path look inevitable.

## 2026-08-24 · Product identity and safety objective

- Status: `approved`
- Decision maker: Steven
- Decision: Use `burn-before-reset` as the repository and Skill name. Treat expiring quota as a constraint; the objective is useful, traceable, reviewable work that stops before reset.
- Rationale: Steven asked to build the project and Skill from the attached discussion.
- Alternatives: `token-burner`, `nightshift`, and unconstrained content generation.
- Revisit when: Naming conflict, user confusion, or evidence that the positioning overlaps an existing project too closely.

## 2026-08-24 · v0.1 execution boundary

- Status: `approved`
- Decision maker: Steven
- Decision: v0.1 supports local Codex CLI only, a user-supplied absolute reset time, a default 15-minute hard-stop buffer, deterministic allowlisted indexing, frozen queues, sequential workers, and local reports.
- Rationale: This is the smallest testable boundary that preserves the central product claim.
- Alternatives: Cloud tasks, multi-provider routing, quota scraping, automatic provider switching, and broad parallel execution.
- Revisit when: Three real safe runs succeed and stronger read-scope isolation has been demonstrated.

## 2026-08-24 · Candidate before release

- Status: `approved`
- Decision maker: Steven
- Decision: Build and validate inside the project first. Do not install into portable live Skills, create a GitHub remote, push, or claim release in this phase.
- Rationale: Skill lifecycle evidence must precede promotion; external actions require a separate gate.
- Alternatives: Immediate global installation or public launch.
- Revisit when: Structural tests, historical replay, forward test, fresh-process discovery, and three real task runs are available.

## 2026-08-24 · Repair blockers before pilots

- Status: `approved`
- Decision maker: Steven
- Decision: Repair the reproduced P0/P1 execution blockers, add deterministic regressions, and obtain Kimi 3 plus Claude Opus 5 terminal reviews before any real pilot.
- Rationale: Machine verification did not cover guard-loss races, unconfirmed descendant shutdown, or exception finalization; a pilot would otherwise test known safety defects.
- Alternatives: Run the original three-pilot sequence first, or abandon execution and keep the project plan-only.
- Revisit when: The repaired candidate passes the full suite and both requested review lanes have returned or are explicitly unavailable after bounded attempts.

## 2026-08-24 · Publish as a public candidate after one real pilot

- Status: `approved`
- Decision maker: Steven
- Decision: Publish this repository publicly while lifecycle remains `candidate`, after one real, non-sensitive pilot has run end to end through the product adapter and every receipt has been reviewed. `PROMOTION_GATE` still requires three real successful tasks before `verified` may be claimed.
- Rationale: Publication and promotion are separate claims. A candidate can be open source as long as the README says so plainly. Waiting for 3/3 before publishing leaves an untested happy path unexercised for longer than publishing it as a candidate does.
- Alternatives: Publish with `PROMOTION_GATE` at 0/3 and no real run behind it; or hold publication until 3/3.
- Reverses: the publication half of `2026-08-24 · Candidate before release`. The promotion half of that decision stands unchanged: no `verified` claim, no global install, until 3/3.
- Revisit when: A pilot on a user's own sources reveals a boundary failure, or three real tasks succeed and `verified` becomes claimable.

## 2026-08-24 · Bilingual Skill description, English body

- Status: `approved`
- Decision maker: Steven
- Decision: The Skill `description` carries English and Chinese triggers together, front-loaded so the first clause stands alone. `SKILL.md` prose is English, matching the README and the rest of the repository.
- Rationale: `description` is the line another agent matches on. A Chinese-only description made the Skill unmatchable for the English-speaking audience the English README attracts, while a Chinese-speaking user still needs Chinese trigger words. Front-loading matters because the Codex skill inventory truncates descriptions to fit its context budget when many skills are installed; on a crowded host only the opening clause survives.
- Alternatives: English only; Chinese only; leave the split as it was.
- Revisit when: Usage shows one audience dominating, or the inventory truncation behaviour changes.

## 2026-08-24 · Pre-publication fix scope

- Status: `approved`
- Decision maker: Steven
- Decision: Before publishing, repair the four defects a pre-publication audit reproduced (billing detection reading the deliverable; Worker stdin inherited into an unattended run; unscoped source-mutation detection reporting a bare boolean; `git status` rewriting the source index), plus the high-value hardening around run-directory location and permissions, Worker environment filtering, continuous integration, and the documented exit-code contract.
- Rationale: Two of the four were reproduced against this repository's own files, so the first external user would have hit them. Each repair ships with a regression test that fails against the previous behaviour.
- Alternatives: Publish first and repair on report; or repair only the desensitisation issues.
- Revisit when: A repair proves incomplete against a real pilot on user data.

## 2026-08-25 · Close promotion evidence by coverage, not by repetition

- Status: `approved`
- Decision maker: Steven
- Decision: Satisfy the remaining `PROMOTION_GATE` evidence with one bounded test designed against the paths pilot 1 left unexercised, rather than by repeating the pilot twice. The bounded test covered the `git` source adapter end to end, the multi-task loop, and the deadline guard stopping a live Codex process group.
- Rationale: The gate counts successful runs, and a count does not measure coverage. Three repetitions of one run shape carry one run shape's worth of evidence. The guard killing a real process was the product's central claim and had only ever fired against fake processes; repeating pilot 1 would not have touched it.
- Alternatives: Run two more pilots identical to the first; or publish at 1/3.
- Consequence: `PROMOTION_GATE` reached 3/3 through two source types rather than three repetitions, and `VALIDATION.md` now carries an explicit "still unproven" list — `balanced` mode, the guard firing inside a real run, signal escalation past SIGINT, and sources at real scale.
- Revisit when: The gate is next reviewed. It should be restated as a coverage checklist; the number 3 was never the thing that mattered.

## 2026-08-25 · Ship Claude Code skill discovery, keep the Codex-only worker

- Status: `approved`
- Decision maker: Steven
- Decision: Add `.claude/skills/burn-before-reset` alongside `.agents/skills/burn-before-reset` so Claude Code discovers the Skill from a checkout, and state plainly in the README that the v0.1 worker still shells out to `codex exec` and no other adapter exists.
- Rationale: Steven asked whether the Skill is portable across agents. Discovery and execution are separate questions and had opposite answers. A probe confirmed a Claude Code session in the repository answered `NO` before the symlink and `YES` after; the worker remains Codex-only regardless. Since plan-only is the default path, discovery alone is genuinely useful, but the README must not let "works with my agent" be read as "runs with my agent".
- Alternatives: Ship only the Codex path; or hold discovery until a Claude Code worker adapter exists.
- Revisit when: A second worker adapter lands, or another agent's discovery convention needs a third path.

## 2026-08-25 · Retest the trigger path before pushing

- Status: `approved`
- Decision maker: Steven
- Decision: The natural-language trigger test is re-run with a scripted, copy-paste setup (neutral directory + repository skill link + session launched inside it) before the repository is pushed. Documentation is swept now; OWNER replacement, tag, and push wait for the retest result.
- Rationale: The first attempt failed at setup — the session started where the Skill was not discoverable, so the activation gate was never exercised. Prose setup instructions were the failure point; the environment must travel with the trigger sentence. Pushing first would ship an activation gate that has never once fired from natural language.
- Alternatives: Skip the natural-trigger test and accept explicit invocation as sufficient; or install the Skill globally and test post-install discovery instead.
- Revisit when: The retest runs — in either result — or the distribution form changes to a global install.

## 2026-08-25 · Product direction: bounded autonomy, burn to completion

- Status: `approved`
- Decision maker: Steven
- Decision: Four corrections to the product's center of gravity, in Steven's words:
  1. The user does not know what should be done — **finding the most valuable work is the agent's job**, because the user may be asleep. Discovering valuable todos, known and unknown, is the product.
  2. Discovery must not assume a note vault. The core competency is reading **recent Claude/Codex session logs, repositories, documents — the traces on the machine**.
  3. Exactly **one question up front**: review the plan, or let the agent decide (看着办). Not a mid-flow approval gate the sleeping user can never answer.
  4. **Riding the inner replenishment cycle is a hard requirement.** The goal is to burn the quota to completion before the outer reset; quota left unburned is failure. v0.2 builds this first.
- Consequence: safety moves from mid-flow approval gates into **boundaries** — read-only sources, writes confined to the run directory, no external actions, billing fail-closed, the outer reset as an immovable hard stop. Autonomy governs what to work on; boundaries govern what it can touch. The v0.1 rule "an empty queue stops instead of inventing work" is superseded for time-remaining runs by **re-planning rounds** — new rounds still come only from real signals; a replan that finds nothing ends the run honestly.
- Alternatives: keep the v0.1 review-first flow as default; or full autonomy without the up-front mode question.
- Revisit when: a real overnight autopilot run produces artifacts Steven judges not worth their quota.
