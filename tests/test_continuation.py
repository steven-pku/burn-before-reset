from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from burn_before_reset.config import load_config
from burn_before_reset.discover import discover_sources, render_proposals
from burn_before_reset.planner import plan_run
from burn_before_reset.runner import execute_run
from burn_before_reset.validation import validate_run

from .helpers import write_config


def _entry_script() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "bbr.py"


def _counting_worker(path: Path, counter: Path, *, limit_hits: int) -> Path:
    """Fails with a rate-limit message `limit_hits` times, then succeeds."""
    path.write_text(
        "#!/bin/sh\n"
        f'C="{counter}"\n'
        'n=$(cat "$C" 2>/dev/null || echo 0); n=$((n+1)); printf %s "$n" > "$C"\n'
        f"if [ $n -le {limit_hits} ]; then\n"
        "  echo 'rate limit reached for this window' >&2\n"
        "  exit 1\n"
        "fi\n"
        "printf '%s\\n' '{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"# Done\\n\\nRecovered; validation passed.\"}}'\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _claude_style_config(path: Path, extra_run: str) -> None:
    text = path.read_text(encoding="utf-8").replace(
        'mode = "safe"', f'mode = "safe"\n{extra_run}', 1
    )
    path.write_text(text, encoding="utf-8")


class QuotaContinuationTests(unittest.TestCase):
    """The goal is to burn the quota to completion; a closed window is a pause, not an end."""

    def _run(self, *, limit_hits: int, wait: bool) -> dict:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            fake = _counting_worker(root / "fake-codex", root / "counter", limit_hits=limit_hits)
            config_path = write_config(root / "config.toml", source, root / "output", enabled=True, codex_binary=str(fake))
            _claude_style_config(
                config_path,
                f"wait_for_replenish = {str(wait).lower()}\nquota_replenish_probe_minutes = 0.005\nreplan_when_queue_empty = false",
            )
            config = load_config(config_path)
            run_dir = plan_run(config)
            state = execute_run(config, run_dir, _entry_script())
            state["_validate"] = validate_run(run_dir)
            return state

    def test_run_rides_across_a_closed_window(self) -> None:
        state = self._run(limit_hits=2, wait=True)
        self.assertEqual(state["stop_reason"], "queue_exhausted")
        self.assertEqual(len(state["completed"]), 1)
        self.assertEqual(state["failed"], [])
        self.assertGreaterEqual(state["quota_wait_cycles"], 2)
        self.assertEqual(state["_validate"], [])

    def test_wait_disabled_keeps_the_old_single_window_behaviour(self) -> None:
        state = self._run(limit_hits=2, wait=False)
        self.assertEqual(state["stop_reason"], "quota_exhausted")
        self.assertEqual(state["completed"], [])
        self.assertEqual(state["quota_wait_cycles"], 0)


class ReplanRoundTests(unittest.TestCase):
    """A drained queue with usable time left re-plans instead of stopping at 3am."""

    def _success_worker(self, path: Path) -> Path:
        path.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' '{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"# Done\\n\\nRecovered; validation passed.\"}}'\n",
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_second_round_picks_up_the_remaining_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "one.md").write_text("# One\n\nTODO: finish one.\n", encoding="utf-8")
            (source / "two.md").write_text("# Two\n\nTODO: finish two.\n", encoding="utf-8")
            fake = self._success_worker(root / "fake-codex")
            config_path = write_config(
                root / "config.toml", source, root / "output", enabled=True, codex_binary=str(fake), max_tasks=1
            )
            config = load_config(config_path)
            run_dir = plan_run(config)
            first_queue = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))
            self.assertEqual(len(first_queue["tasks"]), 1)

            state = execute_run(config, run_dir, _entry_script())
            self.assertEqual(state["stop_reason"], "queue_exhausted")
            self.assertEqual(len(state["completed"]), 2, "the second file was never picked up")
            self.assertEqual(len(state["rounds"]), 2)
            self.assertTrue((run_dir / "QUEUE-r2.json").is_file())
            self.assertEqual(validate_run(run_dir), [])

    def test_a_round_that_finds_nothing_ends_the_run_honestly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "one.md").write_text("# One\n\nTODO: finish one.\n", encoding="utf-8")
            fake = self._success_worker(root / "fake-codex")
            config_path = write_config(
                root / "config.toml", source, root / "output", enabled=True, codex_binary=str(fake), max_tasks=1
            )
            config = load_config(config_path)
            run_dir = plan_run(config)
            state = execute_run(config, run_dir, _entry_script())
            self.assertEqual(state["stop_reason"], "queue_exhausted")
            self.assertEqual(len(state["completed"]), 1)
            self.assertEqual(len(state["rounds"]), 1, "no filler round should be invented")
            self.assertFalse((run_dir / "QUEUE-r2.json").exists())
            self.assertEqual(validate_run(run_dir), [])


