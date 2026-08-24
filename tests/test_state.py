from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from burn_before_reset.state import (
    content_hash,
    freeze_queue,
    read_json,
    validate_frozen_queue,
    write_json_atomic,
)


class StateTests(unittest.TestCase):
    def _task(self, task_id: str = "task-a", deliverable: str = "artifacts/task-a.md") -> dict[str, object]:
        return {"id": task_id, "deliverables": [deliverable]}

    def test_queue_is_immutable_and_hash_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "QUEUE.json"
            queue = freeze_queue(path, [self._task()], "2026-08-24T00:00:00+00:00")
            validate_frozen_queue(queue)
            with self.assertRaises(FileExistsError):
                freeze_queue(path, [], "2026-08-24T00:00:01+00:00")
            tampered = read_json(path)
            tampered["tasks"].append(self._task("task-b", "artifacts/task-b.md"))
            write_json_atomic(path, tampered)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                validate_frozen_queue(read_json(path))

    def test_rehashed_queue_still_rejects_path_escape(self) -> None:
        task = self._task("../escape", "../../outside.md")
        queue = {
            "frozen": True,
            "tasks": [task],
            "tasks_sha256": content_hash([task]),
        }
        with self.assertRaisesRegex(ValueError, "unsafe path"):
            validate_frozen_queue(queue)


if __name__ == "__main__":
    unittest.main()
