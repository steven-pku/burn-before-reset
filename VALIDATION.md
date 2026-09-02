# Burn Before Reset · Validation · 2026-08-24

## Result

Lifecycle is `candidate`. Implementation, structural checks, historical replay, controlled forward test, repository fresh-process discovery, and the post-audit safety repair suite passed. A pre-publication audit then reproduced four further defects; each was repaired with a regression test that fails against the previous behaviour, and one real Codex task subsequently ran end to end through the product adapter. `PROMOTION_GATE` stands at 1 of 3. The project is not installed globally, is not `verified`, and is not proven safe for unattended sensitive data.

> This file is a ledger. Sections are appended in order. Earlier entries record what was true when they were written and are not rewritten; the pre-publication section at the end supersedes counts and gate states above it.

## Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Python syntax | PASS | All files under `scripts/` and `src/burn_before_reset/` compiled. |
| Unit/integration suite | PASS | 34 tests; config gates, path/symlink boundary, frozen contract, planner, fake worker, billing fail-close, artifact promotion, report, guard supervision, exception finalization, prompt boundary, and process-group watchdog. |
| Skill structure | PASS | `skill-creator/scripts/quick_validate.py` returned `Skill is valid!`. |
| Description budget | PASS | 60 characters total; first trigger sentence 22 characters. |
| UI metadata | PASS | `short_description` is 53 characters and `default_prompt` explicitly names `$burn-before-reset`. |
| Project status schema | PASS after correction | `health: yellow` was rejected; changed to allowed `amber`. |
| Source mutation | PASS in tests/evals | Planner test preserved source bytes; read-only A/B directories contained only original fixture and intended Skill symlink after runs. |
| End-to-end plan CLI | PASS | Real `validate-config` + `plan` + `validate-run` produced one source-linked task, frozen hash, and no source mutation. |
| Execution double gate | PASS | `run --execute` returned exit 2 while `execution.enabled = false`; no Worker launched. |

## Historical replay

Automated replay covers:

- Missing/naive/past deadline, buffer below ten minutes, and false billing assertions.
- API-key environment present during execution.
- Output/source overlap, secret-like files, excluded paths, and symlink escape.
- Invalid Codex JSONL.
- Frozen queue tampering.
- Empty queue without invented work.
- Billing/auth Worker error without retry/fallback.
- Worker plus child process stopped as one process group.
- Completed status requiring a non-empty artifact and final report.

Result: PASS, 34/34 tests.

## Post-audit safety repairs

The pre-pilot audit exposed four execution blockers. Root reproduced each applicable failure before changing the implementation.

- Guard lifecycle: the parent now supervises both Worker and guard, fails closed if the guard dies, waits for deadline escalation, cleans descendants, and records whether stop was actually observed.
- Unconfirmed termination: SIGKILL without observed process-group termination is reported as `sigkill-unconfirmed`; it cannot be counted as success.
- Exception finalization: Worker exceptions still produce structured task state, `STOP_REASON`, `MORNING_REPORT.md`, and run events.
- Timing and prompt boundaries: execution is mechanically plan-only inside sixty minutes of the hard stop; Worker prompts omit source snippets and bracket locator fields as untrusted task data.

Deterministic regressions cover stubborn descendants, premature guard death, Worker exceptions, stopped-run replay, missing artifacts, output-root escape, CLI nonzero stop status, and adversarial task metadata.

Claude Opus 5 then identified one additional P1 false-success path: a zero-exit Worker without a completed `agent_message` could promote raw JSONL tail text as an artifact. Root reproduced the control-flow path and removed the fallback. Official artifacts are now promoted only after the full success predicate; failed Worker messages remain diagnostic evidence under the Worker directory. Rehashed queues also reject unsafe task IDs and deliverable traversal, runtime task roots are rebound to the configured sources and run directory, and exact sixty-minute boundary coverage was added.

## Independent terminal review

### Claude Opus 5

- CLI: Claude Code 2.1.241.
- Main model verified from result metadata: `claude-opus-5`, provider `firstParty`; no fallback model was configured.
- Boundary: static, read-only review with only Read/Grep/Glob tools; no network requests, edits, test execution, or subagents.
- Result: `PILOT_READY_WITH_RISKS` before the cited P1 was repaired.
- Root disposition: accepted the P1 raw-event artifact finding and the rehashed path-boundary concern; repaired both. Also applied bounded P2 hardening for signal/liveness handling, failed-output isolation, default state fields, timeout budget, and exact boundary/CLI coverage. Final deterministic suite: 34/34 PASS.

The CLI result reported `total_cost_usd: 0.6171295`; this is recorded as tool metadata, not interpreted as the user's final billing statement.

### Kimi 3

- CLI: Kimi Code 0.38.0 with requested model alias `kimi-code/k3-256k`.
- Two bounded read-only attempts produced repeated `EINTR` errors while watching the local Kimi configuration files and no model or tool event.
- The final narrowed attempt was stopped after five minutes and exited 137 after ignoring a normal termination signal.
- Result: `AUDIT_INCONCLUSIVE`. No Kimi finding or approval is claimed.

## Fresh-process discovery

An actual new `codex debug prompt-input` process launched from the repository:

- Advertised exactly one `burn-before-reset` entry.
- Resolved it through `.agents/skills/burn-before-reset/SKILL.md`.
- Preserved the full 60-character description.
- Produced zero-byte startup stderr in the final debug run.

The first discovery run exposed a symlink error: `../../..` resolved to `/private/tmp` and advertised unrelated temporary Skills. The link was corrected to `../..`; the second inventory contained only this repository Skill.

## Controlled with-Skill / without-Skill A/B

Two new isolated Git directories contained the same single fixture and received the same prompt. The only designed difference was one repository Skill symlink.

Mechanical inventory:

- with-Skill: exactly one `burn-before-reset` match.
- without-Skill: zero matches.
- both debug-process stderr files: zero bytes.

Observed behavior:

- with-Skill: refused Worker execution, applied the less-than-60-minute plan-only rule, required exact `reset_at`, zero Credits, Auto top-up off, subscription authentication, and a separate output root.
- without-Skill: stopped only because the sample lacked the referenced implementation and old product note and the workspace was read-only. It did not introduce Credits, Auto top-up, subscription-auth, or hard-stop gates.

Result: PASS. The Skill changed safety-relevant decisions rather than only changing wording.

Actual model-process stderr also contained host-level warnings about shortened global Skill descriptions, existing session-state database discrepancies, and one shell-snapshot timeout. The candidate still appeared and executed its gate correctly. These warnings are recorded but not attributed to this repository.

## Governance gates

| Gate | Status | Basis |
|---|---|---|
| `HISTORICAL_REPLAY` | PASS | 34 deterministic tests, including post-audit regressions. |
| `FORWARD_TEST` | PASS | Independent new-process, controlled A/B prompt. |
| `READ_ONLY_DEFAULT` | PASS | Config default off; planner source preservation; A/B read-only. |
| `FRESH_PROCESS_VERIFIED` | PASS | One inventory match, correct path, final debug stderr empty. |
| `NO_FALSE_SUCCESS` | PASS | Empty queue, worker error, timeout/billing paths have explicit stop states. |
| `SSOT_BOUNDARY` | PASS | Project, run root, source roots, frozen queue, and external actions are separated. |
| `STATUS_DISCIPLINE` | PASS | Candidate, machine-verified, verified, released, and portable are distinct. |
| `INDEPENDENT_TERMINAL_REVIEW` | DEGRADED | Claude Opus 5 completed and its P1 was fixed; Kimi 3 CLI remained unavailable after bounded attempts. |
| `PROMOTION_GATE` | 1/3 | One real Codex task completed 2026-08-24; see the pre-publication section. |

## Remaining risks

1. Standard Codex sandbox modes do not establish a project-specific read allowlist. Do not use the execution pilot with sensitive home-directory roots.
2. Credits balance and Auto top-up are user assertions. The local watchdog cannot guarantee server-side billing behavior or cancel already-submitted server work.
3. The supervised process-group watchdog is validated locally, including stubborn descendants and guard death, but not across a real quota-reset event, system sleep/wake, or every supported Linux distribution.
4. No real Codex task has run through the product adapter; fake-worker integration and read-only behavioral evals are not promotion evidence.
5. Kimi 3 did not return a post-fix review because its local CLI stalled after file-watcher errors; independent terminal coverage therefore consists of Claude Opus 5 plus Root verification, not two completed reviewers.

