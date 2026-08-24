# Task Contract

Every queued task must include:

- Stable `id`, title, source references, and objective.
- One or more concrete deliverables under the run root.
- Absolute allowed read roots and write root.
- At least one deterministic validation rule.
- Risk and human-dependency scores.
- Estimated size and checkpoint interval.

Missing deliverables, validation, source references, or write boundary make a task ineligible.

## Ranking

Use 0–5 inputs:

```text
score = 3*strategic_value
      + 2*reuse
      + 2*readiness
      + 2*verifiability
      + 2*recency
      + checkpointability
      + token_fitness
      - 3*risk
      - 2*human_dependency
```

Every input must vary with the source, or the score stops ranking. An earlier revision
derived only two of them from content and left the rest constant: 194 of 200 candidates
on a real corpus scored identically, so the queue became whichever titles hashed first.
`recency` carries the most weight per unit of effort here, because a two-year-old TODO
and this week's blocker are not the same opportunity.

`token_fitness` only breaks ties; it must not rescue a low-value task. Reject risk above the configured maximum, human dependency above the configured maximum, or scores below the threshold.

## Freeze rule

Write `QUEUE.json` once with `frozen: true` and its content hash. A run may update task status only in `RUN_STATE.json`; it must not add tasks to the frozen queue. Queue exhaustion is a normal stop condition.
