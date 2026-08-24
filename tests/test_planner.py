from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from burn_before_reset.config import load_config
from burn_before_reset.planner import plan_run
from burn_before_reset.state import read_json, validate_frozen_queue
from burn_before_reset.validation import validate_run

from .helpers import write_config


class PlannerTests(unittest.TestCase):
    def test_plan_builds_traceable_frozen_queue_without_source_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            note = source / "project.md"
            original = "# Project Alpha\n\nTODO: run the missing validation and record the next step.\n"
            note.write_text(original, encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output"))
            run_dir = plan_run(config)
            queue = read_json(run_dir / "QUEUE.json")
            validate_frozen_queue(queue)
            self.assertEqual(len(queue["tasks"]), 1)
            self.assertEqual(queue["tasks"][0]["source_refs"][0]["path"], "project.md")
            self.assertEqual(note.read_text(encoding="utf-8"), original)
            self.assertEqual(validate_run(run_dir), [])

    def test_empty_queue_is_a_valid_stop_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "done.md").write_text("# Done\n\nNo open work.\n", encoding="utf-8")
            config = load_config(write_config(root / "config.toml", source, root / "output"))
            run_dir = plan_run(config)
            self.assertEqual(read_json(run_dir / "QUEUE.json")["tasks"], [])
            self.assertIn("No eligible task", (run_dir / "RUN_PLAN.md").read_text(encoding="utf-8"))

    def test_invalid_codex_jsonl_is_not_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sessions"
            source.mkdir()
            (source / "bad.jsonl").write_text('{"type":"other"}\nTODO: fake\n', encoding="utf-8")
            config = load_config(
                write_config(root / "config.toml", source, root / "output", source_type="codex_sessions")
            )
            run_dir = plan_run(config)
            self.assertEqual(read_json(run_dir / "QUEUE.json")["tasks"], [])


if __name__ == "__main__":
    unittest.main()