## Correction review

- Correction: repository Skill symlink originally pointed one directory too high.
- Evidence: fresh inventory advertised unrelated temporary Skills; corrected inventory showed one match.
- Root cause: incorrect relative-path calculation.
- Preventive control: fresh-process inventory asserts exact match count and resolved entry path.

- Correction: first without-Skill baseline was contaminated by a readable root `SKILL.md` even though inventory disabled it.
- Evidence: model cited project hard rules after mechanical inventory showed zero match.
- Root cause: evaluation isolation failure.
- Preventive control: controlled A/B uses two new directories whose only designed difference is the repository Skill symlink.

- Correction: project `STATUS.md` used unsupported `health: yellow`.
- Evidence: `validate_status.py` rejected it.
- Root cause: schema vocabulary drift.
- Preventive control: run the canonical validator before integration and use `amber`.

- Correction: the first machine-verified candidate could lose the deadline guard, leave a descendant alive after a leader exit, or skip final reports on a Worker exception.
- Evidence: bounded fault-injection probes reproduced the guard race and missing-finalization path before repair.
- Root cause: the parent treated the guard as a fire-and-forget helper and the run loop did not own exception finalization.
- Preventive control: supervise both processes, require observed stop confirmation, finalize all ordinary exceptions, and keep deterministic regressions in the release gate.

- Correction: a syntactically non-empty raw event tail could be promoted as a successful artifact when no final Worker message existed.
- Evidence: Claude Opus 5 static review cited `_extract_final_message`; Root confirmed the success predicate accepted its fallback and added a failing regression before repair.
- Root cause: diagnostic fallback text and user-facing deliverables shared one return channel.
- Preventive control: require a completed `agent_message`, isolate failed final messages under `workers/`, and promote to `artifacts/` only after the entire success predicate passes.

---

# Pre-publication audit · 2026-08-24

Steven commissioned an independent pre-publication audit before any push. It ran against this working tree with Claude Opus 5, read-only first, then executed the repairs it recommended. This section supersedes the counts and gate states recorded above it.

## Result

Four defects were reproduced, two of them against this repository's own files. All four are repaired. Each repair ships with a regression test that was confirmed to **fail** against the previous behaviour before being accepted; positive-side tests were added alongside them so the repairs cannot over-correct. One real pilot then ran end to end.

## Defects found and repaired

| ID | Defect | Reproduction | Repair |
|---|---|---|---|
| A1 | Billing detection read the Worker's own deliverable. Any artifact containing "billing", "rate limit", "usage limit", "credit balance", or "auto top-up" was judged a billing failure: the artifact was discarded and the run aborted as `billing_or_auth_error`. | This repository's `README.md`, `SECURITY.md`, `SKILL.md`, and `references/risk-policy.md` each triggered it when fed in as Worker output. | Detection reads stderr and error events only. `_diagnostic_scan` separates diagnostics from the deliverable. |
| A2 | The Worker `Popen` set no `stdin`, so Codex inherited the parent's. Under `nohup`, cron, or a pipe -- the product's central overnight scenario -- Codex blocks reading stdin and never starts work. | Controlled A/B on one command, changing only stdin: `DEVNULL` exited in 11.0s having emitted 5 events; an open pipe that never closes had produced **zero** events and had not exited at the 90s bound. (An earlier note cited the `Reading additional input from stdin...` stderr line as the reproduction. That line appears under `DEVNULL` too, so it is not evidence of a hang; the A/B above is.) | `stdin=subprocess.DEVNULL` on both the Worker and the guard. |
| A3 | Source-mutation detection walked the entire source root unfiltered, keyed on mtime and size, and reported a bare boolean. Any background write -- a sync client, `.DS_Store`, `.git` bookkeeping -- aborted the run as `source_mutation_detected` with no evidence the user could triage. | Writing `.DS_Store` into a source root between snapshots produced a mutation verdict. | The snapshot reuses the indexer's allowlist, and `source_changed_paths` names every path that moved, in the task result and the Morning Report. |
| A4 | `git status --short` refreshes the on-disk index, changing `.git/index` mtime inside a source root. The documented claim "Planner never modifies source roots" held for bytes but not for filesystem metadata. | Measured directly: `plain: index mtime 1787583805.215547552 -> 1787583806.355329429`; with `--no-optional-locks`, unchanged. | `git --no-optional-locks -C <root> status --short`. |

## Hardening applied alongside

- Worker environment filtering. `--ignore-user-config` covers only `$CODEX_HOME/config.toml`; an environment variable could still supply a key or redirect the endpoint, defeating the `allow_provider_fallback = false` assertion. Credential and endpoint variables are now withheld and recorded in `workers/<task>/DROPPED_ENV.txt`. Proxy variables are kept by design.
- Run directories are created `0700`, and the example config no longer points `output_root` at `/tmp`. Run directories hold redacted excerpts of the user's own notes; `/tmp` is world-readable and is cleared by the OS.
- Codex `item.completed` events of type `error` are captured into `worker_errors` and the Morning Report. They arrive on zero-exit runs and were previously discarded.
- Documented exit-code contract in the README: a deadline stop is a correct outcome that still returns `1`.
- Continuous integration on `ubuntu-latest` and `macos-latest` across Python 3.11, 3.12, and 3.13: compile, full suite, a real plan-only end-to-end, the execution double gate, and a source-root checksum assertion.
- Drift tests assert the shipped JSON Schemas still describe what the code emits. They immediately caught the two new result fields missing from the schemas.

## Findings recorded without change

- `task_policy.minimum_score` is inert at its default. Enumerating all 48 planner input combinations gives scores of 30–43; the default threshold of 12 rejects 0 of 48, and `maximum_risk = 2` rejects 0 of 48 because risk is only ever 0 or 1. The only filter that fires by default is `maximum_human_dependency = 1`, which removes all 16 combinations carrying a `decision` signal. Scoring therefore ranks; it does not gate.
- `claude_sessions` is accepted as a source type but has no adapter distinct from `markdown`. Transcript lines matching a signal are excerpted into `CANDIDATES.jsonl`, which sits uneasily beside the guidance in `source-adapters.md`.
- The Codex skill inventory truncates descriptions to fit its context budget when many skills are installed; on the audit host only the first ~64 characters survived. The description is now front-loaded so its opening clause stands alone.
- `schemas/*.json` carry an `$id` under `https://github.com/stevenpku-2026/...`. resolved to `stevenpku-2026` at push.

## Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Python syntax | PASS | `python3 -m py_compile scripts/bbr.py src/burn_before_reset/*.py`. |
| Unit/integration suite | PASS | 47 tests, Python 3.14.7. |
| Regression tests fail against old behaviour | PASS | Behaviour reverted in a scratch copy: 7 of the 10 new boundary tests failed, matching exactly the four repairs plus the three hardening items. The remaining 3 are positive-side tests that must pass in both states. |
| Schema drift | PASS | Planner `TaskSpec` field set equals the schema's declared properties; run state and task result emit no undeclared fields. |
| Skill structure | PASS | `quick_validate.py` returned `Skill is valid!`; description 527 of 1024 characters. |
| Fresh-process discovery | PASS | A new `codex debug prompt-input` from the repository advertised exactly one entry, resolved through `.agents/skills/burn-before-reset/SKILL.md`, with zero-byte startup stderr. |
| CI workflow | PASS locally | The `Plan-only end-to-end` step was extracted from the workflow and executed against a copy of the repository: exit 0, including the exit-2 gate assertion and the source checksum assertion. |

## First real pilot

Run `run-20260824-232739-28d11d67`, source roots limited to three of this project's own Markdown documents, `mode = "safe"`, `max_tasks = 1`, Codex CLI 0.149.1.

