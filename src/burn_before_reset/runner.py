from __future__ import annotations

import json
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import AppConfig
from .report import write_morning_report
from .state import (
    read_json,
    validate_frozen_queue,
    write_json_atomic,
    write_text_atomic,
)
from .worker import run_task


class StopRequested(Exception):
    """The operator asked the supervisor to stop."""


_stop_requested = False


def _request_stop(signum: int, _frame: Any) -> None:
    global _stop_requested
    _stop_requested = True
    raise StopRequested(f"signal {signum}")


def install_supervisor_signals() -> None:
    """Keep the supervisor alive through a closing terminal, and stop it cleanly otherwise.

    A supervisor killed mid-run leaves the queue half-worked with no stop reason and
    no morning report, and the run cannot be resumed. SIGHUP is ignored outright so
    ending the launching session does not end an overnight run. SIGTERM and SIGINT
    are turned into an ordinary stop that still finalises every receipt.
    """
    for name, handler in (
        ("SIGHUP", signal.SIG_IGN),
        ("SIGTERM", _request_stop),
        ("SIGINT", _request_stop),
    ):
        available = getattr(signal, name, None)
        if available is not None:
            try:
                signal.signal(available, handler)
            except (OSError, ValueError):
                # Not the main thread, or the platform refuses. Not fatal.
                pass


