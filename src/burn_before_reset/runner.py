from __future__ import annotations

import json
import signal
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import AppConfig
from .planner import plan_followup_round
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


def _failure_stop_reason(result: dict[str, Any]) -> str:
    if _stop_requested:
        # The operator asked us to stop mid-task. The worker did not fail;
        # mislabelling this as a crash sends the morning reader hunting a bug.
        return "operator_stop"
    if result["billing_error"]:
        return "billing_or_auth_error"
    if result.get("quota_exhausted"):
        # The allowance ran out. That is the window closing, not a fault.
        return "quota_exhausted"
    if result["source_changed"]:
        return "source_mutation_detected"
    if result["deadline_stop"]:
        return "deadline_guard"
    if result["timed_out"]:
        return "task_timeout"
    if result.get("descendant_cleanup_required"):
        return "descendant_cleanup_required"
    if result.get("guard_failed"):
        return "guard_failure"
    if result.get("error_type") == "NoFinalMessage":
        return "invalid_worker_output"
    if result.get("error_type"):
        return "worker_exception"
    if not result.get("stop_confirmed"):
        return "stop_unconfirmed"
    return "worker_failed"


def _wait_for_replenishment(config: AppConfig, run_dir: Path, state: dict[str, Any], task_id: str) -> bool:
    """Sleep one probe interval, bounded by the hard stop. True = worth retrying.

    Subscription allowances replenish on an inner cycle whose exact boundary the
    tool cannot read, so there is no clock to sleep until. Probing is the honest
    mechanism: sleep, retry the same task, and let a still-exhausted allowance
    fail closed again at near-zero cost. The outer `reset_at` stays an immovable
    ceiling — the wait never crosses the hard stop.
    """
    state["quota_wait_cycles"] = int(state.get("quota_wait_cycles", 0)) + 1
    write_json_atomic(run_dir / "RUN_STATE.json", state)
    _event(
        run_dir / "events.jsonl",
        "quota.waiting",
        task_id=task_id,
        wait_cycle=state["quota_wait_cycles"],
        probe_minutes=config.run.quota_replenish_probe_minutes,
    )
    _checkpoint(
        run_dir / "CHECKPOINTS.md",
        f"## {datetime.now().astimezone().isoformat(timespec='seconds')} · {task_id} · "
        f"quota exhausted — waiting for replenishment (cycle {state['quota_wait_cycles']})",
    )
    deadline = time.monotonic() + config.run.quota_replenish_probe_minutes * 60
    while time.monotonic() < deadline:
        if _stop_requested:
            return False
        now = datetime.now(tz=config.run.reset_at.tzinfo)
        if now >= config.run.hard_stop_at:
            return False
        time.sleep(min(5.0, max(0.05, deadline - time.monotonic())))
    return not _stop_requested


def _work_queue(
    config: AppConfig,
    run_dir: Path,
    state: dict[str, Any],
    tasks: list[dict[str, Any]],
    entry_script: Path,
    stop_reason: str,
) -> str:
    """Dispatch one frozen queue. Returns the reason dispatch ended."""
    drain_at = config.run.reset_at - timedelta(minutes=config.run.drain_window_minutes)
    for task in tasks:
        if _stop_requested:
            return "operator_stop"
        task_id = task["id"]
        while True:
            now = datetime.now(tz=config.run.reset_at.tzinfo)
            if now >= config.run.hard_stop_at or (run_dir / "STOP_NOW").exists():
                return "deadline_guard"
            if now >= drain_at:
                return "drain_window"
            state["task_status"][task_id] = "running"
            write_json_atomic(run_dir / "RUN_STATE.json", state)
            _event(run_dir / "events.jsonl", "task.started", task_id=task_id)
            # Match the finished_at format below. Mixing the deadline's timezone with
            # the local one puts two spellings of one instant on adjacent receipt lines.
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
                write_json_atomic(run_dir / "RUN_STATE.json", state)
                break  # next task

            if (
                result.get("quota_exhausted")
                and config.run.wait_for_replenish
                and not _stop_requested
                and not result["billing_error"]
                and not result["source_changed"]
            ):
                # The window closed mid-run. This is not a failure of the task, so it
                # is not booked as one: the task goes back to queued, the supervisor
                # sleeps one probe interval, and the same task is retried. A retry
                # against a still-closed window fails closed again at near-zero cost.
                state["task_status"][task_id] = "waiting_quota"
                if _wait_for_replenishment(config, run_dir, state, task_id):
                    continue  # retry the same task
                state["task_status"][task_id] = "failed"
                state["failed"].append(task_id)
                write_json_atomic(run_dir / "RUN_STATE.json", state)
                return "operator_stop" if _stop_requested else "quota_exhausted"

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
            write_json_atomic(run_dir / "RUN_STATE.json", state)
            return _failure_stop_reason(result)

        if _stop_requested:
            return "operator_stop"
    return stop_reason


