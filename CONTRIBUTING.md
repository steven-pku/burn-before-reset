# Contributing

This project works with local notes, repositories and subscription quota. Contributions should include evidence that their changes preserve the documented execution boundaries.

## Before you open a PR

```bash
python3 scripts/check.py                  # hermetic tests; no model CLI required
uvx ruff==0.16.5 check .                  # pinned to the same version as CI
python3 scripts/demo.py                   # plan + illustrative report; no model calls
```

## The three rules every change follows

1. **A bug fix ships with a test that fails against the previous behaviour.** Check out the old tree into a scratch worktree, copy your test in, and watch it go red. A green test that was never red proves nothing. Record the red/green pair in `VALIDATION.md`.
2. **Safety gates fail closed.** Billing uncertainty, an unconfirmed process stop, a lost deadline guard, a source write attributable to a worker — each stops the run. Never widen a gate to make a scenario pass; narrow the scenario or find the real cause. Never propose dropping `--safe-mode` (see `SECURITY.md`).
3. **Every user-facing string comes from a dictionary.** `REPORT.html` and the Markdown report are deterministic: data fills slots, nothing is composed freestyle. New copy goes into `CHROME` in `report_html.py` for every supported language, and the adaptation matrix in `tests/test_report_html.py` must still pass.

## What a good PR looks like

- One concern per PR. A safety fix and a report tweak are two PRs.
- The description says what was observed, what was wrong, what changed, and how it was verified — same shape as a `VALIDATION.md` entry, because that is where it ends up.
- No new external requests, dependencies, or network calls. The runner and the report are self-contained by design.
- Schemas in `schemas/` change in the same commit as the fields they describe; the schema-coverage tests will catch you otherwise.

## Reporting a security issue

See `SECURITY.md`. Please do not open a public issue for anything that could let a run act outside its allowlist or spend money it should not.

## Audits are welcome

This tool has been through four external audit rounds. If you want to audit it, `docs`-free is fine: start from `SKILL.md`, then `worker.py`, `runner.py`, `planner.py`. Findings with a file:line and a reproduction path are adopted fast; hypotheses are welcome too — label them as such.

## Release consistency

Before proposing a tag, run `python3 scripts/check.py --release-tag vX.Y.Z` with the intended version. Keep `pyproject.toml` and the release entry in `CHANGELOG.md` aligned. An Unreleased entry is not a published release.