- `stop_reason`: `queue_exhausted`; CLI exit `0`; `validate-run` clean.
- One artifact promoted. `completed` 1, `failed` 0.
- Source roots byte-identical: all three SHA-256 digests matched their pre-run values, and `source_changed_paths` was empty.
- Guard ready, guard exit `0`, stop confirmed, no descendant cleanup, no timeout.
- Run directory permissions `0700`.
- `DROPPED_ENV.txt` recorded five withheld variables, including `ANTHROPIC_BASE_URL` and three `*_API_KEY` entries present in the launching shell.
- `worker_errors` captured one real Codex error event on an otherwise successful zero-exit run, and it appears in the Morning Report.
- **A1 confirmed in the wild.** The promoted artifact contains both "billing" and "auto top-up". Under the previous behaviour this correct, useful deliverable would have been discarded and the run aborted as a billing failure -- on the very first real run.

## Gate ledger after this audit

| Gate | Status | Basis |
|---|---|---|
| `HISTORICAL_REPLAY` | PASS | 47 deterministic tests. |
| `FORWARD_TEST` | PASS | Independent new-process controlled A/B, unchanged from the earlier section. |
| `READ_ONLY_DEFAULT` | PASS | Config default off; planner no longer touches the Git index; pilot left source bytes identical. |
| `FRESH_PROCESS_VERIFIED` | PASS | One inventory match, correct resolved path, empty startup stderr. |
| `NO_FALSE_SUCCESS` | PASS | Empty queue, worker error, timeout, and billing paths all have explicit stop states; error events are surfaced rather than dropped. |
| `SSOT_BOUNDARY` | PASS | Unchanged. |
| `STATUS_DISCIPLINE` | PASS | `candidate`, `machine-verified`, `verified`, `released`, and `portable` remain distinct claims. |
| `INDEPENDENT_TERMINAL_REVIEW` | DEGRADED | Claude Opus 5 completed both the earlier static audit and this pre-publication audit. Kimi 3 never returned. Independent coverage is one reviewer, not two. |
| `PROMOTION_GATE` | 3/3 | Three real successful tasks across two source types, 2026-08-24/25. See the bounded coverage test below. |
| `CONTINUOUS_INTEGRATION` | PASS locally | Workflow added and its end-to-end step executed locally; it has not yet run on GitHub. |

## Remaining risks

1. Standard Codex sandbox modes still do not establish a project-specific read allowlist. Do not point the execution pilot at sensitive home-directory roots.
2. Credits balance and Auto top-up remain user assertions. The local watchdog cannot guarantee server-side billing behaviour or cancel work already submitted.
3. The watchdog is validated locally, including stubborn descendants and guard death, but still not across a real quota-reset event, system sleep/wake, or every supported Linux distribution.
4. One real task has run, not three. Fake-worker integration and read-only behavioural evals are not promotion evidence.
5. Kimi 3 did not return a post-fix review, so independent terminal coverage is Claude Opus 5 plus Root verification, not two completed reviewers.
6. Billing detection now ignores the Worker's prose. A Worker that reports a quota failure only in its final message, with a zero exit status and no error event, would not trip this specific check. The other gates still apply. See `SECURITY.md`.
7. The CI workflow has never executed on GitHub. Its first real signal arrives with the first push.

---

# Bounded coverage test · 2026-08-25

Steven asked whether the remaining promotion evidence could come from one bounded test rather than repeating the pilot. It could, and it should have from the start: `PROMOTION_GATE` counts runs, and a count does not measure coverage. Three repetitions of one run shape carry one run shape's worth of evidence.

So the remaining runs were designed against what pilot 1 had **not** exercised, rather than against the number 3.

## What pilot 1 left unproven

| Path | Why it mattered |
|---|---|
| `git` source type end to end | This is the exact code changed by repair A4. It had a unit test and no real run. |
| Multi-task loop (`max_tasks > 1`) | Per-task state writes, checkpoint accumulation, and the loop's stop conditions had only ever run once through. |
| The deadline guard actually killing a live Codex process group | **The product's central claim.** It had only ever fired against fake processes in unit tests. Pilot 1 had six hours of headroom, so the guard idled and exited 0 without stopping anything. |

## Test 1 · git source, two tasks

Run `run-20260824-235446-b5b28932`. Source root a dirty Git repository: one modified tracked file, one untracked file, two Markdown documents carrying `TODO`, `blocked`, and next-step signals.

- Frozen queue: 2 tasks, scores 38 and 35, both `risk = 1` via the Git adapter.
- `stop_reason` `queue_exhausted`, CLI exit `0`, `validate-run` clean.
- Both tasks succeeded; two artifacts promoted; `failed` empty.
- Checkpoints recorded four ordered entries across the two tasks.
- **`.git/index` mtime identical before and after the whole run** (`1787586886.605537519` both times), confirming repair A4 end to end rather than only in a unit test.
- All three source digests unchanged; `source_changed_paths` empty.

Cumulative real successful tasks: 1 + 2 = **3**, across two source types.

## Test 2 · the guard against a live Codex process

Not a bbr run. A direct test of the one path a bbr run cannot reach quickly, because execution is mechanically plan-only inside sixty minutes of the hard stop.

A real `codex exec` was launched into its own session with a long generation prompt, then `bbr guard` was pointed at it with a deadline twenty seconds out.

- Codex confirmed **alive** at T+8s, so the kill had something real to act on.
- Guard exited `0` at 21.7s.
- `STOP_NOW` written: `deadline reached at 2026-08-24T23:57:01+08:00`.
- `STOP_REASON` written: `deadline_guard:sigint` — stopped at the first escalation step, no SIGTERM or SIGKILL needed, and not `sigkill-unconfirmed`.
- Process group independently verified gone: `ps -eo pid=,pgid=` showed no surviving member, and no `codex exec` process remained anywhere on the host.

One incidental finding: the verifying script's own `os.killpg(pgid, 0)` raised `PermissionError` after the group died, because the pgid had been recycled. `process_group_alive` already handles exactly this by falling back to a `ps` scan, and returned `False` correctly. The library was right and the naive check was wrong.

## Repairs from this round

- Checkpoint timestamps mixed timezones. `started` was written in the deadline's timezone and `completed` in the local one, so adjacent lines of `CHECKPOINTS.md` spelled the same instant as `15:54` and `23:55` — a receipt that reads as an eight-hour task. Both now use the local offset.
- Claude Code could not discover the Skill. It reads `.claude/skills/` in the working directory and its parents, not `.agents/skills/`. Verified by probe: a Claude Code session started in this repository answered `NO` before the change and `YES` after. A second symlink was added, and a test now asserts both paths resolve to the canonical `SKILL.md`, because this class of breakage is silent.

## Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 49 tests. |
| Regression tests fail against old behaviour | PASS | Timezone and dual-discovery behaviour reverted in a scratch copy: both new tests failed, the other 13 passed. |
| Dual discovery | PASS | Codex resolves `r8/burn-before-reset/SKILL.md`; a fresh Claude Code process answers `YES`. |

## Gate ledger

| Gate | Status | Basis |
|---|---|---|
| `PROMOTION_GATE` | 3/3 | Three real successful tasks, two source types. |
| `DEADLINE_GUARD_LIVE` | PASS | `deadline_guard:sigint` against a live Codex process group, independently confirmed dead. |
| `INDEPENDENT_TERMINAL_REVIEW` | DEGRADED | Unchanged: one completed reviewer, not two. |

## Still unproven

1. `balanced` mode. Every real run so far used `mode = "safe"` and the `read-only` sandbox. The `workspace-write` staging path has never run against real Codex.
2. The guard firing **inside a real bbr run**. Test 2 exercised the guard directly. A run whose worker is still going when the hard stop arrives requires a task that outlives the sixty-minute execution gate, so it has not been staged.
3. Escalation beyond SIGINT. The live process stopped at the first signal, so SIGTERM and SIGKILL against real Codex remain unit-tested only.
4. Sources at real scale. All runs used a handful of small files. Indexing a full vault or a large repository is untested for both duration and candidate quality.

---

# Second worker adapter, hardening, and a test that did not run · 2026-08-25

## Claude Code worker adapter

`execution.provider = "claude"` shells out to Claude Code headless. Its read-only guarantee is **tool absence**: `--safe-mode`, `--strict-mcp-config` with an empty server map, and only Read/Grep/Glob granted.

