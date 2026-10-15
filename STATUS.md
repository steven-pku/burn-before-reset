---
project_state: active
stage: v0-3-public
health: amber
updated_at: 2026-10-15T14:00:00+00:00
next_action_owner: Codex
next_action: Steven grades the 10-artifact D3 sample from the 2026-09-08 overnight run; that is the only input that can move task_policy.minimum_score from a proxy to value.
blocked_by: []
---

# Burn Before Reset · Status

## Current state

- Independent Kimi K3 review of v0.3.4 commit `4533f16` is complete. Codex reproduced a high-severity quota-retry safety-gate bypass and the interrupted-wait receipt defect, repaired both, and aligned the imported version with release metadata for v0.3.5. The previous Release remains published while the patch completes its release gates. No old tag is rewritten.

- [v0.3.4 is published](https://github.com/steven-pku/burn-before-reset/releases/tag/v0.3.4), non-draft and non-prerelease, and was confirmed as latest. Its annotated tag resolves to `4533f16b671d08ecf68679a63aab30b8d816b5e3`. [Main CI](https://github.com/steven-pku/burn-before-reset/actions/runs/38556911620) and [tag CI](https://github.com/steven-pku/burn-before-reset/actions/runs/38556918245) each passed all eight jobs.
- The wheel, independent Skill ZIP and SHA256SUMS are published. Public downloads match their SHA-256 hashes; the downloaded source passes all 187 tests, and downloaded packages pass the no-model demo and installed mock failure/recovery checks. No runtime dependency is declared.
- v0.3.3 has a retained tag but no Release: tag CI caught a guard startup interruption cleanup gap. v0.3.4 fixes it with a deterministic regression; no old tag was rewritten.
- The project remains a public `candidate`, not a globally installed or `verified` Skill. This distinction is not a blocker to the public candidate release Steven approved.
- Explicit reviewed-queue/autopilot selection, frozen configuration/deadline binding, an independent runtime ceiling, open-task filtering, Git worktree discovery and qualified report labels are implemented.
- English and Chinese README, a no-model first-use demo, sample report screenshot, terminal GIF, contribution checks and security-report links are aligned with the release.
- Private vulnerability reporting is enabled. The standard 1280×640 social-preview asset is included; the Settings page and file chooser now work, but both upload attempts failed with a GitHub attachment storage-request error. The 1280×640 RGB PNG passed local format inspection. No successful image replacement is claimed.
- Three defects from the first real overnight autopilot run (2026-09-08) are included in v0.3.4: `exclude_fragments` now matches substrings (`/`-anchored entries match whole segments) and `validate-config` counts what each entry catches; the planner drops the tool's own output by construction; one task failure no longer ends the run (`execution.max_consecutive_failures`, default 3). The Skill's morning-delivery and receipt-reading guidance was tightened from the same night. See CHANGELOG 0.3.4 and the dated VALIDATION entries.

## Verification

- 187 hermetic unit/integration tests pass, including seventeen new regressions for the 2026-09-08 defects that fail against `d450e82`.
- Pinned ruff 0.16.5 passes. The first-use demo validates its real plan, confirms unchanged source content and refuses execution; its illustrative reports are clearly labelled.
- A fresh Codex process is used for repository Skill inventory and startup-log verification. Discovery does not prove reliable model triggering.
- The published release was independently read back as non-draft and non-prerelease. About text is updated; README report and terminal GIF load on the public page. See the final dated entry in VALIDATION for receipts.

## Evidence and limits

- One historical overnight exercise completed 25 tasks and produced 27 artifacts across three runs. The CLI reported $71.38 in estimated usage cost before a provider refusal. This is not an invoice, a measured saving, a verified zero balance or evidence of artifact value.
- A second real overnight autopilot run (2026-09-08, Claude worker, two counted runs plus one SIGTERM-stopped recovery attempt) produced 46 genuine artifact files covering 45 distinct tasks, plus seven self-referential artifacts that passed every validation gate and are worth nothing — the planner defect fixed above. The CLI estimated $133.86 across 54 worker calls; the same qualifiers apply. The tool has no merged report across runs; a derived view was assembled by hand outside `output_root`.
- Human usefulness grades remain outstanding; a 10-artifact sample from the 2026-09-08 run is the approved first measurement (D3). They are a follow-up measurement, not an unreported successful validation or an added release gate.
- Historical real Codex tasks, a live process-group deadline stop and one small balanced-mode exercise are documented in VALIDATION. No new real worker pilot is claimed for v0.3.4.
- Worker read confinement is broader than the deterministic indexer’s allowlist; server-side balances and billing remain user-asserted. No sensitive-data unattended guarantee is made.

## One next action

Publish v0.3.5 once its full suite, installed-package checks and tag CI pass. The independent review and blocker reproduction are complete. Non-blocking follow-ups are recorded in the dated VALIDATION entry. Human artifact grading is outside this closeout; no promotion or marketplace submission is part of this task.
