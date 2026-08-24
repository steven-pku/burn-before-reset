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


def validate_run(run_dir: Path) -> list[str]:
    errors: list[str] = []
    for name in sorted(BASE_FILES):
        if not (run_dir / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        return errors
    try:
        queue = read_json(run_dir / "QUEUE.json")
        validate_frozen_queue(queue)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"invalid queue: {exc}")
        return errors
    try:
        state = read_json(run_dir / "RUN_STATE.json")
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"invalid state: {exc}")
        return errors
    if state.get("queue_sha256") != queue.get("tasks_sha256"):
        errors.append("state queue hash mismatch")
    queue_ids = {task.get("id") for task in queue.get("tasks", [])}
    if set(state.get("task_status", {})) != queue_ids:
        errors.append("task status keys differ from frozen queue")
    if state.get("phase") == "stopped":
        for name in ("MORNING_REPORT.md", "STOP_REASON"):
            if not (run_dir / name).is_file():
                errors.append(f"missing finalized {name}")
        for task_id in state.get("completed", []):
            task = next((item for item in queue["tasks"] if item["id"] == task_id), None)
            if not task:
                errors.append(f"completed unknown task {task_id}")
                continue
            for deliverable in task.get("deliverables", []):
                path = run_dir / deliverable
                if not path.is_file() or not path.read_text(encoding="utf-8", errors="replace").strip():
                    errors.append(f"missing completed deliverable {deliverable}")
    return errors
