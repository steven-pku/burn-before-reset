from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .state import read_json, validate_frozen_queue

BASE_FILES = {
    "RUN_PLAN.md",
    "CANDIDATES.jsonl",
    "QUEUE.json",
    "RUN_STATE.json",
    "CHECKPOINTS.md",
    "events.jsonl",
}

# Every stop reason the runner can write. A ledger carrying anything else was not
# produced by this code path, however intact its hashes are.
KNOWN_STOP_REASONS = frozenset(
    {
        "queue_exhausted",
        "operator_stop",
        "billing_or_auth_error",
        "quota_exhausted",
        "source_mutation_detected",
        "deadline_guard",
        "task_timeout",
        "descendant_cleanup_required",
        "guard_failure",
        "invalid_worker_output",
        "worker_exception",
        "stop_unconfirmed",
        "worker_failed",
        "drain_window",
        "worker_call_cap",
        "supervisor_exception",
        "planner_exception",
    }
)


def _queue_files(run_dir: Path) -> list[Path]:
    extras = sorted(run_dir.glob("QUEUE-r*.json"))
    return [run_dir / "QUEUE.json", *extras]


def _parse_stamp(raw: object) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return value if value.tzinfo is not None else None


def _integrity_errors(run_dir: Path, state: dict, tasks_by_id: dict[str, dict]) -> list[str]:
    """Hashes, files, and key sets: was this ledger written whole?"""
    errors: list[str] = []
    first_queue = read_json(run_dir / "QUEUE.json")
    if state.get("queue_sha256") != first_queue.get("tasks_sha256"):
        errors.append("state queue hash mismatch")
    for entry in state.get("rounds", []):
        queue_path = run_dir / str(entry.get("queue", ""))
        if not queue_path.is_file():
            errors.append(f"round queue missing: {entry.get('queue')}")
            continue
        try:
            round_queue = read_json(queue_path)
        except (OSError, ValueError, TypeError):
            errors.append(f"round queue unreadable: {entry.get('queue')}")
            continue
        if entry.get("tasks_sha256") != round_queue.get("tasks_sha256"):
            errors.append(f"round ledger hash differs from frozen queue: {entry.get('queue')}")
    if set(state.get("task_status", {})) != set(tasks_by_id):
        errors.append("task status keys differ from the frozen queues")
    return errors


def _semantic_errors(state: dict) -> list[str]:
    """Cross-field terminal-state invariants: could this run have happened?

    An intact hash chain only proves the fields were written together; it cannot
    prove they describe a possible state transition. A forged or corrupted ledger
    that recomputes its own hashes passes integrity and must still fail here.
    """
    errors: list[str] = []
    task_status = state.get("task_status", {})
    completed = list(state.get("completed", []))
    failed = list(state.get("failed", []))
    results = state.get("task_results", {})
    stopped = state.get("phase") == "stopped"
    stop_reason = state.get("stop_reason")

    if not stopped and stop_reason is not None:
        errors.append(f"stop reason set in a run still at phase {state.get('phase')}")

    if set(completed) & set(failed):
        errors.append("tasks listed as both completed and failed")
    for task_id in completed:
        if task_status.get(task_id) != "completed":
            errors.append(f"completed list and task status disagree: {task_id}")
        result = results.get(task_id)
        if not isinstance(result, dict) or not result.get("success"):
            errors.append(f"completed task has no successful result record: {task_id}")
    for task_id in failed:
        if task_status.get(task_id) != "failed":
            errors.append(f"failed list and task status disagree: {task_id}")
    for task_id, status in task_status.items():
        if status == "completed" and task_id not in completed:
            errors.append(f"task status completed but absent from the completed list: {task_id}")
        if status == "failed" and task_id not in failed:
            errors.append(f"task status failed but absent from the failed list: {task_id}")

    created = _parse_stamp(state.get("created_at"))
    for task_id, result in results.items():
        if not isinstance(result, dict):
            continue
        started = _parse_stamp(result.get("started_at"))
        finished = _parse_stamp(result.get("finished_at"))
        if started and finished and finished < started:
            errors.append(f"task finished before it started: {task_id}")

    if stopped:
        if not isinstance(stop_reason, str) or not stop_reason:
            errors.append("stopped run has no stop reason")
        elif stop_reason not in KNOWN_STOP_REASONS:
            errors.append(f"unknown stop reason: {stop_reason}")
        if stop_reason == "queue_exhausted" and failed:
            errors.append("stop reason queue_exhausted contradicts a non-empty failed list")
        finished_at = _parse_stamp(state.get("finished_at"))
        if finished_at is None:
            errors.append("stopped run has no parseable finished_at")
        elif created and finished_at < created:
            errors.append("run finished before it was created")
    return errors


def validate_run(run_dir: Path) -> list[str]:
    errors: list[str] = []
    for name in sorted(BASE_FILES):
        if not (run_dir / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        return errors
    tasks_by_id: dict[str, dict] = {}
    for queue_path in _queue_files(run_dir):
        try:
            queue = read_json(queue_path)
            validate_frozen_queue(queue)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"invalid queue {queue_path.name}: {exc}")
            return errors
        for task in queue.get("tasks", []):
            tasks_by_id[task["id"]] = task
    try:
        state = read_json(run_dir / "RUN_STATE.json")
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"invalid state: {exc}")
        return errors
    errors.extend(_integrity_errors(run_dir, state, tasks_by_id))
    errors.extend(_semantic_errors(state))
    if state.get("phase") == "stopped":
        for task_id, status in state.get("task_status", {}).items():
            if status not in ("queued", "completed", "failed"):
                # A stopped run may leave undispatched tasks queued, but nothing may
                # remain "running" or "waiting_quota" — those are phantom in-flight
                # entries in a run that claims to be over.
                errors.append(f"non-terminal task status in a stopped run: {task_id}={status}")
        for name in ("MORNING_REPORT.md", "STOP_REASON"):
            if not (run_dir / name).is_file():
                errors.append(f"missing finalized {name}")
        for task_id in state.get("completed", []):
            task = tasks_by_id.get(task_id)
            if not task:
                errors.append(f"completed unknown task {task_id}")
                continue
            for deliverable in task.get("deliverables", []):
                path = run_dir / deliverable
                if not path.is_file() or not path.read_text(encoding="utf-8", errors="replace").strip():
                    errors.append(f"missing completed deliverable {deliverable}")
    return errors
