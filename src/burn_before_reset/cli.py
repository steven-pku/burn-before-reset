from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .burn import burn_report
from .config import ConfigError, assert_execution_environment, load_config
from .deadline import guard_process
from .discover import discover_sources, render_proposals
from .paths import audit_exclusions
from .planner import plan_run
from .report_html import generate_report
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
    choice = run.add_mutually_exclusive_group(required=True)
    choice.add_argument("--run-dir", type=Path, help="execute only this reviewed frozen queue")
    choice.add_argument("--autopilot", action="store_true", help="authorize initial planning and follow-up rounds")
    run.add_argument("--execute", action="store_true")

    validate = subparsers.add_parser("validate-run")
    validate.add_argument("--run-dir", required=True, type=Path)

    burn = subparsers.add_parser("burn")
    burn.add_argument("--run-dir", type=Path)
    burn.add_argument("--output-root", type=Path)

    report = subparsers.add_parser("report")
    report.add_argument("--run-dir", required=True, type=Path)
    report.add_argument("--language", default="auto")

    discover = subparsers.add_parser("discover")
    discover.add_argument("--home", type=Path, default=None)

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


def _exclusion_audit(config) -> list[dict[str, object]]:
    """Per source root, what each `exclude_fragments` entry actually catches.

    An exclusion that matches nothing looks exactly like one that is working. On
    2026-09-08 an entry added specifically to keep a directory out of the night
    was inert, `validate-config` reported the configuration clean, and the run
    read the directory anyway. Counting the matches here is what makes an inert
    safety control visible before the window opens.
    """
    rows: list[dict[str, object]] = []
    for source in config.sources:
        audit = audit_exclusions(source.root, source.exclude_fragments)
        rows.append(
            {
                "root": str(source.root),
                "type": source.source_type,
                "matches": {
                    fragment: len(audit.matches.get(fragment, [])) for fragment in source.exclude_fragments
                },
                # A truncated walk cannot tell an inert entry from an unreached one,
                # so it reports neither rather than a confident empty list.
                "matching_nothing": [] if audit.truncated else [
                    fragment for fragment in source.exclude_fragments if not audit.matches.get(fragment)
                ],
                "walk_truncated": audit.truncated,
            }
        )
    return rows


def _summary(config_path: Path) -> dict[str, object]:
    config = load_config(config_path)
    exclusions = _exclusion_audit(config)
    return {
        "valid": True,
        "reset_at": config.run.reset_at.isoformat(),
        "hard_stop_at": config.run.hard_stop_at.isoformat(),
        "mode": config.run.mode,
        "sources": len(config.sources),
        "execution_enabled": config.execution.enabled,
        "exclusions": exclusions,
    }


def _warn_inert_exclusions(summary: dict[str, object]) -> None:
    """Say it in the terminal too; a count buried in JSON is easy to read past."""
    for row in summary.get("exclusions") or []:
        for fragment in row.get("matching_nothing") or []:
            print(
                f"warning: exclude_fragments entry {fragment!r} matches nothing under {row['root']}; "
                "entries are matched as a substring of the path relative to the source root",
                file=sys.stderr,
            )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-config":
            summary = _summary(args.config)
            print(json.dumps(summary, indent=2))
            _warn_inert_exclusions(summary)
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
            state = execute_run(config, run_dir, entry_script, autopilot=args.autopilot)
            print(json.dumps({"run_dir": str(run_dir), "stop_reason": state["stop_reason"]}, indent=2))
            return 0 if state.get("stop_reason") == "queue_exhausted" and not state.get("failed") else 1
        if args.command == "burn":
            print(burn_report(args.run_dir, args.output_root), end="")
            return 0
        if args.command == "report":
            print(generate_report(args.run_dir.resolve(), args.language))
            return 0
        if args.command == "discover":
            print(render_proposals(discover_sources(args.home)), end="")
            return 0
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
            # argparse float accepts "inf" and "nan"; a non-finite grace makes the
            # SIGINT→SIGTERM→SIGKILL ladder lose its bounded-stop guarantee.
            for label, value in (("--sigint-grace", args.sigint_grace), ("--sigterm-grace", args.sigterm_grace)):
                if not math.isfinite(value) or value < 0:
                    raise ConfigError(f"guard {label} must be a finite non-negative number")
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