def _time_for_another_round(config: AppConfig) -> bool:
    now = datetime.now(tz=config.run.reset_at.tzinfo)
    drain_at = config.run.reset_at - timedelta(minutes=config.run.drain_window_minutes)
    return (drain_at - now).total_seconds() > config.execution.task_timeout_seconds


def execute_run(config: AppConfig, run_dir: Path, entry_script: Path) -> dict[str, Any]:
    queue = read_json(run_dir / "QUEUE.json")
    validate_frozen_queue(queue)
    state = read_json(run_dir / "RUN_STATE.json")
    if state.get("queue_sha256") != queue.get("tasks_sha256"):
        raise ValueError("run state and frozen queue hash differ")
    if state.get("phase") != "frozen":
        raise ValueError(f"run cannot start from phase {state.get('phase')}")
    if state.get("completed") or state.get("failed"):
        raise ValueError("refusing to resume a partially executed run")

    all_tasks: list[dict[str, Any]] = list(queue.get("tasks", []))
    state["phase"] = "execute"
    write_json_atomic(run_dir / "RUN_STATE.json", state)
    _event(run_dir / "events.jsonl", "run.started", run_id=state["run_id"])
    stop_reason = "queue_exhausted"
    try:
        stop_reason = _work_queue(config, run_dir, state, list(queue.get("tasks", [])), entry_script, stop_reason)
        # Burn to completion: a drained queue with usable time left is not the end
        # of the night. Re-plan against the sources as they are now; a round that
        # finds nothing new ends the run honestly — no filler tasks are invented.
        while (
            stop_reason == "queue_exhausted"
            and config.run.replan_when_queue_empty
            and not _stop_requested
            and _time_for_another_round(config)
        ):
            round_index = len(state.get("rounds", [])) + 1
            planned = plan_followup_round(
                config,
                run_dir,
                round_index,
                exclude_ids=frozenset(state.get("task_status", {})),
            )
            if planned is None:
                _event(run_dir / "events.jsonl", "round.nothing_left", round_index=round_index)
                break
            queue_name, tasks_sha, new_tasks = planned
            state.setdefault("rounds", []).append({"queue": queue_name, "tasks_sha256": tasks_sha})
            for task in new_tasks:
                state["task_status"][task["id"]] = "queued"
            all_tasks.extend(new_tasks)
            write_json_atomic(run_dir / "RUN_STATE.json", state)
            _event(run_dir / "events.jsonl", "round.planned", round_index=round_index, tasks=len(new_tasks))
            stop_reason = _work_queue(config, run_dir, state, new_tasks, entry_script, stop_reason)
    except StopRequested:
        stop_reason = "operator_stop"

    state["phase"] = "stopped"
    state["stop_reason"] = stop_reason
    state["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json_atomic(run_dir / "RUN_STATE.json", state)
    if not (run_dir / "STOP_REASON").exists():
        write_text_atomic(run_dir / "STOP_REASON", stop_reason + "\n")
    write_morning_report(run_dir, state, {"tasks": all_tasks})
    _event(run_dir / "events.jsonl", "run.stopped", stop_reason=stop_reason)
    return state
