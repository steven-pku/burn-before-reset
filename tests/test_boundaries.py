from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from burn_before_reset.config import ConfigError, assert_execution_environment, load_config
from burn_before_reset.indexer import index_source
from burn_before_reset.planner import plan_run
from burn_before_reset.runner import execute_run
from burn_before_reset.validation import validate_run
from burn_before_reset.worker import (
    _diagnostic_scan,
    _snapshot_diff,
    _tree_snapshot,
    _worker_environment,
    run_task,
)

from .helpers import write_config


def _events(path: Path, records: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


class DiagnosticScanTests(unittest.TestCase):
    """The Worker's own answer is the deliverable, never a failure signal."""

    def test_agent_message_is_excluded_from_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = _events(
                Path(temporary) / "events.jsonl",
                [
                    {"type": "thread.started", "thread_id": "t"},
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": "The notes discuss billing, rate limit handling, and credit balance policy.",
                        },
                    },
                    {"type": "turn.completed"},
                ],
            )
            diagnostics, errors = _diagnostic_scan(path)
            self.assertNotIn("billing", diagnostics.lower())
            self.assertNotIn("rate limit", diagnostics.lower())
            self.assertEqual(errors, [])

    def test_error_item_is_captured_as_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = _events(
                Path(temporary) / "events.jsonl",
                [
                    {
                        "type": "item.completed",
                        "item": {"type": "error", "message": "usage limit reached for this account"},
                    }
                ],
            )
            diagnostics, errors = _diagnostic_scan(path)
            self.assertIn("usage limit", diagnostics.lower())
            self.assertEqual(len(errors), 1)

    def test_unparsable_line_is_kept(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            path.write_text("authentication failed\n", encoding="utf-8")
            diagnostics, _ = _diagnostic_scan(path)
            self.assertIn("authentication failed", diagnostics)


class ArtifactDiscussingBillingTests(unittest.TestCase):
    """An artifact that merely talks about pricing must still be delivered."""

    def _fake_codex(self, path: Path) -> Path:
        message = (
            "# Recovered artifact\\n\\nConfirmed from source reference; validation passed. "
            "The note compares API billing against the paid credits model and mentions rate limit behaviour."
        )
        path.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' '{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\""
            + message
            + "\"}}'\n"
            "printf '%s\\n' '{\"type\":\"turn.completed\"}'\n",
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_billing_vocabulary_in_the_deliverable_does_not_fail_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            fake = self._fake_codex(root / "fake-codex")
            config = load_config(
                write_config(root / "config.toml", source, root / "output", enabled=True, codex_binary=str(fake))
            )
            assert_execution_environment(config, {})
            run_dir = plan_run(config)
            state = execute_run(config, run_dir, Path(__file__).resolve().parents[1] / "scripts" / "bbr.py")
            self.assertFalse(state["billing_error_detected"])
            self.assertEqual(state["stop_reason"], "queue_exhausted")
            self.assertEqual(len(state["completed"]), 1)


class SnapshotScopeTests(unittest.TestCase):
    """Background writes outside the allowlist are not source mutations."""

    def _config(self, root: Path):
        source = root / "source"
        source.mkdir()
        (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
        return load_config(write_config(root / "config.toml", source, root / "output")), source

    def test_unindexed_file_does_not_register_as_a_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, source = self._config(root)
            settings = config.sources[0]
            before = {str(source): _tree_snapshot(source, settings)}
            (source / ".DS_Store").write_bytes(b"\x00finder noise")
            (source / "notes.pages").write_text("not an indexed extension", encoding="utf-8")
            after = {str(source): _tree_snapshot(source, settings)}
            self.assertEqual(_snapshot_diff(before, after), [])

    def test_indexed_file_change_is_named_in_the_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, source = self._config(root)
            settings = config.sources[0]
            before = {str(source): _tree_snapshot(source, settings)}
            (source / "work.md").write_text("# Work\n\nTODO: verify this. Edited.\n", encoding="utf-8")
            after = {str(source): _tree_snapshot(source, settings)}
            diff = _snapshot_diff(before, after)
            self.assertEqual(len(diff), 1)
            self.assertTrue(diff[0].endswith("work.md"))


class GitReadOnlyTests(unittest.TestCase):
    """Indexing a Git source must not write inside that source."""

    def test_index_source_leaves_git_index_mtime_alone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "repo"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True, timeout=10)
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            env = {
                **os.environ,
                "GIT_AUTHOR_NAME": "t",
                "GIT_AUTHOR_EMAIL": "t@example.invalid",
                "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.invalid",
            }
            subprocess.run(["git", "-C", str(source), "add", "-A"], check=True, timeout=10)
            subprocess.run(["git", "-C", str(source), "commit", "-qm", "init"], check=True, timeout=10, env=env)
            (source / "work.md").write_text("# Work\n\nTODO: verify this again.\n", encoding="utf-8")

            git_index = source / ".git" / "index"
            os.utime(git_index, (1_000_000_000, 1_000_000_000))
            before = git_index.stat().st_mtime_ns

            config = load_config(
                write_config(root / "config.toml", source, root / "output", source_type="git")
            )
            index_source(config.sources[0])

            self.assertEqual(git_index.stat().st_mtime_ns, before)


class WorkerEnvironmentTests(unittest.TestCase):
    """Endpoint overrides and keys never reach the Worker process."""

    def test_endpoint_and_key_variables_are_dropped(self) -> None:
        environment, dropped = _worker_environment(
            {
                "PATH": "/usr/bin",
                "HOME": "/home/example",
                "HTTPS_PROXY": "http://127.0.0.1:7890",
                "OPENAI_API_KEY": "sk-example",
                "OPENAI_BASE_URL": "http://127.0.0.1:10100/v1",
                "ANTHROPIC_BASE_URL": "http://127.0.0.1:10100",
                "SOME_SERVICE_API_KEY": "x",
            }
        )
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("OPENAI_BASE_URL", environment)
        self.assertNotIn("ANTHROPIC_BASE_URL", environment)
        self.assertNotIn("SOME_SERVICE_API_KEY", environment)
        self.assertEqual(environment["PATH"], "/usr/bin")
        self.assertEqual(environment["HOME"], "/home/example")
        # A proxy changes the network route, not the billed account.
        self.assertEqual(environment["HTTPS_PROXY"], "http://127.0.0.1:7890")
        self.assertIn("OPENAI_BASE_URL", dropped)


class WorkerStdinTests(unittest.TestCase):
    """An unattended Worker must never inherit a stdin it could block on."""

    def test_worker_is_launched_with_devnull_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            config = load_config(
                write_config(root / "config.toml", source, root / "output", enabled=True, codex_binary="true")
            )
            run_dir = plan_run(config)
            task = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"][0]

            recorded: list[dict] = []
            real_popen = subprocess.Popen

            def capture(*args, **kwargs):
                recorded.append(kwargs)
                return real_popen(*args, **kwargs)

            with patch("burn_before_reset.worker.subprocess.Popen", side_effect=capture):
                run_task(config, task, run_dir, Path(__file__).resolve().parents[1] / "scripts" / "bbr.py")

            # Only the Worker and its guard are launched into their own session;
            # the staging `git init` shares this process group and is not a risk.
            launched = [kwargs for kwargs in recorded if kwargs.get("start_new_session")]
            self.assertEqual(len(launched), 2, "expected the Worker and its deadline guard")
            for kwargs in launched:
                self.assertIs(kwargs.get("stdin"), subprocess.DEVNULL)


class RunDirectoryPermissionTests(unittest.TestCase):
    """Run directories hold excerpts of the user's own notes."""

    def test_run_directory_is_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output"))
            run_dir = plan_run(config)
            self.assertEqual(stat.S_IMODE(run_dir.stat().st_mode), 0o700)


class ReceiptLegibilityTests(unittest.TestCase):
    """Receipts are read by a human the next morning."""

    def test_checkpoint_timestamps_share_one_offset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            config = load_config(
                write_config(root / "config.toml", source, root / "output", enabled=True, codex_binary="true")
            )
            run_dir = plan_run(config)
            execute_run(config, run_dir, Path(__file__).resolve().parents[1] / "scripts" / "bbr.py")

            stamps = [
                line.split(" · ")[0].removeprefix("## ").strip()
                for line in (run_dir / "CHECKPOINTS.md").read_text(encoding="utf-8").splitlines()
                if line.startswith("## ")
            ]
            self.assertTrue(stamps, "no checkpoints were written")
            offsets = {datetime.fromisoformat(stamp).utcoffset() for stamp in stamps}
            self.assertEqual(
                len(offsets),
                1,
                f"checkpoints mix timezones, so one instant reads as several: {stamps}",
            )


class SkillDiscoveryTests(unittest.TestCase):
    """Both discovery paths must keep resolving, and they fail silently when they break."""

    def test_agent_and_claude_skill_links_resolve_to_the_repository_skill(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        canonical = (repo / "SKILL.md").resolve()
        for link in (
            repo / ".agents" / "skills" / "burn-before-reset" / "SKILL.md",
            repo / ".claude" / "skills" / "burn-before-reset" / "SKILL.md",
        ):
            with self.subTest(link=str(link.relative_to(repo))):
                self.assertTrue(link.is_file(), f"{link} does not resolve")
                self.assertEqual(link.resolve(), canonical)


class ShippedSchemaTests(unittest.TestCase):
    """The published contracts must keep describing what the code emits."""

    def _schema(self, name: str) -> dict:
        path = Path(__file__).resolve().parents[1] / "schemas" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_task_spec_schema_matches_planner_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output"))
            run_dir = plan_run(config)
            task = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"][0]
            schema = self._schema("task-spec.schema.json")
            self.assertEqual(set(task), set(schema["properties"]))
            self.assertTrue(set(schema["required"]).issubset(set(task)))

    def test_run_state_schema_covers_emitted_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output"))
            run_dir = plan_run(config)
            state = json.loads((run_dir / "RUN_STATE.json").read_text(encoding="utf-8"))
            schema = self._schema("run-state.schema.json")
            self.assertTrue(set(schema["required"]).issubset(set(state)))
            undeclared = set(state) - set(schema["properties"])
            self.assertEqual(undeclared, set(), f"run state emits undeclared fields: {undeclared}")

    def test_task_result_schema_covers_emitted_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
            config = load_config(
                write_config(root / "config.toml", source, root / "output", enabled=True, codex_binary="true")
            )
            run_dir = plan_run(config)
            task = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"][0]
            result = run_task(config, task, run_dir, Path(__file__).resolve().parents[1] / "scripts" / "bbr.py")
            schema = self._schema("task-result.schema.json")
            self.assertTrue(set(schema["required"]).issubset(set(result)))
            undeclared = set(result) - set(schema["properties"])
            self.assertEqual(undeclared, set(), f"task result emits undeclared fields: {undeclared}")


if __name__ == "__main__":
    unittest.main()


class ScoringTests(unittest.TestCase):
    """A score that does not vary with the source does not rank anything."""

    def _record(self, path: str, *, days_old: float, signals: tuple[str, ...], snippets: int) -> object:
        from burn_before_reset.model import SourceRef

        modified = datetime.now().astimezone() - timedelta(days=days_old)
        return SourceRef(
            source_type="markdown",
            root="/src",
            path=path,
            modified_at=modified.isoformat(timespec="seconds"),
            title=f"Title for {path}",
            signals=signals,
            snippets=tuple("x" * 60 for _ in range(snippets)),
        )

    def test_scores_spread_across_varied_records(self) -> None:
        from burn_before_reset.planner import _task_from_record

        now = datetime.now().astimezone()
        records = [
            self._record("a/one.md", days_old=1, signals=("decision", "blocked", "todo"), snippets=5),
            self._record("a/two.md", days_old=10, signals=("blocked",), snippets=3),
            self._record("b/three.md", days_old=90, signals=("todo",), snippets=1),
            self._record("b/README.md", days_old=400, signals=("todo",), snippets=1),
            self._record("c/five.md", days_old=2, signals=("unverified",), snippets=2),
            self._record("c/six.md", days_old=200, signals=("fixme", "next-step"), snippets=4),
        ]
        scores = {_task_from_record(r, Path("/run"), now).score for r in records}
        self.assertGreaterEqual(
            len(scores), 5, f"scoring barely discriminates, so the queue is arbitrary: {sorted(scores)}"
        )

    def test_recency_outranks_an_older_but_otherwise_identical_record(self) -> None:
        from burn_before_reset.planner import _task_from_record

        now = datetime.now().astimezone()
        fresh = _task_from_record(self._record("a/x.md", days_old=1, signals=("todo",), snippets=2), Path("/run"), now)
        stale = _task_from_record(self._record("a/y.md", days_old=500, signals=("todo",), snippets=2), Path("/run"), now)
        self.assertGreater(fresh.score, stale.score)


class QueueDiversityTests(unittest.TestCase):
    """One recently-touched project must not monopolise the window."""

    def test_queue_spreads_across_projects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            for project in ("alpha", "beta", "gamma"):
                folder = source / project
                folder.mkdir(parents=True)
                for index in range(6):
                    (folder / f"note{index}.md").write_text(
                        f"# {project} note {index}\n\nTODO: finish this.\nblocked: waiting.\n",
                        encoding="utf-8",
                    )
            # alpha looks freshest, which is exactly what sweeps a straight top-N.
            for index in range(6):
                os.utime(source / "alpha" / f"note{index}.md", None)

            config = load_config(write_config(root / "config.toml", source, root / "output"))
            config = replace(config, execution=replace(config.execution, max_tasks=6))
            run_dir = plan_run(config)
            queue = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))
            projects = {PurePosixPath(t["source_refs"][0]["path"]).parts[0] for t in queue["tasks"]}
            self.assertEqual(
                projects,
                {"alpha", "beta", "gamma"},
                f"queue collapsed onto a subset of projects: {sorted(projects)}",
            )


class ClaudeWorkerTests(unittest.TestCase):
    """The Claude worker's read-only guarantee is that write tools are absent."""

    def _config(self, root: Path, **overrides):
        source = root / "source"
        source.mkdir()
        (source / "work.md").write_text("# Work\n\nTODO: verify this.\n", encoding="utf-8")
        path = write_config(root / "config.toml", source, root / "output", enabled=True)
        text = path.read_text(encoding="utf-8").replace(
            '[execution]\nenabled = true', '[execution]\nenabled = true\nprovider = "claude"'
        )
        path.write_text(text, encoding="utf-8")
        return load_config(path), source

    def test_command_withholds_customisations_and_every_write_tool(self) -> None:
        from burn_before_reset.worker import _worker_command

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, source = self._config(root)
            command = _worker_command(config, "prompt", root / "staging", [source])
            joined = " ".join(command)
            # --safe-mode drops CLAUDE.md, skills, plugins, hooks and MCP servers.
            # A probe without it reached a cloud-storage create_file tool.
            self.assertIn("--safe-mode", command)
            self.assertIn("--strict-mcp-config", command)
            self.assertIn('{"mcpServers":{}}', command)
            self.assertIn("--tools", command)
            tools = command[command.index("--tools") + 1]
            for writer in ("Write", "Edit", "Bash", "WebFetch", "Task"):
                self.assertNotIn(writer, tools)
            self.assertNotIn("--dangerously-skip-permissions", joined)
            self.assertNotIn("bypassPermissions", joined)

    def test_balanced_mode_is_refused_for_the_claude_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "work.md").write_text("# Work\n\nTODO: verify.\n", encoding="utf-8")
            path = write_config(root / "config.toml", source, root / "output", enabled=True, mode="balanced")
            text = path.read_text(encoding="utf-8").replace(
                '[execution]\nenabled = true', '[execution]\nenabled = true\nprovider = "claude"'
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_failed_or_denied_runs_yield_no_artifact(self) -> None:
        from burn_before_reset.worker import _claude_diagnostics, _claude_extract

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"

            path.write_text(json.dumps({"subtype": "success", "is_error": False, "result": "content"}), encoding="utf-8")
            self.assertEqual(_claude_extract(path).strip(), "content")

            path.write_text(
                json.dumps({"subtype": "error_during_execution", "is_error": True, "result": "half an answer"}),
                encoding="utf-8",
            )
            self.assertEqual(_claude_extract(path), "")
            _, errors = _claude_diagnostics(path)
            self.assertTrue(errors)

    def test_denied_tool_is_reported_not_swallowed(self) -> None:
        from burn_before_reset.worker import _claude_diagnostics

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "subtype": "success",
                        "is_error": False,
                        "result": "fine",
                        "permission_denials": [{"tool_name": "mcp__cloud__create_file"}],
                    }
                ),
                encoding="utf-8",
            )
            diagnostics, errors = _claude_diagnostics(path)
            self.assertIn("mcp__cloud__create_file", diagnostics)
            self.assertTrue(any("not granted" in e for e in errors))

    def test_the_deliverable_is_never_scanned_for_billing_words(self) -> None:
        from burn_before_reset.worker import _claude_diagnostics, _contains_billing_error

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            path.write_text(
                json.dumps(
                    {"subtype": "success", "is_error": False, "result": "The note compares billing and rate limit policy."}
                ),
                encoding="utf-8",
            )
            diagnostics, _ = _claude_diagnostics(path)
            self.assertFalse(_contains_billing_error(diagnostics))


