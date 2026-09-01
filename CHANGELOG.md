# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Dates are the dates changes landed in this repository; the validation ledger in
`VALIDATION.md` and the status ledger in `STATUS.md` remain the authoritative
record of what has actually been proven.

## [Unreleased]

## [0.3.0] — 2026-09-02

### Added

- `REPORT.html`: the user's page, generated deterministically beside the Markdown
  report (`report_html.py`, `bbr report --run-dir … [--language]`). A fixed-format
  opening; a proverb verdict chosen from **what was delivered**, never from how much
  was burned; a validated categorical palette with a stroke icon per kind of work;
  "queue for my agent" → copy a handoff brief as the primary action, grading as
  optional feedback. Self-contained, no network requests, light and dark.
- `run.report_language` (the page speaks the user's language; en/zh built in,
  everything else falls back to English) and `run.output_language` (artifacts follow
  the sources they were read from, or a forced language).
- Cross-run de-duplication: `prior_completions()` skips candidates an earlier run
  in the same `output_root` already answered, until their source moves. Skips are
  counted in `reused_from_prior_runs` and named in `RUN_PLAN.md`.
- Stop reason `worker_reported_error` for a provider refusal the term lists cannot
  classify; the message reaches the report verbatim.
- Task-result fields `source_write_attributable` and run-state
  `source_movement_observed`, separating "a file moved" from "the worker moved it".
- Adaptation matrix `tests/test_report_html.py`: every stop reason × language,
  every archetype as dominant, ties, empty and sixty-artifact runs, truncation,
  missing files, hostile markup, non-Latin text, unsupported languages, determinism.

### Fixed

- Quota exhaustion misread as malformed worker output: the refusal was stated only
  in the `result` text, which diagnostics excluded as "the deliverable"; errored
  results now enter diagnostics, and the term list covers "spend limit" /
  "weekly limit" wordings (A15).
- A read-only worker was blamed for allowlisted files that moved (another agent
  appending to its own session log, a sync client); attribution now follows write
  capability (A16).
- A run that died made the next run redo its finished work — 7 of 27 artifacts in
  the first overnight run were repeats (A17).
- `report_language = "日本語"` selected the Chinese dictionary (A18); the report's JSON
  payload escaped only `</` (A19).
- SKILL.md said four up-front items were required; three are (item 4 has a safe
  default), and the closing paragraph already said so.

### Changed

- Morning Report wording: "no source write was attributable to the worker" replaces
  "source snapshot remained unchanged"; a new line separates attributed writes from
  observed movement.
- README exit-code table names `quota_exhausted` as a designed stop and documents
  `worker_reported_error`.


### Added

- `execution.max_worker_calls_per_run`: an absolute per-run cap on worker
  launches (first attempts, quota retries, and re-planned rounds all count) —
  the one spend bound the tool can enforce itself, since it cannot observe the
  server-side quota pool (third external audit).
- `validate-run` now checks terminal-state semantics, not only hash integrity:
  stop-reason vocabulary and compatibility, completed/failed/status/result
  agreement, `finished_at` presence, and timestamp monotonicity.
- Preflight probes `claude --help` for `--safe-mode` and every other
  load-bearing worker flag, refusing the run if any is missing — the flag is
  not in the published CLI reference and must not be assumed stable.

### Fixed

- Non-finite durations (`inf`, `-inf`, `nan`) no longer pass configuration
  validation: every duration, timeout, grace period, and probe interval must
  be a finite bounded number, or the SIGINT→SIGTERM→SIGKILL escalation would
  lose its bounded-stop guarantee (third external audit, reproduced).

- Hardened v0.2 seams found by a two-seat external audit: `StopRequested` is a
  `BaseException` so a SIGTERM inside the worker window is no longer swallowed
  into a fake task failure; quota retries start from a clean guard handshake;
  the Claude worker cwd is pinned to staging with the read surface limited to
  staging plus granted roots; a denied tool attempt fails the task instead of
  being promoted; replenishment waits are hard-stop-bounded; replan and
  supervisor exceptions finalise receipts instead of stranding the run.

