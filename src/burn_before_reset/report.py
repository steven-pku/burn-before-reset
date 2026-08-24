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
        f"- Queue hash: `{state['queue_sha256']}`",
        "",
        "## Completed",
        "",
    ]
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
                "- Validation: worker completed, artifact exists, and source snapshot remained unchanged.",
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
            "- Source mutations detected: " + ("yes" if state.get("source_mutation_detected") else "no"),
            "- Source mutation check incomplete: " + ("yes" if state.get("source_check_incomplete") else "no"),
            "- Billing/auth error detected: " + ("yes" if state.get("billing_error_detected") else "no"),
            "- Deadline guard failure detected: " + ("yes" if state.get("guard_failure_detected") else "no"),
            "- Process-group stop unconfirmed: " + ("yes" if state.get("stop_unconfirmed_detected") else "no"),
            "- New task added after freeze: no; queue hash revalidated.",
            "- Push/merge/deploy/message actions: unsupported.",
        ]
    )
    changed_paths = state.get("source_changed_paths") or []
    if changed_paths:
        lines.extend(["", "### Allowlisted paths that moved during the run", ""])
        lines.extend(f"- `{path}`" for path in changed_paths)
        lines.extend(
            [
                "",
                "Check each one before treating this as a boundary violation. A background "
                "sync client touching an indexed file leaves the same trace as the Worker "
                "writing to it.",
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
            "## Human review",
            "",
            "Review every artifact before applying any change outside this run directory.",
        ]
    )
    write_text_atomic(run_dir / "MORNING_REPORT.md", "\n".join(lines).rstrip() + "\n")