- **Negative test that shaped the design**: with only the built-in tools restricted, a worker told to "use any tool available including cloud storage" reached for a connected Google Drive `create_file` MCP tool (blocked by `dontAsk`, but visible). With `--safe-mode` + strict empty MCP map, the same probe saw no such tool at all: `permission_denials` empty, no file created, source checksums unchanged.
- Two real end-to-end pilots passed: `queue_exhausted`, exit 0, artifact promoted, sources byte-identical, guard exit 0, `validate-run` clean.
- The first pilot's artifact opened with 200 characters of tooling apologia because `deliverables` read as a write instruction; the Worker prompt now states it is a filing location. The second pilot's artifact opened with content and explicitly declared which files it had *not* read.
- `balanced` mode is refused for this provider at config load: its read-only story cannot survive handing write tools back, and that path is unproven.

## Quota exhaustion separated from billing fault

Claude reports hitting its allowance as a structured `stop_reason: "usage_limit"` (snake_case); the billing term list matched only the prose spelling, so exhaustion would have surfaced as `invalid_worker_output`. Exhaustion is now its own signal — `quota_exhausted`, matched in both spellings — and is documented as an ordinary end of window, not a fault. The activation gate now also asks which replenishment cycle `reset_at` belongs to, and states plainly that v0.1 runs a single window: no waiting out a mid-run replenishment, no resuming a started run.

## Supervisor survival

Before: SIGTERM to the supervisor killed it silently — `phase: execute`, `stop_reason: None`, no Morning Report, worker and guard orphaned, and the run unresumable. Measured directly by killing a live supervisor.
After: SIGHUP is ignored (an overnight run survives its launching session closing, no `nohup` needed); SIGTERM/SIGINT finalise every receipt and stop the worker group — `stop_reason: operator_stop`, zero orphans, `validate-run` clean. Integration tests cover both, and both fail against the previous behaviour.

## Scoring and queue composition

On a real 2,604-file corpus the previous scorer put 194 of 200 candidates on one score, so the queue was ordered by content hash — an arbitrary sample. Every scoring input now varies with the source, a `recency` term was added (weight 2), and the queue fills round-robin across projects because recency otherwise lets the most recently touched project sweep every slot: measured before the fix, all queue slots came from one directory; after, 12 slots covered 12 projects, scores spread across 18 distinct values. Degenerate titles fall back to path-with-parent. `max_tasks` cap raised 10 → 200 (the real bounds are the hard stop, drain window, and per-task timeout). All helper binaries resolve to absolute paths at preflight, so a missing `codex`/`claude`/`git`/`ps` fails before the window opens, not during it.

## Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 62 tests. |
| Regression tests fail against old behaviour | PASS | Scorer (2), supervisor (2), timezone + discovery (2) each confirmed red in reverted scratch copies; schema-drift tests caught newly added result fields twice. |
| ruff + actionlint | PASS | Both clean; both wired into CI alongside the matrix. |

## Natural-language trigger test · DID NOT RUN

The planned experiment — a fresh session, a neutral directory, one natural-language sentence, no coaching — **failed at setup and produced zero signal about the Skill**. The session was launched from a directory where the Skill was not discoverable (no repository checkout, no project or global skill link), so no gate could fire. The session interpreted the sentence as a general request and did 36 minutes of unrelated (useful) work; the runner was never invoked; no run directory exists for that night. Recorded here because an absent test is easy to later misread as a passed one. The test is to be re-run with a scripted setup that places the session where the Skill is discoverable before the sentence is uttered.

## Scripted trigger retest · 2026-08-25 · gate PASS, trigger model-dependent

Environment: a neutral directory containing only `.claude/skills/burn-before-reset` (symlink to this checkout), verified discoverable. Same trigger sentence as the failed attempt, headless, no coaching.

- **Haiku**: confirmed the Skill in its inventory when asked directly, but did **not** invoke it for a sentence nearly verbatim to the description's trigger phrases. It answered generically. Trigger reliability is model-dependent; recorded, not patched — blind description iteration against one weak model is worse than the data.
- **Sonnet**: found the Skill, enumerated the full activation gate — absolute `reset_at` with timezone, **which replenishment cycle it belongs to**, safety buffer, separate source/output roots, mode, billing confirmations, environment check — stated that any missing field stops at a question, and stopped at a question. This is the pass criterion as designed, including the two-cycle interrogation added 2026-08-25.
- **Contamination caveat**: the Sonnet session followed the symlink into the repository and read `STATUS.md`, recognising the retest it was part of. The gate enumeration itself derives from `SKILL.md`, but the session was test-aware. A fully blind pass would require a copy of the Skill stripped of project state; accepted as-is for a candidate.
- Cost of the whole retest: two probe turns, well under a dollar. The nine-hour execution premise was deliberately not simulated: burning non-expiring quota to test a tool whose premise is expiring quota fails the tool's own first principle. The full-premise execution test is scheduled for the night before the real weekly reset.

---

# v0.2 · Bounded autonomy · 2026-08-25

Steven reset the product's center of gravity (DECISIONS 2026-08-25): the agent finds the most valuable work — the user may be asleep and does not know what should be done; discovery must not assume a note vault; exactly one up-front question (review the plan, or autopilot); and riding the inner replenishment cycle is a hard requirement, because quota left unburned is the failure mode. Safety moved from mid-flow approval gates into boundaries.

## What landed

- **Multi-window continuation.** A task that hits the allowance limit is not booked as failed: it returns to `queued`, the supervisor sleeps one probe interval (`quota_replenish_probe_minutes`, default 20), and the same task is retried — a retry against a still-closed window fails closed again at near-zero cost. Waits are bounded by the outer `hard_stop_at` and abort on operator stop. `reset_at` guidance inverted accordingly: it is now the **outer** reset; the previous guidance to point it at the inner window is superseded.
- **Re-planning rounds.** A drained queue with more than one task-timeout of usable time left re-indexes the sources as they are now and freezes `QUEUE-r{n}.json`, excluding every task id already worked. A round that finds nothing new ends the run honestly — the no-filler rule survives the burn-to-completion goal because rounds still derive only from real signals.
- **`bbr discover`.** Read-only proposals for source roots, most recently active first: Claude/Codex session logs (they exist for every user of these tools), then git repositories and markdown-rich directories under the standard work bases, pruned of hidden, dependency, and secret-like paths. On the development machine the first proposal was the Claude session-log root. Proposals are suggestions; choosing and tightening excludes stays upstream judgment.
- **One-question flow.** SKILL.md now opens with the single delegation question (review vs autopilot). In autopilot, that answer is the standing authorization: discover → configure → plan → execute, no mid-flow gate; the morning review is where human judgment re-enters. The activation gate itself is unchanged.

## Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 69 tests. |
| Continuation regression | PASS | Fake worker fails twice with a rate-limit message, then succeeds: run completes with `queue_exhausted`, `failed` empty, `quota_wait_cycles ≥ 2`. With `wait_for_replenish = false` the old single-window behaviour is preserved (`quota_exhausted`, task failed). |
| Re-planning regression | PASS | Two source files, `max_tasks = 1`: round 2 picks up the second file (`completed = 2`, `rounds = 2`, `QUEUE-r2.json` frozen). One source file: no filler round is invented (`rounds = 1`). |
| Old behaviour fails the new tests | PASS | With continuation and re-planning disabled in a scratch copy, both core tests fail. |
| Discovery | PASS | Fixture home: session logs and a recent git tree proposed; `.ssh`-style directories never proposed. Real machine: first proposal is the Claude session-log root. CLI `discover --home` covered. |
| Multi-round `validate-run` | PASS | Validation walks every frozen queue, checks per-round hashes, task-status key union, and completed deliverables across rounds. |
| Schema drift | PASS | `quota_wait_cycles` and `rounds` added to the run-state contract; drift tests enforce it. |
| ruff + actionlint | PASS | Clean. |

## Still unproven

1. A real overnight autopilot run under the new flow — discovery-chosen sources, a genuine closed-window wait, and a re-planned round against live quota. Scheduled for the night before the real weekly reset.
2. Probe cost against real providers is assumed near-zero for a closed window; measured only against fakes.
3. Artifact quality under autopilot-chosen sources — the judgment risk the mode question exists to price in — has no evidence yet either way.

---

# External audit (second-opinion, two seats) · 2026-08-26