def _checkpoint(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n\n")


def _event(path: Path, event_type: str, **payload: Any) -> None:
    record = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "type": event_type,
        **payload,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")




def _work_queue(
    config: AppConfig,
    run_dir: Path,
    state: dict[str, Any],
    tasks: list[dict[str, Any]],
    entry_script: Path,
    stop_reason: str,
) -> str:
    """Dispatch the frozen queue. Returns the reason dispatch ended."""
    drain_at = config.run.reset_at - timedelta(minutes=config.run.drain_window_minutes)
    for task in tasks:
        if _stop_requested:
            return "operator_stop"
        now = datetime.now(tz=config.run.reset_at.tzinfo)
        if now >= config.run.hard_stop_at or (run_dir / "STOP_NOW").exists():
            stop_reason = "deadline_guard"
            break
        if now >= drain_at:
            stop_reason = "drain_window"
            break
        task_id = task["id"]
        state["task_status"][task_id] = "running"
        write_json_atomic(run_dir / "RUN_STATE.json", state)
        _event(run_dir / "events.jsonl", "task.started", task_id=task_id)
        # Match the finished_at format below. Mixing the deadline's timezone with the
        # local one puts two spellings of the same instant on adjacent receipt lines.
        started_stamp = now.astimezone().isoformat(timespec="seconds")
        _checkpoint(run_dir / "CHECKPOINTS.md", f"## {started_stamp} · {task_id} · started")
        try:
            result = run_task(config, task, run_dir, entry_script)
        except Exception as exc:
            finished_at = datetime.now().astimezone().isoformat(timespec="seconds")
            result = {
                "task_id": task_id,
                "success": False,
                "return_code": -1,
                "timed_out": False,
                "source_changed": False,
                "source_changed_paths": [],
                "worker_errors": [],
                "billing_error": False,
                "quota_exhausted": False,
                "deadline_stop": (run_dir / "STOP_NOW").exists(),
                "artifact": None,
                "started_at": now.astimezone().isoformat(timespec="seconds"),
                "finished_at": finished_at,
                "guard_ready": False,
                "guard_failed": False,
                "guard_exit_code": None,
                "stop_confirmed": False,
                "stop_result": None,
                "descendant_cleanup_required": False,
                "source_check_completed": False,
                "error_type": type(exc).__name__,
                "error_message": " ".join(str(exc).split())[:300],
            }
        state.setdefault("task_results", {})[task_id] = result
        reported_errors = result.get("worker_errors") or []
        if reported_errors:
            state.setdefault("worker_errors", []).extend(reported_errors)
        if result["success"]:
            state["task_status"][task_id] = "completed"
            state["completed"].append(task_id)
            _event(run_dir / "events.jsonl", "task.completed", task_id=task_id)
            _checkpoint(run_dir / "CHECKPOINTS.md", f"## {result['finished_at']} · {task_id} · completed")
        else:
            state["task_status"][task_id] = "failed"
            state["failed"].append(task_id)
            _event(
                run_dir / "events.jsonl",
                "task.failed",
                task_id=task_id,
                error_type=result.get("error_type"),
            )
            state["source_mutation_detected"] = bool(result["source_changed"])
            state["source_changed_paths"] = list(result.get("source_changed_paths") or [])
            state["billing_error_detected"] = bool(result["billing_error"])
            state["quota_exhausted"] = bool(result.get("quota_exhausted"))
            state["source_check_incomplete"] = not bool(result.get("source_check_completed"))
            state["guard_failure_detected"] = bool(result.get("guard_failed"))
            state["stop_unconfirmed_detected"] = not bool(result.get("stop_confirmed"))
            _checkpoint(run_dir / "CHECKPOINTS.md", f"## {result['finished_at']} · {task_id} · failed\n\n`{result}`")
            if _stop_requested:
                # The operator asked us to stop mid-task. The worker did not fail;
                # mislabelling this as a crash sends the morning reader hunting a bug.
                stop_reason = "operator_stop"
            elif result["billing_error"]:
                stop_reason = "billing_or_auth_error"
            elif result.get("quota_exhausted"):
                # The allowance ran out. That is the window closing, not a fault.
                stop_reason = "quota_exhausted"
            elif result["source_changed"]:
                stop_reason = "source_mutation_detected"
            elif result["deadline_stop"]:
                stop_reason = "deadline_guard"
            elif result["timed_out"]:
                stop_reason = "task_timeout"
            elif result.get("descendant_cleanup_required"):
                stop_reason = "descendant_cleanup_required"
            elif result.get("guard_failed"):
                stop_reason = "guard_failure"
            elif result.get("error_type") == "NoFinalMessage":
                stop_reason = "invalid_worker_output"
            elif result.get("error_type"):
                stop_reason = "worker_exception"
            elif not result.get("stop_confirmed"):
                stop_reason = "stop_unconfirmed"
            else:
                stop_reason = "worker_failed"
            write_json_atomic(run_dir / "RUN_STATE.json", state)
            break
        write_json_atomic(run_dir / "RUN_STATE.json", state)

        if _stop_requested:
            return "operator_stop"
    return stop_reason


def execute_run(config: AppConfig, run_dir: Path, entry_script: Path) -> dict[str, Any]:
    queue = read_json(run_dir / "QUEUE.json")
    validate_frozen_queue(queue)
    state = read_json(run_dir / "RUN_STATE.json")
    if state.get("queue_sha256") != queue.get("tasks_sha256"):
        raise ValueError("run state and frozen queue hash differ")
    if state.get("phase") != "frozen":
        raise ValueError(f"run cannot start from phase {state.get('phase')}")
    if state.get("completed") or state.get("failed"):
        raise ValueError("refusing to resume a partially executed v0.1 run")

    tasks = queue.get("tasks", [])
    state["phase"] = "execute"
    write_json_atomic(run_dir / "RUN_STATE.json", state)
    _event(run_dir / "events.jsonl", "run.started", run_id=state["run_id"])
    stop_reason = "queue_exhausted"
    try:
        stop_reason = _work_queue(config, run_dir, state, tasks, entry_script, stop_reason)
    except StopRequested:
        stop_reason = "operator_stop"

    state["phase"] = "stopped"
    state["stop_reason"] = stop_reason
    state["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json_atomic(run_dir / "RUN_STATE.json", state)
    if not (run_dir / "STOP_REASON").exists():
        write_text_atomic(run_dir / "STOP_REASON", stop_reason + "\n")
    write_morning_report(run_dir, state, queue)
    _event(run_dir / "events.jsonl", "run.stopped", stop_reason=stop_reason)
    return state
