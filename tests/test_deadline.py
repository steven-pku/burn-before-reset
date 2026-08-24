from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from burn_before_reset.deadline import process_group_alive, stop_process_group


class DeadlineTests(unittest.TestCase):
    def test_sigkill_without_observed_stop_is_reported_unconfirmed(self) -> None:
        sent: list[int] = []
        with (
            patch("burn_before_reset.deadline.process_group_alive", return_value=True),
            patch("burn_before_reset.deadline._wait_until_stopped", return_value=False),
        ):
            result = stop_process_group(
                12345,
                sigint_grace=0,
                sigterm_grace=0,
                killpg=lambda _pgid, sig: sent.append(sig),
            )
        self.assertEqual(result, "sigkill-unconfirmed")
        self.assertEqual(sent, [signal.SIGINT, signal.SIGTERM, signal.SIGKILL])

    def test_sigint_permission_error_after_group_exit_is_already_stopped(self) -> None:
        with patch("burn_before_reset.deadline.process_group_alive", side_effect=[True, False]):
            result = stop_process_group(
                12345,
                sigint_grace=0,
                sigterm_grace=0,
                killpg=lambda _pgid, _sig: (_ for _ in ()).throw(PermissionError()),
            )
        self.assertEqual(result, "already-stopped")

    @unittest.skipUnless(hasattr(os, "killpg"), "process groups unavailable")
    def test_guard_stops_spawned_process_group_and_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worker = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "import subprocess,sys,time; "
                    "c=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                    "print(c.pid, flush=True); time.sleep(30)",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
            self.assertIsNotNone(worker.stdout)
            child_pid = int(worker.stdout.readline().strip())
            worker.stdout.close()
            pgid = os.getpgid(worker.pid)
            entry = Path(__file__).resolve().parents[1] / "scripts" / "bbr.py"
            guard = subprocess.Popen(
                [
                    sys.executable,
                    str(entry),
                    "guard",
                    "--pid",
                    str(worker.pid),
                    "--deadline",
                    (datetime.now(UTC) + timedelta(milliseconds=200)).isoformat(),
                    "--stop-marker",
                    str(root / "STOP_NOW"),
                    "--stop-reason",
                    str(root / "STOP_REASON"),
                    "--ready-marker",
                    str(root / "GUARD_READY"),
                    "--sigint-grace",
                    "2.0",
                    "--sigterm-grace",
                    "1.0",
                ],
                start_new_session=True,
            )
            worker.wait(timeout=5)
            guard.wait(timeout=5)
            self.assertEqual(guard.returncode, 0)
            self.assertFalse(process_group_alive(pgid))
            self.assertTrue((root / "STOP_NOW").is_file())
            self.assertTrue((root / "GUARD_READY").is_file())
            self.assertIn("deadline_guard:", (root / "STOP_REASON").read_text(encoding="utf-8"))
            # Both parent and child were in the same process group. A killed
            # child may remain briefly as a zombie, which is stopped work and
            # is deliberately treated as not alive by process_group_alive.
            self.assertGreater(child_pid, 0)


if __name__ == "__main__":
    unittest.main()
