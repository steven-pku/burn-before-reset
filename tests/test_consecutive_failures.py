from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path

from burn_before_reset.config import load_config
from burn_before_reset.planner import plan_run
from burn_before_reset.runner import execute_run
from burn_before_reset.validation import validate_run

from .helpers import write_config

# A worker that produces no final agent message for its first `fail_first`
# launches, then succeeds. The launch counter lives in a file beside the script
# because every launch is a fresh process; nothing else in the run carries state
# across them.
FAKE_WORKER = '''#!/usr/bin/env python3
import json
import pathlib
import sys

counter = pathlib.Path(__file__).with_name("launches")
seen = int(counter.read_text()) if counter.exists() else 0
counter.write_text(str(seen + 1))
if seen < {fail_first}:
    print(json.dumps({{"type": "turn.completed"}}))
    sys.exit(0)
print(
    json.dumps(
        {{
            "type": "item.completed",
            "item": {{
                "type": "agent_message",
                "text": "# Artifact\\n\\nConfirmed from source reference; validation passed.",
            }},
        }}
    )
)
print(json.dumps({{"type": "turn.completed"}}))
'''


class ConsecutiveFailureTests(unittest.TestCase):
    """One failed task must not end a night the operator authorized.

    On 2026-09-08 a run with 43 completions and zero failures was stopped by its
    44th task timing out, 79 minutes before the hard stop it was allowed to use.
    Steven approved booking such a task failed and continuing, with a bounded
    consecutive-failure count as the real stop condition (DECISIONS.md,
    2026-09-08). Safety failures — billing, source mutation, deadline, guard
    failure, an unconfirmed stop, an incomplete source check — never wait for a
    count; those paths are covered in `test_runner.py`.
    """

    def _worker(self, path: Path, *, fail_first: int) -> Path:
        path.write_text(FAKE_WORKER.format(fail_first=fail_first), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def _run(self, root: Path, *, fail_first: int, limit: int, tasks: int) -> tuple[Path, dict]:
        source = root / "source"
        source.mkdir()
        for index in range(tasks):
            (source / f"work{index}.md").write_text(
                f"# Work {index}\n\nTODO: recover item {index}.\n", encoding="utf-8"
            )
        fake = self._worker(root / "fake-worker", fail_first=fail_first)
        config = load_config(
            write_config(
                root / "config.toml",
                source,
                root / "output",
                enabled=True,
                codex_binary=str(fake),
                max_tasks=tasks,
                max_consecutive_failures=limit,
            )
        )
        run_dir = plan_run(config)
        state = execute_run(config, run_dir, Path(__file__).resolve().parents[1] / "scripts" / "bbr.py")
        return run_dir, state

    def test_one_failure_does_not_end_a_queue_with_work_left(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, state = self._run(Path(temporary), fail_first=1, limit=3, tasks=3)
            self.assertEqual(len(state["failed"]), 1)
            self.assertEqual(len(state["completed"]), 2, "dispatch stopped after the failure")
            self.assertEqual(state["stop_reason"], "queue_exhausted")
            self.assertEqual(state["consecutive_failures"], 0, "a success must clear the count")
            self.assertEqual(validate_run(run_dir), [])

    def test_failures_in_a_row_stop_the_run_at_the_configured_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir, state = self._run(Path(temporary), fail_first=9, limit=2, tasks=3)
            self.assertEqual(len(state["failed"]), 2, "stopped at the limit, not before or after")
            self.assertEqual(state["completed"], [])
            self.assertEqual(state["consecutive_failures"], 2)
            # The threshold is what ended the run, so that is what the ledger says.
            # Naming the last task's own failure would report a single bad task as
            # the cause — the reading this change exists to correct. The per-task
            # cause survives in task_results and in the Morning Report.
            self.assertEqual(state["stop_reason"], "consecutive_failure_limit")
            self.assertEqual(
                state["task_results"][state["failed"][-1]]["error_type"], "NoFinalMessage"
            )
            self.assertEqual(validate_run(run_dir), [])

    def test_a_limit_of_one_keeps_the_first_failure_terminal(self) -> None:
        """The opt-out back to the earlier behaviour still works.

        The stop reason is the threshold's, not the task's — a limit of one is
        still a limit. The task's own cause is in the failed-task list.
        """
        with tempfile.TemporaryDirectory() as temporary:
            _, state = self._run(Path(temporary), fail_first=9, limit=1, tasks=3)
            self.assertEqual(len(state["failed"]), 1)
            self.assertEqual(state["stop_reason"], "consecutive_failure_limit")
            self.assertEqual(
                state["task_results"][state["failed"][0]]["error_type"], "NoFinalMessage"
            )


if __name__ == "__main__":
    unittest.main()
