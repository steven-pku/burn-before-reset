from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _latest_run(output_root: Path | None) -> Path | None:
    root = output_root or Path.home() / "burn-before-reset-runs"
    if not root.is_dir():
        return None
    runs = sorted((p for p in root.glob("run-*") if p.is_dir()), key=lambda p: p.name)
    return runs[-1] if runs else None


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def burn_report(run_dir: Path | None = None, output_root: Path | None = None) -> str:
    """Read-only progress check on a run, safe to call while it is still going.

    The provider's remaining allowance cannot be read from here, so progress is
    measured by what has been spent against how much of the window is left. A run
    that is far under its own pace with hours remaining is failing at its one job,
    and that has to be visible before the window closes, not in the morning.
    """
    target = run_dir or _latest_run(output_root)
    if target is None or not target.is_dir():
        return "No run found. Pass --run-dir, or --output-root if runs live outside ~/burn-before-reset-runs.\n"
    state = _read(target / "RUN_STATE.json")
    if not state:
        return f"{target.name}: RUN_STATE.json unreadable.\n"

    burn = state.get("burn") or {}
    spent = float(burn.get("cost_usd", 0.0) or 0.0)
    priced = int(burn.get("cost_known_calls", 0))
    calls = int(state.get("worker_calls", 0))
    out_tokens = int(burn.get("output_tokens", 0))
    phase = state.get("phase", "?")
    done, failed = len(state.get("completed", [])), len(state.get("failed", []))

    lines = [
        f"{target.name}  ·  phase {phase}"
        + (f"  ·  stopped: {state.get('stop_reason')}" if phase == "stopped" else "  ·  running"),
        f"  tasks       {done} done, {failed} failed, {calls} worker calls, {len(state.get('rounds', []))} round(s)",
        f"  waits       {int(state.get('quota_wait_cycles', 0))} quota replenishment wait(s)",
        f"  burned      {f'${spent:.4f}' if priced else 'not priced by this provider'}, "
        f"{out_tokens:,} output tokens",
    ]

    try:
        hard_stop = datetime.fromisoformat(str(state.get("hard_stop_at")))
        started = datetime.fromisoformat(str(state.get("created_at")))
        now = datetime.now(tz=hard_stop.tzinfo)
        elapsed_h = max((now - started).total_seconds() / 3600, 1e-6)
        left_h = (hard_stop - now).total_seconds() / 3600
        rate = spent / elapsed_h
        lines.append(f"  elapsed     {elapsed_h:.2f}h   remaining {max(left_h, 0):.2f}h to hard stop")
        if priced:
            lines.append(f"  rate        ${rate:.3f}/h  →  projected ${spent + rate * max(left_h, 0):.2f} by hard stop")
        if phase != "stopped" and left_h > 0.5 and calls == 0:
            lines.append("  ⚠  nothing has been dispatched yet — check the queue is not empty")
    except (TypeError, ValueError):
        pass

    return "\n".join(lines) + "\n"
