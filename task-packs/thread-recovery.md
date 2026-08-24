# Task Pack · Thread Recovery

Use for allowlisted Codex or Claude session transcripts.

## Candidate signals

- Explicit next step, unrun test, unresolved decision, abandoned patch, blocked claim, or requested follow-up.

## Output

For each selected item record the session reference, original timestamp, bounded context, current evidence, and the smallest restart action. Do not reproduce full private transcripts.

## Validation

- Session file is structurally valid for its adapter.
- Each item separates quoted source signal, current-state inference, and unknowns.
- No credentials, private absolute paths, or transcript dumps appear.