Steven commissioned an independent audit after the push. Rationale: the maintainer of v0.2 is also its author, so the in-house review lane had collapsed into self-review. Two seats, different vendors, same contract (anchors mandatory, problems only, no edits), run blind to each other against the local checkout. Identity verified channel-side; working tree fingerprint identical before and after both audits.

- **GPT-5.6 sol** (`codex exec --sandbox read-only`): 10 findings.
- **Grok 4.6** (`grok -p`): 13 findings, plus an explicit "checked, found nothing" list.

Every adopted finding was verified against the source before any fix. Nothing either seat reported was fabricated; overlap between seats (replan unbounded past the hard stop, stale SKILL step 7, unverified round hashes) raised confidence rather than conflict.

## Adopted and fixed (commits `a2a0edf`→`da39…` series, CI green)

1. **Signal swallow (Grok 🔴)** — `StopRequested` subclassed `Exception`, so a SIGTERM landing inside the worker window was caught by `except Exception` and booked as a fake task failure; the v0.2 supervisor test had passed only because `_failure_stop_reason` checks the flag first. Now a `BaseException`, unwinding through the worker-stopping guards to a clean `operator_stop`.
2. **Stale handshake markers (Grok 🔴)** — a quota retry reused the task's `worker_dir`, so `GUARD_READY`/`START_WORKER` from the previous attempt let the launcher exec before the new guard was ready — defeating the exact race the handshake exists to prevent. Markers are now unlinked at the start of every attempt; a probe-based test asserts they are gone at worker launch.
3. **Claude worker read surface (Grok 🔴)** — the worker `Popen` set no `cwd`, and Claude's Read/Grep are unprompted in the cwd while `--add-dir` only widens: launched from a home directory, the worker could read everything there. Cwd is now pinned to the empty staging dir; SECURITY discloses the read-scope model.
4. **Denied tool attempts promoted (sol 🔴)** — the success predicate ignored `permission_denials`: a worker that reached for an ungranted tool and returned a non-empty answer was promoted. Now fails as `PermissionDenied`, output kept as diagnostics only.
5. **Replan/supervisor exceptions stranded runs (sol 🔴)** — only `StopRequested` was caught around the round loop; an indexing or freeze error left `phase: execute`, no stop reason, no report, unresumable. Now finalised as `planner_exception`/`supervisor_exception`.
6. **Wait-loop deadline seams (Grok 🟡)** — sleeps are now bounded by the hard stop as well as the probe window; the post-probe return re-checks the hard stop; a wait cut short by the deadline is labelled `deadline_guard`, not `quota_exhausted`; waits are refused after deadline/timeout/guard failures.
7. **Ledger integrity (sol 🟡 + Grok 🟡)** — `validate-run` now verifies each round ledger hash against its frozen queue and rejects `running`/`waiting_quota` in a stopped run; finalisation normalises in-flight statuses; the morning report states per-round freezing instead of the false "no task added after freeze" constant.
8. **Claim/implementation seams (both 🔴/🟡)** — SKILL step 7 ("two rounds, no substantive improvement" — a v0.1 fossil), SKILL's quota line ("stop on quota uncertainty" vs the wait loop), risk-policy's "one window per run", README's "queue freezes before execution": all rewritten to describe what the code does. Honesty notes added: per-task `validation` rules are guidance, not machine enforcement (sol); textual rate-limit matching cannot distinguish org limits from allowance windows (sol).

Five new regression tests; all confirmed red against the pre-fix behaviour in a reverted scratch copy (5/5). Full suite 75 tests, green in both the normal and the codex/claude-masked environment; CI green on GitHub.

## Declined or deferred

- **Mechanical execution of per-task validation rules** (sol): real, large; recorded as future work with the honest note above, not patched under audit pressure.
- **A dedicated cap on replenishment waits** (sol): the outer hard stop already bounds the worst case; a cap would add a second knob for the same ceiling. Disclosure chosen instead.
- **Process-level watchdog for between-task windows** (Grok): the supervisor's bounded 5s polling plus per-task dispatch checks now cover the seams found; a standing second process is queued for consideration with the v0.3 resume work, not bolted on tonight.

## Seat performance

Both seats added real value. sol was strongest on state-machine escape paths and claim-vs-code accounting; Grok was strongest on the v0.2 seams (handshake lifecycle, signal semantics, read-surface widening) and disciplined about not re-reporting settled v0.1 findings. No fabricated finding from either seat. Keep both.

---

# Third external audit (one seat) · 2026-08-26

Steven commissioned a third seat after the two-seat round: **GPT-5.6 Pro**, contract as before (anchors mandatory, problems only, no edits), run against a `git archive` ZIP of commit `1f08f4b`. HEAD had advanced past that commit (documentation and launch-asset commits only) by the time fixes landed; every anchor was re-verified against the current tree before adoption. The seat explicitly deduplicated against this ledger and re-reported nothing already recorded — that discipline held on inspection. Four 🔴 findings.

## Adopted as reported

1. **Non-finite durations pass validation (🔴 2.1)** — reproduced before fixing: `sigint_grace_seconds = inf` sailed through `load_config`, because `inf` and `nan` are not negative and the only guard was a sign check. `inf` in the escalation chain makes a grace wait never expire; `nan` makes every comparison false. A non-finite bound on the stop ladder is no bound at all. Fix: every duration, timeout, grace period, probe interval — and the count-shaped `max_tasks`, whose bare `int()` cast crashed with an uncaught `OverflowError` on `inf` — now passes one `_finite_number` validator (bool-rejecting, `math.isfinite`, closed range) at load, and the `guard` subcommand re-checks its own argparse floats. Parameterised tests cover `inf`/`-inf`/`nan` for every field.
2. **`validate-run` verified hashes, not self-consistency (🔴 2.2)** — the seat demonstrated that a ledger whose hashes are recomputed by the same implementation passes validation while describing an impossible run. Validation is now split into integrity (files, hashes, key sets — unchanged) and semantic terminal-state invariants, both always run: stop-reason vocabulary (`KNOWN_STOP_REASONS`), completed/failed/task-status/task-results agreement, completed tasks must carry a successful result record, `queue_exhausted` contradicts a non-empty failed list, stopped runs need a parseable `finished_at` that does not precede `created_at`, per-task finish must not precede its start, and a stop reason on a non-stopped phase is rejected. Nine corruption cases, each leaving every hash valid, are covered by regression tests.

## Adopted with correction

3. **`--safe-mode` treated as a stable contract (🔴 1b)** — the report's framing ("the flag is absent from the official CLI reference, so the worker may exit before any model call") was checked against reality before adoption: the flag **exists** in the installed CLI (`claude --help` lists it) and an earlier negative test proved it is load-bearing — without it the worker saw a connected cloud-storage write tool. So the defect is not a phantom flag; it is depending on an **undocumented** flag with no detection if a future release drops or renames it. Fix: preflight now probes `claude --help` for every load-bearing flag (`CLAUDE_LOAD_BEARING_FLAGS`) and fails closed, naming what is missing; a drift test pins the worker command's option set to the probed list. The report's alternative — drop the parameter and rely on the documented `--tools` — was **explicitly rejected**: that reopens the exact MCP write-tool exposure the flag closes. SECURITY.md now discloses the observed-capability status.
4. **Open-loop spend authority (🔴 design)** — direction accepted: the tool observes local time, exit codes, and refusal text, never the provider's quota pool, so before a refusal arrives every successful call is presumed safe to burn. Partly already priced (billing gates, hard stop, drain window, per-task timeout, subscription-only assertions). What landed tonight is the honest minimum: `execution.max_worker_calls_per_run` — one absolute per-run cap that every worker launch (first attempts, quota retries, re-planned rounds) counts against, enforced across rounds and surfaced as stop reason `worker_call_cap` — plus plain-language positioning in README and SECURITY that the tool stops on the user's clock and cannot promise only expiring quota is burned. The report's further asks — an absolute latest-stop ceiling independent of `reset_at`, and a second-source balance/cycle confirmation near the boundary — are recorded in `ROADMAP.md` v0.3, deliberately not bolted on under audit pressure.

## Declined

- Nothing declined outright this round. The two deferred spend-authority sub-asks above are backlog with named owners in the roadmap, not silent drops.

## Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 82 tests, normal environment. |
| Masked-PATH suite | PASS | Same 82 under a PATH holding only standard tools (git, ps, sh, python3, true, coreutils) with `codex`/`claude` absent. |
| Regression tests fail against old behaviour | PASS | src reverted to pre-fix HEAD in a scratch copy with the new tests kept: 16 of 22 new cases red (7 failures + 9 errors). The 6 green cases are inputs the old code already rejected — `-inf` grace via the sign check, and all non-finite probe intervals via the existing range check — kept in the matrix for coverage, not as proof. |
| ruff | PASS | Clean. |
| Schema drift | PASS | `worker_calls` added to the run-state contract and schema together. |

## Seat performance

Strong on input-domain and ledger-semantics reasoning; both correctness findings were real and one was demonstrated by construction. The `--safe-mode` finding needed the implementation-side correction above — right defect class, wrong factual premise — which is exactly why adopted findings are verified against the tree first. The design-layer finding restated some already-priced boundaries but drove one genuinely missing control. Keep, with the verify-before-adopt step non-negotiable.

## Balanced mode · first real run · 2026-08-26 · PASS

Commissioned by Steven to close the long-standing `blocked_by` item. One real `codex exec --sandbox workspace-write` run (`run-20260826-141005-01c39da3`), git source with a dirty tree: 2/2 tasks completed, artifacts promoted, `validate-run` clean, guard exit 0 with confirmed stop. Source bytes and `.git/index` mtime identical before and after — the `--no-optional-locks` and snapshot guarantees hold under the write-capable sandbox too; the worker chose not to use its staging write area, which is permitted. With this, both remaining `blocked_by` tails close: balanced is now evidence-backed, and the Kimi review lane's inconclusive result is treated as compensated by the three completed independent audit seats (sol, Grok 4.6, GPT-5.6 Pro).

## First full overnight run · 2026-09-01 · burned to exhaustion, stopped on two defects

The first run against a real expiring weekly allowance, unattended, autopilot, Claude
worker in safe mode. Sources: Claude and Codex session logs plus fourteen project
trees. Hourly inspection by a separate session.

**Result: 25 tasks completed, 27 artifacts, $71.38 burned across three runs.** The
allowance was driven to genuine exhaustion — the provider refused with "You've hit
your monthly spend limit" — which is the outcome the tool exists to produce. Two
defects made the night cost more than it should have.

| | Run | Outcome | Burn |
|---|---|---|---|
| 1 | `run-020916-f6a3467b` | 5 done, stopped `source_mutation_detected` | $17.17 |
| 2 | `run-025752-cad743c2` | 4 done, stopped `source_mutation_detected` | $18.50 |
| 3 | `run-033437-2db9cbc5` | 16 done, stopped `invalid_worker_output` | $35.71 |

### A15 · Quota exhaustion misread as a malformed worker result

Run 3's final worker returned `is_error: true`, `subtype: "success"`,
`stop_reason: "stop_sequence"`, and the text *"You've hit your monthly spend limit ·
raise it at claude.ai/settings/usage · your weekly limit resets 12pm
(Asia/Singapore)"*. Every structured field was useless or wrong; the one true
statement was prose in `result`.

Two failures compounded. `QUOTA_EXHAUSTED_TERMS` matched none of "spend limit" or
"weekly limit" — the same class as the earlier `usage_limit` snake_case miss, and
the reason a term list is the wrong instrument on its own. Worse, `_claude_diagnostics`
deliberately excluded `result` as "the deliverable", which is correct on success and
wrong on error: on `is_error` there is no deliverable, and `result` is the only place
the refusal is stated. So the exhaustion signal was never scanned. The run took the
`NoFinalMessage` path, was labelled `invalid_worker_output`, and stopped — instead of
entering `wait_for_replenish` and riding the window.

**Fix.** `result` now enters diagnostics whenever `is_error` is set, and reaches the
Morning Report as the worker's own words. The term list gained the shapes a limit
message actually takes. A provider refusal this code cannot classify is now
`worker_reported_error`, not `invalid_worker_output` — the morning reader gets the
message instead of being sent after a parser bug.

### A16 · Source-movement detection blamed a worker that could not write

Runs 1 and 2 both stopped on `source_mutation_detected`, discarding nine completed
tasks. The named paths:

- a Codex session transcript under `~/.codex/sessions/2026/09/01/` — another Codex
  session appending to its own transcript **while the run was in progress**
- an older Codex session transcript under `~/.codex/sessions/`
- a project's `progress.md`, written by something else on the machine

The worker held `Read,Grep,Glob` under `--safe-mode` and could not write anywhere.
Neither stop was a boundary violation; both were other processes on the machine.

A3 fixed the noisiest version of this by scoping the snapshot to the indexer's
allowlist. That was necessary and insufficient: the sources this tool is *built* to
read — agent session logs, live project trees — are precisely the ones something else
is always writing to. A before/after diff over them measures machine activity, not
worker containment. The instrument could not answer the question being asked of it.

**Fix.** Attribution now comes from capability, not from the diff. `source_changed`
stays an observation and is always reported; `source_write_attributable` — movement
AND a worker that could write — is what fails the task. Read-only workers (any Claude
worker; Codex in safe mode) are never blamed. Codex in `balanced` mode still fails
closed, unchanged. The boundary itself is not weakened: it is enforced by the absent
tools and the sandbox, and an attempt to reach past it is caught directly by
`permission_denials`, which already blocks promotion.

The Morning Report now separates "writes attributed to the Worker" from "files that
moved", so not stopping does not become not telling.

### Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 101 tests. |
| Regression tests fail against old behaviour | PASS | HEAD checked out to a scratch worktree with the new tests kept: all 7 new cases red (5 failures + 2 errors); green on the fixed tree. |
| Schema drift | PASS | `source_write_attributable` and `source_movement_observed` added to the task-result and run-state schemas in the same change; the schema-coverage test caught the omission first. |
| Real payload as fixture | PASS | A15's test uses the 2026-09-01 worker result verbatim, including the lying `subtype: "success"`. |

### Still unproven

- Whether the 27 artifacts were worth $71.38. The Morning Report asks for a grade per
  artifact; until that is answered the scorer is ranking how *live* a finding looks,
  which is a proxy for value, not value.
- Window utilisation. Run 3 exhausted the allowance in 1.26h with 2.96h nominally
  left. The report calls that unused window, which reads as failure when the real
  cause was the allowance running out first. Burn and clock need separating.

### A17 · A dead run made the next run redo its finished work

Runs 1 and 2 stopped early (A16). Run 3 then indexed the same unchanged sources,
re-derived the same task ids from them, and worked them again — the task id hashes
the source reference and its signals, so an unchanged source produces the same id
every time. Nothing in the planner looked at sibling run directories.

Replaying the night through the fix identifies the repeats exactly:

| Run | Completed | Already answered by an earlier run |
|---|---|---|
| `run-020916` | 5 | 0 |
| `run-025752` | 4 | **4** — every task it completed |
| `run-033437` | 16 | 3 |

Seven of 27 artifacts were repeats: two project directories swept three times
each, one plan document audited three times, one decision card written twice. Run 2 produced
nothing that run 1 had not already produced, so its $18.50 bought no new work;
proportionally the night lost roughly $25 of $71.38 to redoing settled questions.

**Fix.** `prior_completions()` reads sibling run directories in the same
`output_root` and collects every completed task whose deliverable still exists and
is non-empty, along with the newest modification time across the sources it cited.
A candidate is skipped when its id matches and its sources have not moved since —
*answered stays answered until the source moves*, which keeps a genuinely updated
file eligible. Skips are counted in `reused_from_prior_runs` and named individually
in `RUN_PLAN.md` under **Already answered by an earlier run**, with a pointer to the
run and artifact holding the answer: dropping a candidate silently would look
identical to never having found it.

A completion whose artifact has since been deleted does not gate, so a pruned run
directory restores eligibility rather than permanently suppressing a topic.

### Mechanical checks · A17

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 109 tests. |
| Regression tests fail against old behaviour | PASS | HEAD in a scratch worktree with the new tests kept: the three load-bearing cases red (2 failures + 1 error). The two remaining cases — a moved source is re-picked, a missing artifact does not gate — pass against old code by construction; they guard the fix against over-reach rather than prove it. |
| Replayed against the real night | PASS | `prior_completions` over the real run directories reports 0 / 4 / 3 avoidable repeats per run, matching the 7 duplicate artifacts found independently by grouping artifacts by task id. |
| Schema drift | PASS | `reused_from_prior_runs` added to the run-state schema in the same change; the schema-coverage test caught the omission first. |

