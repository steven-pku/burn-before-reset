# Burn Before Reset · Project Guidance

## Scope

These rules apply only to `burn-before-reset`.

## Required startup

Before substantial work:

1. Read `PROJECT.md` and `STATUS.md` completely.
2. Read the most recent relevant entries in `DECISIONS.md`; search older entries by task keyword.
3. Read `ROADMAP.md` only when the task changes milestones, phases, or scope.
4. Read `HANDOFF.md` only when it exists with `status: open`.
5. Load research, references, and large artifacts just in time instead of preloading them.

## Sources of truth

- `PROJECT.md`: stable mission, scope, success criteria, and safety boundary.
- `STATUS.md`: current stage, health, blockers, verification, and one next action.
- `DECISIONS.md`: approved decisions and rationale; do not record unconfirmed ideas.
- `README.md`: human-facing overview; do not use it as the live status ledger.

## Work rules

- Preserve unrelated user changes and inspect the working tree before edits.
- Do not fabricate evidence, paths, completion, or validation results.
- Ask before destructive, external-facing, production, credential, billing, or paid actions.
- Keep changes narrow and follow existing project patterns.

## Validation

- Run the narrowest relevant automated check after edits.
- Record the exact check and result in `STATUS.md` when the task materially changes the project.
- Report skipped checks and remaining risk explicitly.

## Closeout

- Update `STATUS.md` after substantial project work; do not add subjective progress percentages.
- Append `DECISIONS.md` only for a decision Steven confirmed or an approved evidence-driven reversal.
- Update `ROADMAP.md` only when the plan changed and `README.md` only when human-facing behavior changed.
- Create `HANDOFF.md` only for a real pause, blocker, context transfer, or agent switch.
- Do not edit this `AGENTS.md` unless Steven approves a durable project-rule change.
