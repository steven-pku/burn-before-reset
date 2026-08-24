from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .config import ConfigError, assert_execution_environment, load_config
from .deadline import guard_process
from .planner import plan_run
from .runner import execute_run, install_supervisor_signals
from .validation import validate_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bbr", description="Burn Before Reset local runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("validate-config", "plan"):
        command = subparsers.add_parser(name)
        command.add_argument("--config", required=True, type=Path)

    run = subparsers.add_parser("run")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--run-dir", type=Path)
    run.add_argument("--execute", action="store_true")

    validate = subparsers.add_parser("validate-run")
    validate.add_argument("--run-dir", required=True, type=Path)

    guard = subparsers.add_parser("guard")
    guard.add_argument("--pid", required=True, type=int)
    guard.add_argument("--deadline", required=True)
    guard.add_argument("--stop-marker", required=True, type=Path)
    guard.add_argument("--stop-reason", required=True, type=Path)
    guard.add_argument("--ready-marker", type=Path)
    guard.add_argument("--sigint-grace", required=True, type=float)
    guard.add_argument("--sigterm-grace", required=True, type=float)

    launcher = subparsers.add_parser("worker-launch")
    launcher.add_argument("--start-marker", required=True, type=Path)
    launcher.add_argument("worker_command", nargs=argparse.REMAINDER)
    return parser


def _summary(config_path: Path) -> dict[str, object]:
    config = load_config(config_path)
    return {
        "valid": True,
        "reset_at": config.run.reset_at.isoformat(),
        "hard_stop_at": config.run.hard_stop_at.isoformat(),
        "mode": config.run.mode,
        "sources": len(config.sources),
        "execution_enabled": config.execution.enabled,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-config":
            print(json.dumps(_summary(args.config), indent=2))
            return 0
        if args.command == "plan":
            config = load_config(args.config)
            run_dir = plan_run(config)
            print(run_dir)
            return 0
        if args.command == "run":
            if not args.execute:
                raise ConfigError("run requires the explicit --execute flag")
            config = load_config(args.config)
            assert_execution_environment(config)
            if args.run_dir:
                run_dir = args.run_dir.resolve()
                if not run_dir.is_dir():
                    raise ConfigError("run directory must exist")
                if not run_dir.is_relative_to(config.run.output_root):
                    raise ConfigError("run directory must be inside run.output_root")
            else:
                run_dir = plan_run(config)
            entry_script = Path(sys.argv[0]).resolve()
            # From here the process supervises an unattended run; keep it alive through
            # a closing session and make any stop finalise the receipts.
            install_supervisor_signals()
            state = execute_run(config, run_dir, entry_script)
            print(json.dumps({"run_dir": str(run_dir), "stop_reason": state["stop_reason"]}, indent=2))
            return 0 if state.get("stop_reason") == "queue_exhausted" and not state.get("failed") else 1
        if args.command == "validate-run":
            errors = validate_run(args.run_dir.resolve())
            if errors:
                print(json.dumps({"valid": False, "errors": errors}, indent=2))
                return 1
            print(json.dumps({"valid": True, "run_dir": str(args.run_dir.resolve())}, indent=2))
            return 0
        if args.command == "guard":
            deadline = datetime.fromisoformat(args.deadline.replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                raise ConfigError("guard deadline must include timezone")
            return guard_process(
                args.pid,
                deadline,
                args.stop_marker,
                args.stop_reason,
                args.ready_marker,
                sigint_grace=args.sigint_grace,
                sigterm_grace=args.sigterm_grace,
            )
        if args.command == "worker-launch":
            command = list(args.worker_command)
            if command and command[0] == "--":
                command = command[1:]
            if not command:
                raise ConfigError("worker-launch requires a command after --")
            deadline = time.monotonic() + 30
            while not args.start_marker.exists():
                if time.monotonic() >= deadline:
                    raise ConfigError("worker start marker was not created")
                time.sleep(0.05)
            os.execvpe(command[0], command, os.environ)
    except (ConfigError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"bbr: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
