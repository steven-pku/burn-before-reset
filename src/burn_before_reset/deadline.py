from __future__ import annotations

import errno
import os
import signal
import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .paths import ExecutableError, resolve_executable
from .state import write_text_atomic


def _ps_group_alive(pgid: int) -> bool | None:
    """Return live/non-zombie group state, or None when ps is unavailable."""
    try:
        result = subprocess.run(
            [resolve_executable("ps"), "-eo", "pgid=,stat="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError, ExecutableError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        fields = line.split(None, 1)
        if len(fields) != 2:
            continue
        try:
            group = int(fields[0])
        except ValueError:
            continue
        if group != pgid:
            continue
        if not fields[1].lstrip().startswith("Z"):
            return True
    return False


def process_group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        observed = _ps_group_alive(pgid)
        return True if observed is None else observed
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        raise
    # A terminated process may remain as a zombie until its parent reaps it.
    # killpg(..., 0) still sees that process group, but there is no executable
    # work left to stop. Prefer a process-table check when available.
    observed = _ps_group_alive(pgid)
    return True if observed is None else observed


def _wait_until_stopped(pgid: int, seconds: float, sleeper: Callable[[float], None] = time.sleep) -> bool:
    deadline = time.monotonic() + seconds
    while process_group_alive(pgid) and time.monotonic() < deadline:
        sleeper(min(0.1, max(0.0, deadline - time.monotonic())))
    return not process_group_alive(pgid)


def stop_process_group(
    pgid: int,
    *,
    sigint_grace: float,
    sigterm_grace: float,
    killpg: Callable[[int, int], None] = os.killpg,
) -> str:
    if not process_group_alive(pgid):
        return "already-stopped"
    try:
        killpg(pgid, signal.SIGINT)
    except ProcessLookupError:
        return "already-stopped"
    except PermissionError:
        if not process_group_alive(pgid):
            return "already-stopped"
        raise
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return "already-stopped"
        raise
    if _wait_until_stopped(pgid, sigint_grace):
        return "sigint"
    try:
        killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return "sigint"
    except PermissionError:
        if not process_group_alive(pgid):
            return "sigint"
        raise
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return "sigint"
        raise
    if _wait_until_stopped(pgid, sigterm_grace):
        return "sigterm"
    try:
        killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return "sigterm"
    except PermissionError:
        if not process_group_alive(pgid):
            return "sigterm"
        raise
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return "sigterm"
        raise
    return "sigkill" if _wait_until_stopped(pgid, 2.0) else "sigkill-unconfirmed"


def guard_process(
    pid: int,
    deadline: datetime,
    stop_marker: Path,
    stop_reason: Path,
    ready_marker: Path | None = None,
    *,
    sigint_grace: float,
    sigterm_grace: float,
) -> int:
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return 0
    if ready_marker is not None:
        write_text_atomic(ready_marker, f"guard ready for pgid {pgid}\n")
    while True:
        if not process_group_alive(pgid):
            return 0
        remaining = (deadline - datetime.now(tz=deadline.tzinfo)).total_seconds()
        if remaining <= 0:
            break
        time.sleep(min(0.5, remaining))
    write_text_atomic(stop_marker, f"deadline reached at {datetime.now().astimezone().isoformat()}\n")
    result = stop_process_group(
        pgid,
        sigint_grace=sigint_grace,
        sigterm_grace=sigterm_grace,
    )
    write_text_atomic(stop_reason, f"deadline_guard:{result}\n")
    return 0 if result != "sigkill-unconfirmed" else 3
