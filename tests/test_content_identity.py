"""v0.3.1 polish round (2026-09-02): content identity in de-duplication, a Claude
transcript filter, and a score floor that can actually fire.

Run against the tree before this round, the load-bearing cases go red; the pairing is
recorded in VALIDATION.md.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from burn_before_reset.config import load_config
from burn_before_reset.indexer import index_source
from burn_before_reset.model import TaskSpec
from burn_before_reset.planner import plan_run

from .helpers import write_config


def _complete(run_dir: Path) -> str:
    """Book the first queued task as completed with a real artifact, as a finished run would."""
    task = json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"][0]
    state = json.loads((run_dir / "RUN_STATE.json").read_text(encoding="utf-8"))
    state["completed"] = [task["id"]]
    (run_dir / "RUN_STATE.json").write_text(json.dumps(state), encoding="utf-8")
    artifact = run_dir / task["deliverables"][0]
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("# Answered\n\nEvidence.\n", encoding="utf-8")
    return task["id"]


def _reused(run_dir: Path) -> int:
    return int(json.loads((run_dir / "RUN_STATE.json").read_text(encoding="utf-8"))["reused_from_prior_runs"])


def _queued_ids(run_dir: Path) -> list[str]:
    return [task["id"] for task in json.loads((run_dir / "QUEUE.json").read_text(encoding="utf-8"))["tasks"]]


class ContentIdentityTests(unittest.TestCase):
    """A25 follow-up · answered stays answered until the *content* moves."""

    def _fixture(self, root: Path):
        source = root / "source"
        source.mkdir()
        note = source / "work.md"
        note.write_text("# Work\n\nTODO: verify the export path.\n", encoding="utf-8")
        config = load_config(write_config(root / "config.toml", source, root / "output"))
        return note, config

    def test_touch_only_is_not_movement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note, config = self._fixture(root)
            first = plan_run(config)
            task_id = _complete(first)
            # cp -p, tar -x, a checkout: the stamp moved, the bytes did not.
            later = time.time() + 7200
            os.utime(note, (later, later))
            second = plan_run(config)
            self.assertEqual(_reused(second), 1, "a touched file is not new work")
            self.assertNotIn(task_id, _queued_ids(second))

    def test_same_stamp_edit_is_movement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            note, config = self._fixture(root)
            first = plan_run(config)
            task_id = _complete(first)
            stamp = note.stat()
            # Same markers, so the same task id; new content the earlier answer never saw.
            note.write_text("# Work\n\nTODO: verify the export path.\nIt moved to /srv/new.\n", encoding="utf-8")
            # A same-second edit, or one whose stamp was restored afterwards.
            os.utime(note, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            second = plan_run(config)
            self.assertEqual(_reused(second), 0, "changed bytes under an unchanged stamp are still movement")
            self.assertIn(task_id, _queued_ids(second))

    def test_ledger_without_digest_falls_back_to_the_stamp(self) -> None:
        # A run written before digests existed still gates on an unchanged stamp.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, config = self._fixture(root)
            first = plan_run(config)
            task_id = _complete(first)
            queue_path = first / "QUEUE.json"
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            for ref in queue["tasks"][0]["source_refs"]:
                ref.pop("content_sha256", None)
            queue_path.write_text(json.dumps(queue), encoding="utf-8")
            second = plan_run(config)
            self.assertEqual(_reused(second), 1)
            self.assertNotIn(task_id, _queued_ids(second))


class ClaudeTranscriptFilterTests(unittest.TestCase):
    """`claude_sessions` accepts the transcript shape only, as `codex_sessions` already did."""

    def test_only_session_shaped_jsonl_is_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "projects"
            source.mkdir()
            transcript = {
                "type": "user",
                "sessionId": "s-1",
                "cwd": "/srv/p",
                "message": {"role": "user", "content": "TODO: verify the export path before release"},
            }
            (source / "session.jsonl").write_text(json.dumps(transcript) + "\n", encoding="utf-8")
            export = {"id": 1, "note": "TODO: verify the export path before release"}
            (source / "export.jsonl").write_text(json.dumps(export) + "\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output", source_type="claude_sessions"))
            paths = {record.path for record in index_source(config.sources[0])}
            self.assertIn("session.jsonl", paths)
            self.assertNotIn("export.jsonl", paths, "a data export that ends in .jsonl is not a session")


class ScoreFloorTests(unittest.TestCase):
    """`minimum_score` must sit inside the range the formula can produce, or it is a dead knob."""

    def _spec(self, **dims: int) -> TaskSpec:
        base = dict(
            strategic_value=1, reuse=3, readiness=1, verifiability=3, recency=0,
            checkpointability=5, token_fitness=2, risk=0, human_dependency=0,
        )
        base.update(dims)
        return TaskSpec(
            id="task-x", title="t", objective="o", source_refs=({"path": "a.md"},),
            deliverables=("artifacts/task-x.md",), allowed_read_roots=("/srv",),
            allowed_write_root="/srv/run", validation=("v",), **base,
        )

    def test_default_floor_sits_inside_the_reachable_range(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            path = write_config(root / "config.toml", source, root / "output")
            path.write_text(path.read_text(encoding="utf-8").replace("minimum_score = 12\n", ""), encoding="utf-8")
            default = load_config(path).task_policy.minimum_score
        weakest = self._spec().score  # stale, one weak marker, sprawling snippets
        self.assertEqual(weakest, 24)
        fresh = self._spec(recency=5).score  # the same marker, touched this week
        self.assertLess(weakest, default, "a floor below the weakest possible candidate filters nothing")
        self.assertLessEqual(default, fresh, "a fresh marker must survive the default floor")


if __name__ == "__main__":
    unittest.main()