## HTML report · 2026-09-02 · the user's page, held to a public-release standard

The Markdown Morning Report is the agent's contract. `REPORT.html` is the user's
deliverable, generated deterministically beside it by `report_html.py`, and the
first thing a stranger will judge this tool by. Four design rounds with Steven
converged on: a fixed-format opening (no free prose — every string comes from a
dictionary, data fills slots), a proverb as the verdict on **what was delivered**
(never on how much was burned), neutral fact tiles, a validated categorical
palette with an icon per kind of work, and follow-up ("queue for my agent" → copy a
handoff brief) as the primary action with grading demoted to optional feedback.

### Adaptation matrix (tests/test_report_html.py, 17 cases)

The page must hold across languages × outcomes × delivery shapes, not on the one
night it was designed against. Synthetic runs cover: every stop reason the runner
can write plus `None` and an unknown future reason; each of the seven archetypes as
the dominant delivery; ties; fault and empty runs; sixty artifacts; an artifact past
the embed budget; a completed task whose file is gone; a provider that reports
tokens but no price; a state with no `burn_pace` and no `events.jsonl`; hostile
titles and bodies; Japanese, Arabic and emoji text; unsupported UI languages; and
byte-for-byte determinism.

Two real defects were caught by the matrix before anyone outside saw the page:

| | Defect | Fix |
|---|---|---|
| A18 | `report_language = "日本語"` selected the **Chinese** dictionary: the language check treated "any CJK character" as Chinese, and 日本語 is written in Han characters. A Japanese user would have received a Chinese page. | Explicit allowlist of Chinese spellings only; everything else that is not `auto` falls back to English. No machine guess. |
| A19 | The JSON payload feeding the page's script escaped only `</`, so a title containing `<script>` reached the page verbatim inside the JSON block — harmless to the parser, but a raw `<script>` from user data is not an invariant worth arguing about. | Every `<`, `>` and `&` in the payload is `\u00xx`-escaped. |

### Integration

- `run.report_language` (default `auto`): the orchestrating agent sets it from the
  conversation; the report speaks the user's language, the artifacts follow
  `output_language`. Languages without a dictionary (currently en, zh) render English.
- The runner writes `REPORT.html` after `MORNING_REPORT.md`, fail-soft: a rendering
  error is recorded as `report.html_failed` in events.jsonl and never blocks
  finalisation. `validate-run` does not require the HTML file.
- Categorical hues were run through the dataviz validator in both modes (adjacent
  CVD ΔE 9.1 light / 8.4 dark, normal-vision 22.9 / 19.7); the three light-mode hues
  below 3:1 always ship with a text label. Orange is reserved for the brand and red
  for faults, so no kind of work can impersonate a status.

### Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 128 tests (109 prior + 17 matrix + 2 integration). |
| Regression tests fail against old behaviour | PASS | A18 red on the previous language check; A19 red on the previous payload escaping; the runner integration test red before `write_html_report` was wired. |
| No external requests | PASS | Asserted on every rendered scenario. |
| Strict YAML on SKILL.md after edit | PASS | `yaml.safe_load` clean. |

## Fourth external audit · 2026-09-02 · Grok 4.6 and Kimi seats on `8bcc5d0`

Two independent seats, same brief, same commit; their findings overlapped on four
points and each added what the other missed. Every finding below was verified
against the tree and the installed CLI before adoption. The regression module is
`tests/test_audit_round4.py`. It carries an in-module shim so it collects on the audited
tree; run there (`git worktree add … 8bcc5d0`, copy the module in, `python -m unittest
tests.test_audit_round4 -v`) it reports 16 failures and 7 errors of 23 cases — the two
green ones are guards (hard billing terms still fail closed; soft billing alone is still
a fault) that the old tree already satisfied. All 23 pass after the fixes.

### Adopted

| | Finding (seat) | Verified as | Fix |
|---|---|---|---|
| A20 | Billing outranked a window signal: upsell words in a limit message ("enable auto top-up", "billing cycle") stopped the run as a charging fault instead of pausing; bare `"limit reached"` classified context-window errors as exhaustion (both seats). | Term lists and precedence as described in `worker.py`/`runner.py`. | Hard billing terms (a charge path: `credit balance`, `authentication failed`, `billing details`, `payment method`…) fail closed regardless; soft terms (`billing`, `paid credits`, `auto top-up`) count only without a window signal. `limit reached` dropped. `classify_refusal()`. |
| A21 | `--safe-mode` does not remove built-in tools; `--restricted` is the documented removal of code-running tools and WebFetch (Grok, from `claude --help`). | Confirmed on the installed CLI: `--safe-mode` "starts with all customizations… disabled"; `--restricted` "removes the built-in tools that run commands or code … and WebFetch unless `--tools` names them". | `--restricted` added to the worker command and to the load-bearing flag set; preflight now matches whole flags, not substrings; SECURITY.md restates the guarantee as `--tools` allowlist + `--restricted`, not `--safe-mode`. |
| A22 | The Claude worker writes its own transcript into the user's session root, in a directory named after its cwd, so a `claude_sessions` source reports movement on every task (Kimi, hypothesis). | Confirmed: `~/.claude/projects/…-staging-<task>/` directories exist for every task of the 09-01 runs. | The snapshot skips paths carrying the run's own name. |
| A23 | A16's capability rule treated every safe-mode Codex worker as unable to write anywhere, but read-only sandboxes leave the temp family writable, so a source root under `$TMPDIR` could be written and the run would continue (both seats, hypothesis on the sandbox fact). | Sandbox behaviour not probed; the exposure is real regardless of it. | Attribution is now per path: movement under `/tmp`, `/var/folders`, `$TMPDIR` is attributable to any Codex worker. Docstring no longer claims "cannot write anywhere". |
| A24 | `report_language = "auto"` still picked Chinese for Japanese and Korean text: kana were counted as Chinese evidence and the Han range literally began at U+8C48 and ran to U+FAFF, swallowing every Hangul syllable (both seats; Korean and `zh-HK` from Grok). | Reproduced: pure Japanese → zh, pure Korean → zh, `zh-HK` → en. | Han-only ranges; any kana or Hangul in the sample vetoes Chinese; regional spellings (`zh-hk`, `zh-sg`, `zh_CN`…) normalised. `output_language` is validated as a language name before it becomes a prompt rule. |
| A25 | De-duplication treated only a *newer* stamp as movement, so `cp -p`, `tar -x`, `touch -r` or a checkout that set an older mtime was silently suppressed; naive stamps crashed the comparison (both seats). | Reproduced. | Any difference is movement; naive stamps are assumed local, mirroring `_recency`. |
| A26 | Git-dirty freshness used the repository *root* mtime, which POSIX does not advance on a content edit, so further uncommitted changes were suppressed indefinitely (both seats, Grok with a nested-edit reproduction). | Reproduced. | Stamp is the newest mtime over the files `git status` lists. |
| A27 | `prior_completions` parsed sibling ledgers with no defences: one truncated `RUN_STATE.json` in `output_root` raised through `plan_run`; `deliverables[0]` was stat'ed without a traversal check; a whitespace-only artifact counted as an answer; sweep `newest` was a string max and a sweep's identity ignored its membership (Kimi; sweep points from both). | Reproduced. | Per-sibling try/except; ids validated against `TASK_ID_PATTERN`; deliverable must resolve inside the sibling; non-empty means non-whitespace; sweep `newest` is a datetime max and the member count is part of the sweep id. |
| A28 | The Markdown report printed "*N h of the window were left unused*" on a `quota_exhausted` stop, reading exhaustion as under-achievement (both seats; the 09-01 "still unproven" item, now closed). | Reproduced. | The line is suppressed for `quota_exhausted` and `worker_call_cap`. |

Also fixed from the same round: the `round.planned` detail in `REPORT.html` read a
field the runner never emits (Kimi); `_merged_tasks` now drops ids that fail
`TASK_ID_PATTERN` so a foreign run directory cannot reach the page's selectors (Grok).

### Not adopted, and why