class DiscoverTests(unittest.TestCase):
    """Finding work must not assume a note vault: session logs come first."""

    def test_session_logs_and_recent_work_trees_are_proposed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            sessions = home / ".claude" / "projects" / "p1"
            sessions.mkdir(parents=True)
            (sessions / "a.jsonl").write_text("{}\n", encoding="utf-8")
            repo = home / "Documents" / "myrepo"
            (repo / ".git").mkdir(parents=True)
            for index in range(6):
                (repo / f"note{index}.md").write_text(f"# {index}\n", encoding="utf-8")

            proposals = discover_sources(home)
            types = {proposal.source_type for proposal in proposals}
            self.assertIn("claude_sessions", types)
            self.assertIn("git", types)
            rendered = render_proposals(proposals)
            self.assertIn(str(home / ".claude" / "projects"), rendered)
            self.assertIn(str(repo), rendered)
            self.assertIn("[[sources]]", rendered)

    def test_secretish_directories_are_never_proposed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            secret = home / "Documents" / ".ssh"
            secret.mkdir(parents=True)
            for index in range(6):
                (secret / f"note{index}.md").write_text("x", encoding="utf-8")
            proposals = discover_sources(home)
            self.assertEqual([p for p in proposals if "ssh" in str(p.root)], [])


class MissingWorkerBinaryTests(unittest.TestCase):
    """The first real CI run failed because tests assumed codex was installed."""

    def test_missing_worker_binary_fails_preflight_with_a_clear_error(self) -> None:
        from burn_before_reset.config import ConfigError, assert_execution_environment

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# W\n\nTODO: x.\n", encoding="utf-8")
            config = load_config(
                write_config(
                    root / "config.toml", source, root / "output", enabled=True,
                    codex_binary="definitely-not-a-real-binary-7f3a",
                )
            )
            with self.assertRaises(ConfigError) as caught:
                assert_execution_environment(config, {})
            self.assertIn("not found on PATH", str(caught.exception))


