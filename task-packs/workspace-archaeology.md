# Task Pack · Workspace Archaeology

Use when the allowed roots contain multiple projects or work directories and the user wants a recovery map.

## Candidate signals

- Active files with explicit TODO, next-step, blocked, or unverified markers.
- Dirty Git repositories, stale project status, duplicated project intent, or a missing concrete next action.

## Output

Produce one artifact that classifies each cited candidate as active, unfinished, duplicated, superseded, or decision-blocked. Include source references and one bounded next action. Never move, archive, delete, or rename anything.

## Validation

- Every classification cites an indexed source.
- Uncertain status is labeled; absence of evidence is not completion.
- No source-root mutation.