- **Roll A16 back / blame `balanced` less.** Kimi argued `balanced` is confined mechanically too and should not be the one mode still stopped by movement. Kept as is: `balanced` is the one mode holding a write-capable sandbox and the least exercised in real runs; the diff stays its tripwire until that changes. The per-path rule above repairs the actual hole.
- **Short backoff for a bare `rate limit`** (Kimi). A transient 429 currently earns a full replenishment probe interval. Bounded by the hard stop and the call cap, so a throttle costs minutes, never the night. Deferred to a follow-up with its own test.
- **Codex TMPDIR sandbox probe.** Not run; the fix does not depend on the outcome.

### Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 151 tests. |
| Round-4 module against `8bcc5d0` | PASS (red) | 16 failures + 7 errors of 23 (two guards green by design); all green after. Reproduction command above. |
| ruff | PASS | Clean. |
| `claude --help` re-probe | PASS | `--restricted` advertised on the installed CLI; preflight would refuse a CLI without it. |

### Seat performance

Both seats read the whole tree, cited file:line, and separated reproductions from
hypotheses as the brief asked. Grok's `--help` reading overturned a claim this
project had carried since 08-25 — the single most valuable finding of the round.
Kimi's transcript-noise hypothesis was confirmed empirically within minutes and
its sibling-ledger robustness list was the most complete. The overlap between the
two on billing precedence, git-dirty stamps and `auto` language is what makes the
adoption confident.

### Re-review of the adoption · Codex Sol seat · 2026-09-02

The adoption itself was put to a third seat (`codex exec`, read-only, GPT-5 family — the
seat reported its exact version as uncertain) with the brief "audit the author's
adoption, not the repository". Verdict 🔴, thirteen findings. Verified against the tree:

**Adopted**

- The red/green claim was not reproducible as written: the module imported a symbol
  the audited tree lacks, so it could not even collect there. The shim now lives in the
  module and the exact reproduction is recorded above.
- A20: `soft and not quota` let a *failing* charge path pause when the message also
  carried a window word ("subscription payment failed … usage limit"). Hard terms now
  include `payment failed`, `credits exhausted`, `top-up failed`, and tests cover the
  collision. A bare rate-limit word is classified `throttle_only` and backs off for at
  most two minutes instead of a full probe interval — the deferred Kimi item, now done.
- A22: the transcript exclusion matched any path containing the run name, for every
  provider. It now matches only a path component carrying both the run name and
  `staging`, and only under the Claude worker; a source file that merely mentions the
  run name stays watched (tested).
- A24: one kana or Hangul character vetoed Chinese for a whole report; the veto is now
  a share (over a twentieth of letters). The language-name check accepted a sentence
  without punctuation; it now allows at most three words of at most sixteen characters.
- A26: the newest dirty-file mtime could not represent a deletion, an edit to a file
  that was not the newest, or an untracked directory. The git source now carries a
  `fingerprint` of the whole `--porcelain --untracked-files=all` status, folded into the
  task id, so any change to the dirty set is a new task.
- A27: sibling ledgers were guarded only against parse errors; a well-formed but
  mis-shaped one (`completed: 1`, `tasks: null`) still raised. The whole sibling is now
  processed under one guard. A sweep's identity was its member *count*; it is now a
  digest of its membership, so a swapped member is a different sweep.
- A28: the unused-window line was also suppressed for `worker_call_cap`; the cap is the
  user's own knob and hours left behind it are a diagnosis. Only `quota_exhausted`
  suppresses it.
- SECURITY.md said read-only sandboxes are "known" to leave the temp family writable;
  the sandbox was never probed. Reworded as a fail-closed assumption.
- STATUS.md counted two declined items; there were three.

**Partially adopted**

- A23: the `/var/folders → /private/var/folders` alias was handled but not tested;
  a test now pins both spellings. The seat's remark that CI runners may not exercise it
  stands — the resolution is static and covered by the test on every platform.
- A25: any mtime difference counts as movement, which the seat notes still misses a
  same-second edit and re-does work on a metadata touch. True; a content hash of cited
  sources is the real fix and is recorded as the next step rather than bolted on here.
  Naive stamps are assumed local time — a ledger carried across time zones can compare
  wrong; recorded as a limitation.

**Declined**

- Attribute `balanced` per path like `safe`. The seat is right that mode does not imply
  the ability to write a given source path. It stays fail-closed on purpose: `balanced`
  is the one mode with a write-capable sandbox and the least real-run exposure, and the
  diff is its only vendor-independent tripwire. Recorded as a judgment, not a fact.

**Seat performance.** Thirteen findings, every one with a file:line, three of them
material (the unreproducible red claim, the dirty-set identity, the mis-shaped sibling
guard) and none a false positive. The seat also read `claude --help` itself and confirmed
the `--restricted` / `--tools` interaction. Keep.


## v0.3.1 polish · 2026-09-02 · closing what the ledger had left as "next"

Steven's scope for the final polish before promotion: README fact sync, SKILL.md wording,
REPORT.html detail, and the three code items this ledger and the project backlog had
recorded as next steps. Regression module `tests/test_content_identity.py`; run against
the tree before this round (`ce16db8`, scratch worktree, module copied in), 4 of 5 cases
fail — the fifth guards ledgers written before this round and passes on both trees by
construction.

### Adopted

| | Item | Was | Now |
|---|---|---|---|
| A29 | Content identity in de-duplication — the "real fix" A25 recorded as next | `_already_answered` compared the newest cited mtime: a `cp -p`, `tar -x` or checkout re-did settled work, and a same-second edit was suppressed. | Every indexed file record carries `content_sha256` — the file size plus the bounded prefix the indexer read — and a sweep carries a digest over its members. When both the sibling ledger and the candidate carry one, identity is content; ledgers written before this round fall back to the stamp. |
| A30 | `claude_sessions` had no acceptance rule (backlog item since 2026-08-24) | Any `.jsonl` under the root with a marker word was indexed as a session; `codex_sessions` had required a `session_meta` first record since v0.1. | The first record must be a typed entry bound to a session (`type` plus `sessionId`, `cwd` or `uuid`). Surveyed on 1,908 real transcripts on one machine: every one opens that way (1,901 with `sessionId`). `source-adapters.md` states the rule as observed, not published. |
| A31 | `task_policy.minimum_score` default 12 sat below the formula's floor (backlog item since 2026-08-24) | The formula bottoms out at 24 for a file record; the 09-01 corpus ranged 45–59. The default had never removed a candidate. | Default 30 in code and example, documented in `task-contract.md`; a test pins the default inside the reachable range so the knob cannot go dead again. It drops only a stale file carrying one weak marker. |

Also in this round: README's status paragraph and worker section were behind the ledger
(three real tasks → the overnight run; "`balanced` has never run for real" → run once on
08-26; `--restricted` absent from the worker description while SECURITY.md carried it).
SKILL.md took six of eight findings from a skill-reviewer pass — the output contract
explained file by file, `allowance window` as the one term for the inner cycle, the
refusal clause naming all three required items, `Worker` casing, item 3 as a checklist,
em dashes; declined were a body/description de-duplication that would have left the body
incomplete, and a README-wide casing sweep beyond the four role lines fixed.

### Mechanical checks

| Check | Result | Evidence |
|---|---|---|
| Unit/integration suite | PASS | 156 tests, Python 3.14. |
| New module against `ce16db8` | PASS (red) | 4 failures of 5 in a scratch worktree with the module copied in; all 5 green after. |
| ruff | PASS | `ruff 0.16.5`, `check src tests scripts` clean. |
| Schema drift | PASS | `content_sha256` lives inside `source_refs` items, which the task-spec schema types as free objects; run-state and task-result contracts unchanged. |
| Real 09-01 runs re-rendered | PASS | `bbr report --run-dir` over copies of runs 1 and 3 under current code, exit 0. |

### Judgment, not fact

- A31 changed no real queue: nothing in the 09-01 corpus scored under 45. Whether a
  stale single-marker file deserves a slice of the night is a product judgment; the 27
  artifact grades remain the only input that could turn the scorer from proxy to value.
- A29 hashes the prefix the indexer reads plus the file size. A change entirely past
  the byte cap that leaves the size identical is not detected. Recorded, not fixed.
