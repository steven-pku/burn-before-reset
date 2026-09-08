from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from burn_before_reset.config import load_config
from burn_before_reset.planner import plan_run
from burn_before_reset.state import read_json

from .helpers import write_config


def _flattened(path: Path) -> str:
    """How a CLI turns a working directory into one session-directory name.

    Written out here rather than imported so the regression tests the observed
    on-disk shape (`-Users-me-runs-run-1-staging-task-2`) instead of testing the
    production helper against itself.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _claude_transcript(cwd: str) -> str:
    return (
        json.dumps({"type": "user", "sessionId": "s-1", "cwd": cwd})
        + "\nTODO: the unverified claim in this transcript still needs checking\n"
    )


def _codex_transcript(cwd: str) -> str:
    return (
        json.dumps({"type": "session_meta", "payload": {"session_id": "s-1", "cwd": cwd}})
        + "\nTODO: the unverified claim in this transcript still needs checking\n"
    )


class SelfReferenceTests(unittest.TestCase):
    """The planner must never queue work against this tool's own worker transcripts.

    On 2026-09-08 a re-planning round selected a round-2 worker transcript of the
    run it was part of, ran the full task timeout against it and stopped the run
    79 minutes early. Seven further tasks that night completed and passed every
    validation gate against the same exhaust. The guard has to hold by
    construction, not by an operator remembering to write an exclusion.
    """

    def test_claude_worker_transcript_of_another_run_is_not_queued(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sessions"
            source.mkdir()
            config = load_config(
                write_config(
                    root / "config.toml",
                    source,
                    root / "output",
                    source_type="claude_sessions",
                    exclude_fragments=(".git",),
                )
            )
            output_root = config.run.output_root
            # A *different* run in the same output root: the second-run case, which
            # no current-run exclusion can cover.
            exhaust_cwd = output_root / "run-20260101-000000-aaaaaaaa" / "staging" / "task-bbbbbbbbbbbb"
            exhaust = source / _flattened(exhaust_cwd)
            exhaust.mkdir()
            (exhaust / "worker.jsonl").write_text(_claude_transcript(str(exhaust_cwd)), encoding="utf-8")
            genuine_cwd = Path("/Users/someone/Documents/Projects/Alpha")
            genuine = source / _flattened(genuine_cwd)
            genuine.mkdir()
            (genuine / "session.jsonl").write_text(_claude_transcript(str(genuine_cwd)), encoding="utf-8")

            run_dir = plan_run(config)
            queued = read_json(run_dir / "QUEUE.json")["tasks"]
            paths = [task["source_refs"][0]["path"] for task in queued]
            self.assertEqual(paths, [f"{genuine.name}/session.jsonl"])
            plan = (run_dir / "RUN_PLAN.md").read_text(encoding="utf-8")
            self.assertIn("own output", plan)
            self.assertIn(exhaust.name, plan)

    def test_codex_worker_transcript_is_not_queued(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sessions"
            source.mkdir()
            config = load_config(
                write_config(
                    root / "config.toml",
                    source,
                    root / "output",
                    source_type="codex_sessions",
                    exclude_fragments=(".git",),
                )
            )
            exhaust_cwd = config.run.output_root / "run-20260101-000000-aaaaaaaa" / "staging" / "task-cccccccccccc"
            (source / "exhaust.jsonl").write_text(_codex_transcript(str(exhaust_cwd)), encoding="utf-8")
            (source / "genuine.jsonl").write_text(
                _codex_transcript("/Users/someone/Documents/Projects/Alpha"), encoding="utf-8"
            )

            run_dir = plan_run(config)
            queued = read_json(run_dir / "QUEUE.json")["tasks"]
            paths = [task["source_refs"][0]["path"] for task in queued]
            self.assertEqual(paths, ["genuine.jsonl"])

    def test_a_neighbour_directory_sharing_a_name_prefix_is_still_indexed(self) -> None:
        """`.../output` must not swallow `.../outputs`: the marker needs a separator.

        The flattening is lossy — `/a/b/c` and `/a/b-c` collapse to the same name —
        so a neighbour whose own name *extends* the output root with a separator
        cannot be told apart and is excluded. Requiring the separator is the
        tightest rule the encoding actually supports.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sessions"
            source.mkdir()
            config = load_config(
                write_config(
                    root / "config.toml",
                    source,
                    root / "output",
                    source_type="claude_sessions",
                    exclude_fragments=(".git",),
                )
            )
            neighbour_cwd = config.run.output_root.with_name(config.run.output_root.name + "s")
            neighbour = source / _flattened(neighbour_cwd)
            neighbour.mkdir()
            (neighbour / "session.jsonl").write_text(_claude_transcript(str(neighbour_cwd)), encoding="utf-8")

            run_dir = plan_run(config)
            queued = read_json(run_dir / "QUEUE.json")["tasks"]
            self.assertEqual(len(queued), 1)


if __name__ == "__main__":
    unittest.main()
