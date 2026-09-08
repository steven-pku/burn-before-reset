from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_text_atomic(path: Path, value: str) -> None:
    write_bytes_atomic(path, value.encode("utf-8"))


def write_json_atomic(path: Path, value: Any) -> None:
    write_bytes_atomic(path, json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8") + b"\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def freeze_queue(path: Path, tasks: list[dict[str, Any]], created_at: str) -> dict[str, Any]:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen queue: {path}")
    queue = {
        "schema_version": 1,
        "frozen": True,
        "created_at": created_at,
        "tasks_sha256": content_hash(tasks),
        "tasks": tasks,
    }
    write_json_atomic(path, queue)
    return queue


def validate_task_spec(task: Any) -> None:
    if not isinstance(task, dict):
        raise ValueError("queue task must be an object")
    task_id = task.get("id")
    if not isinstance(task_id, str) or not TASK_ID_PATTERN.fullmatch(task_id):
        raise ValueError("task id contains unsafe path characters")
    deliverables = task.get("deliverables")
    if not isinstance(deliverables, list) or len(deliverables) != 1:
        raise ValueError("task must contain exactly one deliverable")
    deliverable = deliverables[0]
    if not isinstance(deliverable, str) or not deliverable or "\\" in deliverable:
        raise ValueError("task deliverable must be a POSIX relative path")
    path = PurePosixPath(deliverable)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("task deliverable must not escape the run directory")
    if len(path.parts) < 2 or path.parts[0] != "artifacts":
        raise ValueError("task deliverable must be under artifacts/")


def validate_frozen_queue(queue: dict[str, Any]) -> None:
    if queue.get("frozen") is not True:
        raise ValueError("queue is not frozen")
    tasks = queue.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("queue tasks must be a list")
    if queue.get("tasks_sha256") != content_hash(tasks):
        raise ValueError("frozen queue hash mismatch")
    for task in tasks:
        validate_task_spec(task)


def is_terminal_failure(result: dict) -> bool:
    """Failure conditions that end a run where they occur, whatever else is true.

    Lives here because two callers must never let it drift: the runner decides
    with it whether dispatch may continue past a failed task, and `validate_run`
    uses the same rule to reject a ledger showing a run that continued past one.
    A copy in each would eventually disagree, and the disagreement would show up
    as a run that validated clean after continuing past a guard failure.

    The raw result is checked rather than the classified stop reason: the
    classifier returns the first match in priority order, so a task that both
    timed out and failed its guard reads as `task_timeout` — a continuable label
    over a condition that must never be continued past.
    """
    return bool(
        result.get("billing_error")
        or result.get("quota_exhausted")
        or result.get("source_write_attributable")
        or result.get("deadline_stop")
        or result.get("descendant_cleanup_required")
        or result.get("guard_failed")
        or not result.get("stop_confirmed")
        or not result.get("source_check_completed")
    )
