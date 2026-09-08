# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Dates are the dates changes landed in this repository; the validation ledger in
`VALIDATION.md` and the status ledger in `STATUS.md` remain the authoritative
record of what has actually been proven.

## [Unreleased]

### Fixed

- **`exclude_fragments` now matches fragments.** Entries were intersected against whole path components, so an entry only ever matched a complete directory or file name despite the option's name and documented examples. On a `claude_sessions` or `codex_sessions` source, where a whole project path is flattened into one directory segment, no entry could express "exclude this project" at all — the same config line behaved differently depending on source type, with nothing telling the user. Entries are now matched as a case-insensitive substring of the path relative to the source root. **This is a behaviour change: an existing configuration excludes more after upgrading, never less.** Writing a `/` at either end of an entry anchors it to a whole path segment, so an entry meant as a directory name keeps its old precision: `/.git/` excludes the `.git` directory at any depth and leaves `.github/` alone, where a bare `.git` now catches both. The shipped example configuration and `discover` proposals anchor their directory-name entries accordingly.
- **One task failure no longer ends the whole run.** A run that had completed 43 tasks with zero failures was stopped by its 44th timing out, 79 minutes before the authorized hard stop. Reading the code corrected the diagnosis: it was not only timeouts — any non-quota failure returned a terminal stop reason. A task timeout, worker-reported error, invalid worker output, worker exception or plain failure is now booked against that task and dispatch continues to the next queued item. Safety failures are unchanged and still end the run where they occur: billing or authentication errors, attributable source mutation, the deadline guard, guard failure, an unconfirmed worker stop, an incomplete source check, and descendant cleanup. The continuation gate reads the raw result rather than the classified label, so a task that both timed out and failed its guard is still terminal, and a supervisor-side crash — whose synthesized result declares neither a confirmed worker stop nor a completed source check — stays terminal despite its label being in the continuable set.
- **The planner no longer selects the run's own worker transcripts.** Workers are pinned to `<output_root>/<run>/staging/<task>`, and a session-recording CLI stores each worker's transcript in a directory named after that working directory. A re-planning round indexed those transcripts as fresh candidates and queued work against the run's own exhaust. Anything under `run.output_root` — by location, by the flattened working-directory name, or by the working directory a transcript declares — is now dropped before scoring, for every run sharing the output root and without depending on an operator-supplied exclusion. Drops are named in `RUN_PLAN.md`.

### Added

- `validate-config` reports what each `exclude_fragments` entry actually catches under each source root and warns about any entry that catches nothing. A silently inert safety control was the more dangerous half of the exclusion defect.
- Stop reason `consecutive_failure_limit`, used when the run ends because failures reached the threshold. The last task's own failure is not promoted to the run's stop reason — that would report one bad task as the cause — and every failed task's cause is named in the Morning Report instead.
- `execution.max_consecutive_failures` (default 3, range 1–20) — failures in a row that stop the run, reset by any success. `1` restores the previous behaviour where the first failure was terminal. `RUN_STATE.json` carries a `consecutive_failures` counter and the events log records each continuation and the limit being reached.
- `RUN_PLAN.md` carries an "Exclusions in effect" section and an "Excluded as this tool's own output" section, so neither an inert exclusion nor a dropped candidate is invisible to the morning reader.

### Changed

- `validate-run` no longer treats `queue_exhausted` beside a non-empty failed list as a contradiction — under the new behaviour a completed queue may legitimately carry failed tasks. It now rejects the case that really is impossible: a run-ending failure recorded inside a run that reports its queue as exhausted.
- Adding `execution.max_consecutive_failures` changes `config_sha256`. A plan frozen before this release refuses to execute against a configuration reloaded after it; re-plan rather than editing the frozen run.
- A blank `exclude_fragments` entry is refused at configuration load. Under substring matching it is contained in every path and would silently empty a source root.

## [0.3.2] — 2026-09-07

### Added

- No-model first-use demo with a real validated plan and separately labelled sample reports.
- One test command shared by contributors and CI, plus proposed release-tag/version checking.
- Independent runtime ceiling (12 hours by default, maximum 24) and configuration binding for reviewed plans.

### Changed

- **Execution migration:** `run` now requires either `--run-dir` or `--autopilot`. Reviewed queues never re-plan. Regenerate older plans before execution.
- Reset must be within 24 hours; execution requires an explicitly selected provider. The real-run template requires actual reset, source and billing confirmation.
- Completed/cancelled Markdown tasks, quotations and fenced examples no longer become open-work signals; discovery recognizes Git worktree marker files.
- README, Chinese introduction, report screenshot and terminal demo now share a reproducible first-use flow.
- Report labels distinguish claim reviews from verified claims, local handoff selection from sending, and CLI cost estimates from bills or value.
- Security reporting links, issue guidance and current Claude flag documentation are aligned. Package metadata and release version are aligned at 0.3.2.

## [0.3.1] — 2026-09-02

### Fixed

- Fourth external audit round (Grok 4.6, Kimi), all with regression tests that fail
  against `8bcc5d0` — see `VALIDATION.md` A20–A28: billing upsell words no longer
  outrank a window signal; `--restricted` joins `--safe-mode` in the Claude worker
  command (the documented tool-removal flag); the worker's own transcript directory
  is excluded from the source snapshot; sources under the temp family are treated as
  writable by any Codex sandbox; `report_language = "auto"` no longer picks Chinese
  for Japanese or Korean text; de-duplication counts any mtime change as movement,
  stamps git-dirty from the dirty files, survives corrupt sibling ledgers, rejects
  whitespace artifacts and path traversal, and folds sweep membership into the
  sweep id; the Markdown report no longer calls exhausted quota "unused window".
- Re-review of that adoption by a Codex Sol seat: hard billing terms cover a failing
  charge path beside a window word; a bare rate limit backs off briefly instead of
  sleeping a full probe interval; the transcript exclusion is shape-bound and
  Claude-only; language detection uses a kana/Hangul share rather than a single-
  character veto; git-dirty identity is a fingerprint of the whole dirty set; sweep
  identity is a membership digest; mis-shaped sibling ledgers are skipped; the
  call-cap stop keeps its unused-window line.
- De-duplication compares the *content* of cited sources when both sides carry a
  digest (`content_sha256`: file size plus the bounded prefix the indexer read): a
  touch, copy or checkout no longer re-does settled work, and a same-second edit is
  no longer suppressed. Ledgers written before this fall back to the stamp (A29).
- `claude_sessions` accepts only transcript-shaped JSONL — a first record with a
  `type` and a `sessionId`, `cwd` or `uuid` — as `codex_sessions` has required
  `session_meta` since v0.1; a data export that merely ends in `.jsonl` is skipped (A30).
- `task_policy.minimum_score` defaults to 30; the earlier 12 sat below the formula's
  floor of 24 and had never filtered a candidate. A test pins the default inside the
  reachable range (A31).
- `REPORT.html` counted one thing in the plural in English ("1 decisions framed");
  the hours tile was labelled "Hours" under "1.3h", now "Elapsed".

### Changed

- README status and worker sections brought level with the ledger: the first
  overnight run, `balanced` run once for real, `--restricted` in the worker
  description. SKILL.md wording pass: the output contract explained file by file,
  one term for the inner allowance window, the refusal clause naming all three
  required items.


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
[Unreleased]: https://github.com/steven-pku/burn-before-reset/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/steven-pku/burn-before-reset/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/steven-pku/burn-before-reset/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/steven-pku/burn-before-reset/compare/0fdd27e...v0.2.0
[0.1.0]: https://github.com/steven-pku/burn-before-reset/commit/0fdd27e