class QuotaExhaustionTests(unittest.TestCase):
    """Running out of allowance is the window closing, not a billing fault."""

    def test_structured_and_prose_spellings_are_both_caught(self) -> None:
        from burn_before_reset.worker import _contains_billing_error, _contains_quota_exhaustion

        # Claude reports a structured snake_case stop_reason; Codex reports prose.
        for text in ("stop_reason=usage_limit", "You've reached your usage limit", "rate_limit", "rate limit"):
            with self.subTest(text=text):
                self.assertTrue(_contains_quota_exhaustion(text))
                self.assertFalse(
                    _contains_billing_error(text),
                    "exhausting an allowance must not be reported as a billing fault",
                )

    def test_real_billing_terms_still_fail_closed(self) -> None:
        from burn_before_reset.worker import _contains_billing_error

        for text in ("auto top-up enabled", "credit balance low", "authentication failed"):
            with self.subTest(text=text):
                self.assertTrue(_contains_billing_error(text))

    def test_exhausted_run_stops_with_its_own_reason(self) -> None:
        from burn_before_reset.worker import _claude_diagnostics, _contains_quota_exhaustion

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "events.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "subtype": "error_during_execution",
                        "is_error": True,
                        "stop_reason": "usage_limit",
                        "result": "You've reached your usage limit.",
                    }
                ),
                encoding="utf-8",
            )
            diagnostics, errors = _claude_diagnostics(path)
            self.assertTrue(_contains_quota_exhaustion(diagnostics))
            self.assertTrue(errors)


