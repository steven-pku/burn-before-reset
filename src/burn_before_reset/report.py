from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import write_text_atomic


def write_morning_report(run_dir: Path, state: dict[str, Any], queue: dict[str, Any]) -> None:
    lines = [
        "# Burn Before Reset · Morning Report",
        "",
        "## Run summary",
        "",
        f"- Run: `{state['run_id']}`",
        f"- Reset at: {state['reset_at']}",
        f"- Hard stop at: {state['hard_stop_at']}",
        f"- Final phase: {state['phase']}",
        f"- Stop reason: {state.get('stop_reason') or 'unknown'}",
        f"- Planning rounds: {len(state.get('rounds', [])) or 1}",
        f"- Quota replenishment waits: {int(state.get('quota_wait_cycles', 0))}",
        "",
        "## Burn",
        "",
    ]
    pace = state.get("burn_pace") or {}
    burn = state.get("burn") or {}
    calls = int(state.get("worker_calls", 0))
    if calls:
        priced = int(burn.get("cost_known_calls", 0))
        spent = pace.get("spent_usd", 0.0)
        spent_line = f"- Spent: ${spent:.4f}" if priced else "- Spent: not priced by this provider (tokens only)"
        if priced and priced < calls:
            spent_line += f" — priced on {priced} of {calls} calls"
        lines.append(spent_line)
        lines.append(f"- Output tokens: {int(pace.get('output_tokens', 0)):,} across {calls} worker calls")
        if priced:
            lines.append(
                f"- Rate: ${pace.get('rate_usd_per_hour', 0):.3f}/hour over {pace.get('hours_elapsed', 0)}h"
            )
        left = float(pace.get("hours_remaining", 0) or 0)
        # Clock left over only means something when the clock was the limit. When
        # the allowance ran out first the remaining hours were never spendable and
        # must not read as waste. A call-cap stop is different: the cap is the
        # user's own knob, and hours left behind it are a real diagnosis.
        if left > 0.5 and state.get("stop_reason") != "quota_exhausted":
            # Time left on the clock at the moment the run stopped. The allowance
            # expires either way, so unused hours are unconverted quota, not safety.
            lines.append(f"- **{left:.1f}h of the window were left unused** — see the stop reason above for why")
    else:
        lines.append("- No worker call completed, so nothing was spent.")
    lines.extend([
        f"- First queue hash: `{state['queue_sha256']}` (later rounds carry their own, see RUN_STATE rounds)",
        "",
        "## Completed",
        "",
    ])
    completed = set(state.get("completed", []))
    failed = set(state.get("failed", []))
    task_by_id = {task["id"]: task for task in queue.get("tasks", [])}
    if not completed:
        lines.append("None.")
    for task_id in sorted(completed):
        task = task_by_id[task_id]
        lines.extend(
            [
                f"### {task['title']}",
                "",
                f"- Artifact: `{task['deliverables'][0]}`",
                "- Validation: worker completed, artifact exists, no tool was refused, and no "
                "source write was attributable to the worker.",
                "",
            ]
        )
    lines.extend(["## Failed or stopped", ""])
    if not failed:
        lines.append("None.")
    for task_id in sorted(failed):
        task = task_by_id.get(task_id, {"title": task_id})
        lines.append(f"- `{task_id}` — {task['title']}")
    lines.extend(
        [
            "",
            "## Safety record",
            "",
            "- Source writes attributed to the Worker: "
            + ("yes" if state.get("source_mutation_detected") else "no"),
            "- Allowlisted files that moved during the run: "
            + ("yes — listed below" if state.get("source_movement_observed") else "no"),
            "- Source mutation check incomplete: " + ("yes" if state.get("source_check_incomplete") else "no"),
            "- Billing/auth error detected: " + ("yes" if state.get("billing_error_detected") else "no"),
            "- Deadline guard failure detected: " + ("yes" if state.get("guard_failure_detected") else "no"),
            "- Process-group stop unconfirmed: " + ("yes" if state.get("stop_unconfirmed_detected") else "no"),
            f"- Frozen queues this run: {len(state.get('rounds', [])) or 1}; each round freezes once and is hash-validated. No task is ever added to an already-frozen queue.",
            "- Push/merge/deploy/message actions: unsupported.",
        ]
    )
    changed_paths = state.get("source_changed_paths") or []
    if changed_paths:
        lines.extend(["", "### Allowlisted paths that moved during the run", ""])
        lines.extend(f"- `{path}`" for path in changed_paths)
        attributed = bool(state.get("source_mutation_detected"))
        if attributed:
            lines.extend(
                [
                    "",
                    "This Worker had write capability, so these are attributed to it and the "
                    "run stopped. Treat them as a boundary violation until each one is "
                    "explained.",
                ]
            )
        else:
            lines.extend(
                [
                    "",
                    "The Worker held no tool that writes — a Claude worker gets Read, Grep "
                    "and Glob only; a Codex worker in safe mode runs read-only — so it "
                    "cannot be the cause and the run continued. Something else on the "
                    "machine wrote these: another agent session appending to its own "
                    "transcript, a sync client, or you. Worth a glance, not an alarm.",
                ]
            )
    worker_errors = state.get("worker_errors") or []
    if worker_errors:
        lines.extend(["", "### Errors reported by the Worker", ""])
        lines.extend(f"- {message}" for message in worker_errors)
        lines.append("")
        lines.append(
            "These arrived alongside the run and did not necessarily stop it. Read them "
            "before trusting any artifact above."
        )
    lines.extend(
        [
            "",
            "## Was this worth the quota?",
            "",
            "The runner ranks candidates by how *live* they look — signal type, how recently",
            "the source changed, evidence density. That is a proxy for value, not value itself:",
            "nothing here knows which of your projects actually matters. Grading the picks is",
            "the only way that gap closes.",
            "",
            "For each artifact above, mark one:",
            "",
            "- **worth it** — you would have wanted this done",
            "- **fine but low value** — correct work on something that did not matter",
            "- **wrong pick** — the window should have gone elsewhere; say where",
            "",
            "The selection reasons are in `RUN_PLAN.md` under each task, so a bad pick can be",
            "traced to the scoring input that caused it.",
            "",
            "## Human review",
            "",
            "Review every artifact before applying any change outside this run directory.",
        ]
    )
    write_text_atomic(run_dir / "MORNING_REPORT.md", "\n".join(lines).rstrip() + "\n")
