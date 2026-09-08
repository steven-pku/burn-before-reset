---
project_state: active
stage: v0-3-public
health: amber
updated_at: 2026-09-02T22:35:00+08:00
next_action_owner: Claude
next_action: Steven posts the two final X articles at a time of his choosing; a CE-line session builds the Xiaohongshu single card (NF06) from `promo/ce-shorts-nf-draft.md`; keep CI green on `main`. Steven still owes the 27 artifact grades and the Settings upload of the social preview.
blocked_by: ["Artifact value is ungraded, so selection is still ranked by how *live* a finding looks rather than by what it is worth.", "`verified` also needs a decision on installation targets; PROMOTION_GATE itself is satisfied at 3/3.", "Trigger reliability is model-dependent: Haiku sees the Skill but does not invoke it; capable models do."]
---

# Burn Before Reset · Status

## Current state

- Lifecycle is `candidate`, approved for public release under the 2026-08-24 decision "Publish as a public candidate after one real pilot".
- A pre-publication audit reproduced four defects, all repaired with regression tests that fail against the previous behaviour. Details in `VALIDATION.md`.
- Real Codex tasks have run end to end across two source types, the deadline guard has been observed killing a live Codex process group, and one full overnight run (2026-09-01) burned a real allowance to exhaustion. `PROMOTION_GATE` is satisfied at 3/3; `verified` additionally needs an installation-target decision.
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
- **Public release (2026-09-02)**: repository made public at Steven's instruction after a desensitisation sweep (six sensitive paths and internal project names removed from the ledgers and a test fixture). v0.3.0 tagged and released, v0.2.0 back-filled; community profile 57% → 100% (code of conduct, contributing guide, issue and PR templates); topics 8 → 12; social preview regenerated through the Codex image channel. CI green on every push. Remaining manual step: the Settings upload of the preview image, which GitHub exposes no API for.
- **Fourth external audit adopted (2026-09-02)**: Grok 4.6 and Kimi seats on `8bcc5d0`; nine findings adopted with a regression module (A20–A28), three declined with reasons; a Codex Sol seat then re-reviewed the adoption itself (see VALIDATION.md). The headline: `--safe-mode` never removed built-in tools — `--restricted` does, and is now load-bearing. Details in `VALIDATION.md`.
- **v0.3.0 released (2026-09-02)**: community profile at 100% (code of conduct, contributing guide, issue and PR templates), launch assets re-rendered in the v0.3 identity, README showcase of `REPORT.html`, CHANGELOG 0.3.0, GitHub Releases for v0.3.0 (latest) and v0.2.0. CI green on `8b19e28` (lint + six-way matrix). The social-preview upload in Settings is the one manual step left.
- **HTML report shipped (2026-09-02)**: `REPORT.html` beside the Markdown twin — fixed-format opening, proverb verdict on what was delivered, validated palette and icon system, handoff-first actions. Adaptation matrix of 17 synthetic scenarios across languages × outcomes × shapes caught two release-blocking defects (Japanese users served a Chinese page; raw `<script>` in the data payload). `run.report_language` added. Details in `VALIDATION.md` (A18–A19).
- **First full overnight run (2026-09-01)**: unattended, autopilot, real expiring weekly allowance. 25 tasks completed, 27 artifacts, $71.38, and the allowance driven to genuine exhaustion — the thing the tool exists to do, done for the first time. Four defects found and repaired with regression tests, all in `VALIDATION.md`: quota exhaustion misread as a malformed worker result (the refusal was stated only in the `result` text, which diagnostics excluded as "the deliverable"); source-movement detection blaming a worker that held no write tool; a dead run making the next run redo its finished work (7 of 27 artifacts were repeats, ~$25 of the night); and reports written in English over Chinese-language sources because nothing in the run carried a language signal but the prompt itself.
- **v0.3.1 released (2026-09-02)**: Steven approved D1; the polish branch fast-forwarded to `main` at `0778d3a`, tag `v0.3.1` pushed, GitHub Release "v0.3.1 — the audited build" published as latest. It is the first public release carrying `--restricted` and A20–A31. The X launch articles (English and Chinese) are final; posting is Steven's. Xiaohongshu gets a single card through the CE line; the Douyin video is deferred (D4).
- **v0.3.1 polish (2026-09-02)**: Steven chose all four polish items. README brought level with the ledger (overnight run, `balanced` run once, `--restricted`); SKILL.md took six of eight skill-reviewer findings; three backlog code items closed with a regression module that goes 4-of-5 red against `ce16db8` — content identity in de-duplication (A29), a `claude_sessions` acceptance rule surveyed on 1,908 real transcripts (A30), and a `minimum_score` default that can actually fire (A31). 157 tests, ruff clean. REPORT.html re-rendered from the real 09-01 runs and read end to end: two copy defects fixed (English singular beside a count; "Elapsed" tile). Promotional material has its landing (Steven, 2026-09-02): X material in `promo/` (gitignored and excluded), Xiaohongshu/Douyin in the CE workspace, copy drafts in the vault — nothing under the public tree. Details in `VALIDATION.md`.

## In progress

