from __future__ import annotations

import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from burn_before_reset.config import load_config
from burn_before_reset.planner import plan_run
from burn_before_reset.runner import StopRequested
from burn_before_reset.state import read_json
from burn_before_reset.worker import _stop_group, _terminate_process, run_task

from .helpers import HERMETIC_BINARY, write_config


class StartupStopTests(unittest.TestCase):
    def test_operator_stop_during_guard_handshake_reaps_both_processes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source'
            source.mkdir()
            (source / 'work.md').write_text('TODO: recover unfinished work\n')
            config = load_config(write_config(root / 'config.toml', source, root / 'output',
                                              enabled=True, codex_binary=HERMETIC_BINARY))
            run_dir = plan_run(config)
            task = read_json(run_dir / 'QUEUE.json')['tasks'][0]
            launched = []
            real_popen = subprocess.Popen
            real_sleep = time.sleep
            real_exists = Path.exists
            interrupted = False

            def capture(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                if len(args[0]) > 2 and args[0][2] in {'worker-launch', 'guard'}:
                    launched.append(process)
                return process

            def handshake_exists(path):
                return False if path.name == 'GUARD_READY' else real_exists(path)

            def stop_on_handshake(seconds):
                nonlocal interrupted
                if not interrupted and len(launched) == 2:
                    interrupted = True
                    raise StopRequested('deterministic handshake interrupt')
                real_sleep(seconds)

            try:
                with patch('burn_before_reset.worker.subprocess.Popen', side_effect=capture), \
                     patch('burn_before_reset.worker.Path.exists', handshake_exists), \
                     patch('burn_before_reset.worker.time.sleep', side_effect=stop_on_handshake), \
                     self.assertRaises(StopRequested):
                    run_task(config, task, run_dir, Path(__file__).resolve().parents[1] / 'scripts/bbr.py')
                self.assertEqual(len(launched), 2)
                self.assertTrue(all(process.poll() is not None for process in launched),
                                'operator stop left the launcher or guard alive')
            finally:
                # The regression must also clean up when exercised against the old bug.
                if launched:
                    _stop_group(launched[0].pid, config)
                for process in launched:
                    _terminate_process(process)
                    process.wait(timeout=5)
