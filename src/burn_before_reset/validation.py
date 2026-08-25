from __future__ import annotations

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


def _queue_files(run_dir: Path) -> list[Path]:
    extras = sorted(run_dir.glob("QUEUE-r*.json"))
    return [run_dir / "QUEUE.json", *extras]


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