- **Promotion drafts (2026-09-02)**: X launch article in English (Claude-written) and Chinese (Gemini draft → fidelity pass → opus review `Ship-with-edits` with zero AI-pattern hits and five fact drifts → v3 → re-verification), plus a Xiaohongshu/Douyin material pack (planning sheet, 202-character narration, dual-platform publishing copy, single-card copy) — all under `promo/`, none published. Four decisions are with Steven: v0.3.1 release, both articles, and which CE line carries the video and card. Nothing is posted until he says so.
- Trigger retest passed on 2026-08-25 (gate enumerated in full; caveats in VALIDATION.md).
- **Pushed to GitHub (2026-08-25, private at first; renamed and made public on 2026-09-02 as `steven-pku/burn-before-reset` at commit `cb1e313` for the fourth external audit round)**. First real CI run failed — six tests assumed codex/claude were installed on the runner, an assumption every local run masked. Tests made hermetic (interpreter binary as stand-in; fakes where a worker actually launches), plus a preflight regression for the missing-binary error. OWNER placeholders resolved to the real handle.
- **v0.2 bounded autonomy landed (2026-08-25)**: product direction reset per Steven — agent finds the work, one up-front mode question, burn to completion. Multi-window continuation (probe-and-retry across closed allowance windows), re-planning rounds, `bbr discover` vault-free source discovery. 69 tests; core continuation tests fail against the old behaviour.
- **README publication pass (2026-08-26)**: audited against the vault README spec. Added static license/python badges and a contents line, inserted the missing edit-config step into Quick start (the full `cp` → `validate-config` → `plan` pipeline was re-run locally against scratch sources, final exit `0`), removed a stale "v0.1" adapter version claim, linked LICENSE. English-only confirmed as the deliberate language choice. Launch assets produced 2026-08-26: `assets/social-preview.png` (1280×640, programmatic render) and `assets/demo.gif` (vhs 0.11.0, regenerable from `assets/demo.tape` against throwaway sources under `/Users/Shared/bbr-demo`; final frame verified). The demo GIF is wired into the README hero. Social preview regenerated on 2026-09-02 in the v0.3 visual identity (`assets/social-preview.png`, 1280×640, rendered from an HTML card); the upload itself is a Settings-page action on the now-public repo and is the one remaining manual step.
- **About + Chinese page (2026-08-26)**: repo description and 8 topics set via API (the About sidebar was empty since the bare push). `README.zh-CN.md` added as a Chinese explainer page — deliberately not a line-by-line translation; the English README stays authoritative — with language-switcher lines in both files.
- **CHANGELOG added (2026-08-26)**: Keep-a-Changelog format, entries grounded in git history and the status ledger — 0.1.0 (initial candidate), 0.2.0 (bounded autonomy, tag `a2a0edf`), Unreleased (external-audit hardening, README pass, rename follow-ups). v0.1.0 has no tag; the initial import commit is the anchor.
- **Third external audit repaired (2026-08-26, GPT-5.6 Pro, 4 🔴)**: non-finite durations (`inf`/`nan`) now fail configuration closed through one finite-number validator (reproduced before fixing); `validate-run` gained semantic terminal-state invariants alongside hash integrity (stop-reason vocabulary/compatibility, list/status/result agreement, `finished_at`, timestamp monotonicity); `--safe-mode` is no longer assumed stable — preflight probes `claude --help` for every load-bearing flag and fails closed (the seat's "drop the flag, rely on --tools" alternative rejected: it reopens the MCP write-tool hole); spend authority honestly bounded with `execution.max_worker_calls_per_run` (stop reason `worker_call_cap`) plus README/SECURITY positioning, with the independent latest-stop ceiling and second-source balance confirmation recorded as v0.3 backlog. 82 tests; 16 of 22 new cases confirmed red against pre-fix src in a scratch copy. Full disposition in `VALIDATION.md`.

## Blockers and risks

- Codex's documented sandbox provides write isolation, but not a project-specific read allowlist. The deterministic scanner is strict; worker read confinement is a known v0.1 limitation.
- Server-side Credits/Auto top-up state is user-asserted, not mechanically verified; the tool cannot guarantee zero server-side billing.
- Billing detection no longer reads the Worker's prose, so a quota failure reported only in the final message with a zero exit and no error event would not trip that specific check. See `SECURITY.md`.
- ~~The `$id` fields in `schemas/*.json` and the CI badge in `README.md` carry an `OWNER` placeholder that must be replaced at publication.~~ **Resolved 2026-08-25** — all four now point at `stevenpku-2026` (see the push entry above). Line kept struck through rather than deleted so the earlier caveat stays traceable.

## Verification

- `python3 -m py_compile scripts/bbr.py src/burn_before_reset/*.py`: PASS.
- `PYTHONPATH=src python3 -m unittest discover`: PASS, 157 tests, Python 3.14 (2026-09-02) — earlier rounds also green under a masked PATH with `codex`/`claude` absent.
- `uvx ruff check src tests scripts`: PASS, ruff 0.16.5 (2026-09-02).
- Regression tests confirmed to fail against the pre-repair behaviour: 7 of 10 failed in the first reverted scratch copy, both tests from the second round failed in a second one, and 16 of 22 third-audit cases failed in a third (the 6 green ones are inputs the old code already rejected). Positive-side tests pass in both states by design.
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