### Changed

- README publication pass: quick start now includes the edit-config step (the
  full `validate-config` → `plan` pipeline re-verified locally), badges and a
  contents line added, a stale adapter version claim removed.
- Badge and schema `$id` URLs follow the account rename to `steven-pku`;
  historical ledger lines are kept as written.

### Documentation

- Honesty notes: per-task validation rules are guidance, not enforcement;
  rate-limit matching cannot distinguish org limits from allowance windows.
- The two-seat external audit is recorded in the validation ledger.

## [0.2.0] — 2026-08-26

Bounded autonomy: the agent finds the work, asks one up-front mode question
(review the plan, or full autopilot), and burns the quota to completion.

### Added

- Riding inner allowance windows: on quota exhaustion the supervisor sleeps
  and retries until the window reopens; only the outer `reset_at` is a hard stop.
- Re-planning rounds: a drained queue with usable time left is refilled from
  fresh signals; a round that finds nothing ends the run honestly.
- `bbr discover`: read-only proposal of session-log, repository, and document
  roots by recent activity — a note vault is never assumed.
- Claude Code worker adapter (`execution.provider = "claude"`): `safe` mode
  only, read-only by tool absence (`--safe-mode`, strict empty MCP, nothing
  beyond Read/Grep/Glob).
- `quota_exhausted` stop reason, distinct from `billing_or_auth_error`.
- Skill discovery for Claude Code (`.claude/skills/`) alongside Codex
  (`.agents/skills/`).
- CI on GitHub, made hermetic: no test may assume `codex` or `claude` is
  installed on the runner.

### Changed

- Scorer rewritten for queue diversity: 194-of-200 identical scores became 18
  distinct values on the same corpus; round-robin across projects;
  `max_tasks` cap raised 10 → 200.
- Supervisor survives operator signals: SIGHUP ignored, SIGTERM/SIGINT
  finalise receipts as `operator_stop`, zero orphans.

### Fixed

- Mixed-timezone checkpoint stamps.
- `OWNER` placeholders in the CI badge and schema `$id` fields resolved to the
  real account.

## [0.1.0] — 2026-08-25

Initial import as a public **candidate** — not `verified`, not proven safe for
unattended use. Development, the pre-publication audit, and the first real
pilot are dated 2026-08-24 in `STATUS.md`.

### Added

- Repository-scoped Agent Skill (`SKILL.md`) with an activation gate.
- Deterministic Python runner (stdlib only): strict TOML preflight, absolute
  reset deadline with timezone, allowlisted read-only indexing, candidate
  scoring, immutable frozen queue, atomic run state, checkpoints, and one
  Morning Report.
- Sequential Codex CLI worker adapter with full event capture.
- Supervised deadline watchdog with confirmed-stop receipts; guard loss fails
  the task.
- Fail-closed billing assertions: unknown Credits balance, unknown Auto top-up
  state, API-key environment variables, or billing/rate-limit errors stop the
  run.
- Worker environment filtering (`DROPPED_ENV.txt`), `0700` run directories,
  documented exit-code contract, schema drift tests.

### Fixed

- Four defects reproduced by the pre-publication audit, each repaired with a
  regression test that fails against the previous behaviour: billing detection
  reading the deliverable, Worker stdin inherited into unattended runs,
  unscoped source-mutation detection, and `git status` rewriting the source
  index.

<!-- v0.1.0 has no git tag; it is the initial import commit 0fdd27e. Retag at release if wanted. -->
[Unreleased]: https://github.com/steven-pku/burn-before-reset/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/steven-pku/burn-before-reset/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/steven-pku/burn-before-reset/compare/0fdd27e...v0.2.0
[0.1.0]: https://github.com/steven-pku/burn-before-reset/commit/0fdd27e