class DiscoverCliTests(unittest.TestCase):
    def test_discover_command_prints_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            sessions = home / ".claude" / "projects" / "p1"
            sessions.mkdir(parents=True)
            (sessions / "a.jsonl").write_text("{}\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(_entry_script()), "discover", "--home", str(home)],
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("claude_sessions", result.stdout)


if __name__ == "__main__":
    unittest.main()


class AuditFixTests(unittest.TestCase):
    """Regressions for the 2026-08-26 external audit (sol + Grok) findings."""

    def test_stop_requested_is_not_swallowed_as_a_task_failure(self) -> None:
        # A signal arriving inside run_task's window must unwind, not become a
        # fake worker crash booked into failed[].
        from unittest.mock import patch

        from burn_before_reset.runner import StopRequested, _work_queue

        self.assertFalse(issubclass(StopRequested, Exception))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# W\n\nTODO: x.\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output", enabled=True))
            run_dir = plan_run(config)
            task = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"][0]
            state = json.loads((run_dir / "RUN_STATE.json").read_text(encoding="utf-8"))
            with (
                patch("burn_before_reset.runner.run_task", side_effect=StopRequested("signal 15")),
                self.assertRaises(StopRequested),
            ):
                _work_queue(config, run_dir, state, [task], _entry_script(), "queue_exhausted")
            self.assertEqual(state["failed"], [], "a stop signal was booked as a task failure")

    def test_retry_clears_stale_handshake_markers(self) -> None:
        # Stale GUARD_READY/START_WORKER from a previous attempt let the launcher
        # exec before the new guard is ready. By the moment the worker process is
        # spawned, both markers from the prior attempt must already be gone.
        import subprocess as subprocess_module
        from unittest.mock import patch

        from burn_before_reset.worker import run_task

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# W\n\nTODO: x.\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output", enabled=True))
            run_dir = plan_run(config)
            task = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"][0]
            worker_dir = run_dir / "workers" / task["id"]
            worker_dir.mkdir(parents=True, exist_ok=True)
            stale_ready = worker_dir / "GUARD_READY"
            stale_start = worker_dir / "START_WORKER"
            stale_ready.write_text("stale\n", encoding="utf-8")
            stale_start.write_text("stale\n", encoding="utf-8")

            observed: dict[str, bool] = {}

            class _Abort(RuntimeError):
                pass

            real_popen = subprocess_module.Popen

            def probe(*args, **kwargs):
                command = args[0] if args else kwargs.get("args", [])
                if "worker-launch" not in command:
                    # git init etc. — let it through untouched.
                    return real_popen(*args, **kwargs)
                observed["ready_gone"] = not stale_ready.exists()
                observed["start_gone"] = not stale_start.exists()
                raise _Abort("probe complete — no process is actually spawned")

            with (
                patch("burn_before_reset.worker.subprocess.Popen", side_effect=probe),
                self.assertRaises(_Abort),
            ):
                run_task(config, task, run_dir, _entry_script())

            self.assertTrue(
                observed.get("ready_gone") and observed.get("start_gone"),
                f"stale handshake markers survived to worker launch: {observed}",
            )

    def test_claude_worker_cwd_is_pinned_to_staging(self) -> None:
        # Read/Grep are unprompted in the worker's cwd; inheriting the supervisor's
        # cwd would silently widen the read surface to wherever bbr was launched.
        from burn_before_reset.worker import run_task

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# W\n\nTODO: x.\n", encoding="utf-8")
            fake = Path(root / "fake-claude")
            fake.write_text(
                "#!/bin/sh\n"
                f'pwd > "{root}/worker-cwd.txt"\n'
                "printf '%s' '{\"subtype\":\"success\",\"is_error\":false,\"result\":\"# Done\"}'\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            config_path = write_config(root / "config.toml", source, root / "output", enabled=True)
            text = config_path.read_text(encoding="utf-8").replace(
                "[execution]\nenabled = true",
                f'[execution]\nenabled = true\nprovider = "claude"\nclaude_binary = "{fake}"',
            )
            config_path.write_text(text, encoding="utf-8")
            config = load_config(config_path)
            run_dir = plan_run(config)
            task = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"][0]
            result = run_task(config, task, run_dir, _entry_script())
            self.assertTrue(result["success"], result)
            recorded = Path(root / "worker-cwd.txt").read_text(encoding="utf-8").strip()
            staging = (run_dir / "staging" / task["id"]).resolve()
            self.assertEqual(Path(recorded).resolve(), staging, "worker cwd is not the staging dir")

    def test_permission_denial_fails_the_task(self) -> None:
        # A worker that reached for an ungranted tool stayed safe only because the
        # boundary held; its output must not be promoted as a success.
        from burn_before_reset.worker import run_task

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# W\n\nTODO: x.\n", encoding="utf-8")
            fake = Path(root / "fake-claude")
            fake.write_text(
                "#!/bin/sh\n"
                "printf '%s' '{\"subtype\":\"success\",\"is_error\":false,\"result\":\"# Done\","
                "\"permission_denials\":[{\"tool_name\":\"Write\"}]}'\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            config_path = write_config(root / "config.toml", source, root / "output", enabled=True)
            text = config_path.read_text(encoding="utf-8").replace(
                "[execution]\nenabled = true",
                f'[execution]\nenabled = true\nprovider = "claude"\nclaude_binary = "{fake}"',
            )
            config_path.write_text(text, encoding="utf-8")
            config = load_config(config_path)
            run_dir = plan_run(config)
            task = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"][0]
            result = run_task(config, task, run_dir, _entry_script())
            self.assertFalse(result["success"], "denied tool attempt was promoted to success")
            self.assertEqual(result["error_type"], "PermissionDenied")
            self.assertIsNone(result["artifact"])

    def test_validate_run_rejects_phantom_inflight_and_bad_round_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# W\n\nTODO: x.\n", encoding="utf-8")
            fake = Path(root / "fake-codex")
            fake.write_text(
                "#!/bin/sh\nprintf '%s\\n' "
                "'{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"# Done\"}}'\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            config = load_config(
                write_config(root / "config.toml", source, root / "output", enabled=True, codex_binary=str(fake))
            )
            run_dir = plan_run(config)
            execute_run(config, run_dir, _entry_script())
            self.assertEqual(validate_run(run_dir), [])

            state_path = run_dir / "RUN_STATE.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            good = json.dumps(state)

            task_id = next(iter(state["task_status"]))
            state["task_status"][task_id] = "waiting_quota"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            self.assertTrue(any("non-terminal" in e for e in validate_run(run_dir)))

            state = json.loads(good)
            state["rounds"][0]["tasks_sha256"] = "0" * 64
            state_path.write_text(json.dumps(state), encoding="utf-8")
            self.assertTrue(any("round ledger hash" in e for e in validate_run(run_dir)))


class BurnLedgerTests(unittest.TestCase):
    """The provider's allowance is unreadable; what was spent is the only progress measure."""

    def test_claude_cost_and_tokens_are_accumulated(self) -> None:
        from burn_before_reset.worker import _burn_from_events

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "subtype": "success",
                        "is_error": False,
                        "result": "x",
                        "total_cost_usd": 0.25,
                        "usage": {"input_tokens": 10, "output_tokens": 500, "cache_read_input_tokens": 900},
                    }
                ),
                encoding="utf-8",
            )
            burn = _burn_from_events(path, "claude")
            self.assertAlmostEqual(burn["cost_usd"], 0.25)
            self.assertEqual(burn["output_tokens"], 500)
            self.assertEqual(burn["cached_input_tokens"], 900)

    def test_codex_reports_tokens_without_inventing_a_price(self) -> None:
        from burn_before_reset.worker import _burn_from_events

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            path.write_text(
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 20, "output_tokens": 7}}) + "\n",
                encoding="utf-8",
            )
            burn = _burn_from_events(path, "codex")
            self.assertIsNone(burn["cost_usd"], "a price must never be invented for a provider that reports none")
            self.assertEqual(burn["output_tokens"], 7)

    def test_run_reports_spend_and_unused_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            fake = Path(root / "fake-codex")
            fake.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' '{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"# Done\"}}'\n"
                "printf '%s\\n' '{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":11,\"output_tokens\":22}}'\n",
                encoding="utf-8",
            )
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            config = load_config(
                write_config(root / "config.toml", source, root / "output", enabled=True, codex_binary=str(fake))
            )
            run_dir = plan_run(config)
            state = execute_run(config, run_dir, _entry_script())
            self.assertEqual(state["burn"]["output_tokens"], 22)
            self.assertIn("hours_remaining", state["burn_pace"])
            report = (run_dir / "MORNING_REPORT.md").read_text(encoding="utf-8")
            self.assertIn("## Burn", report)
            # The window closed with hours unused: that is unconverted quota and
            # the report must say so rather than presenting it as a clean finish.
            self.assertIn("left unused", report)
            self.assertIn("Was this worth the quota?", report)

    def test_burn_command_reads_a_finished_run(self) -> None:
        from burn_before_reset.burn import burn_report

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify.\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output"))
            run_dir = plan_run(config)
            text = burn_report(run_dir)
            self.assertIn(run_dir.name, text)
            self.assertIn("remaining", text)
            self.assertIn("nothing has been dispatched yet", text)

    def test_run_plan_records_why_each_task_was_picked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify.\nblocked: waiting.\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output"))
            run_dir = plan_run(config)
            plan = (run_dir / "RUN_PLAN.md").read_text(encoding="utf-8")
            # A bad pick has to be traceable to the input that caused it.
            self.assertIn("Picked because", plan)
            self.assertIn("recency", plan)