class SupervisorSurvivalTests(unittest.TestCase):
    """A supervisor that dies mid-run leaves an unreadable, unresumable run."""

    def _slow_worker(self, path: Path) -> Path:
        path.write_text(
            "#!/bin/sh\nsleep 30\nprintf '%s\\n' "
            "'{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"# Done\"}}'\n",
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def test_sigterm_finalises_the_run_and_leaves_no_orphans(self) -> None:
        import signal as signal_module

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            for index in range(3):
                (source / f"d{index}.md").write_text(
                    f"# Doc {index}\n\nTODO: item {index}.\nblocked: waiting.\n", encoding="utf-8"
                )
            fake = self._slow_worker(root / "fake-codex")
            config_path = write_config(
                root / "config.toml", source, root / "output", enabled=True, codex_binary=str(fake)
            )
            repo = Path(__file__).resolve().parents[1]
            supervisor = subprocess.Popen(
                [sys.executable, str(repo / "scripts" / "bbr.py"), "run", "--config", str(config_path), "--execute"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env={**os.environ, "PYTHONPATH": str(repo / "src")},
            )
            try:
                deadline = time.monotonic() + 30
                run_dirs: list[Path] = []
                while time.monotonic() < deadline:
                    run_dirs = sorted((root / "output").glob("run-*"))
                    if run_dirs and (run_dirs[0] / "workers").exists():
                        children = list((run_dirs[0] / "workers").iterdir())
                        if children:
                            break
                    time.sleep(0.2)
                self.assertTrue(run_dirs, "the run never started")
                run_dir = run_dirs[0]

                supervisor.send_signal(signal_module.SIGTERM)
                supervisor.wait(timeout=60)
            finally:
                if supervisor.poll() is None:
                    supervisor.kill()
                    supervisor.wait(timeout=10)

            state = json.loads((run_dir / "RUN_STATE.json").read_text(encoding="utf-8"))
            self.assertEqual(state["phase"], "stopped", "the run was left mid-flight with no finalisation")
            self.assertEqual(state["stop_reason"], "operator_stop")
            self.assertTrue((run_dir / "MORNING_REPORT.md").is_file())
            self.assertTrue((run_dir / "STOP_REASON").is_file())
            self.assertEqual(validate_run(run_dir), [])

    def test_sighup_is_ignored_by_the_supervisor(self) -> None:
        import signal as signal_module

        from burn_before_reset.runner import install_supervisor_signals

        previous = signal_module.getsignal(signal_module.SIGHUP)
        try:
            install_supervisor_signals()
            # An overnight run must survive the session that launched it ending.
            self.assertEqual(signal_module.getsignal(signal_module.SIGHUP), signal_module.SIG_IGN)
        finally:
            signal_module.signal(signal_module.SIGHUP, previous)
