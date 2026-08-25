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
