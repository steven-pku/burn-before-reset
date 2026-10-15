from __future__ import annotations

import stat
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from burn_before_reset.config import load_config
from burn_before_reset.planner import plan_run
from burn_before_reset.runner import execute_run
from burn_before_reset.state import read_json

from .helpers import write_config

ENTRY = Path(__file__).resolve().parents[1] / 'scripts/bbr.py'


class QuotaSafetyTests(unittest.TestCase):
    def _plan(self, root, binary=sys.executable):
        source = root / 'source'
        source.mkdir()
        (source / 'todo.md').write_text('TODO: recover unfinished work\n')
        config = load_config(write_config(root / 'config.toml', source, root / 'output',
                                          enabled=True, codex_binary=str(binary)))
        config = replace(config, run=replace(config.run, wait_for_replenish=True),
                         execution=replace(config.execution, max_worker_calls_per_run=1))
        run_dir = plan_run(config)
        task = read_json(run_dir / 'QUEUE.json')['tasks'][0]
        stamp = datetime.now(UTC).isoformat()
        result = dict(task_id=task['id'], success=False, return_code=1, timed_out=False,
                      source_changed=False, source_write_attributable=False, source_changed_paths=[],
                      billing_error=False, quota_exhausted=True, deadline_stop=False,
                      stop_confirmed=True, source_check_completed=True, guard_failed=False,
                      descendant_cleanup_required=False, error_type=None,
                      started_at=stamp, finished_at=stamp, artifact=None)
        return config, run_dir, result

    def test_quota_never_retries_an_unsafe_result(self):
        cases = (
            ('stop_confirmed', False, 'stop_unconfirmed_detected'),
            ('source_check_completed', False, 'source_check_incomplete'),
            ('descendant_cleanup_required', True, None),
            ('guard_failed', True, 'guard_failure_detected'),
            ('source_write_attributable', True, 'source_mutation_detected'),
            ('billing_error', True, 'billing_error_detected'),
        )
        for key, value, state_flag in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                config, run_dir, result = self._plan(Path(temporary))
                result[key] = value
                with patch('burn_before_reset.runner.run_task', return_value=result) as worker, \
                     patch('burn_before_reset.runner._wait_for_replenishment', return_value=True) as wait:
                    state = execute_run(config, run_dir, ENTRY)
                wait.assert_not_called()
                self.assertEqual(worker.call_count, 1)
                self.assertEqual(len(state['failed']), 1)
                self.assertNotEqual(state['stop_reason'], 'quota_exhausted')
                self.assertNotEqual(state['stop_reason'], 'worker_call_cap')
                if state_flag:
                    self.assertTrue(state[state_flag])

    def test_cut_short_clean_quota_wait_records_the_quota_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            config, run_dir, result = self._plan(Path(temporary))
            with patch('burn_before_reset.runner.run_task', return_value=result), \
                 patch('burn_before_reset.runner._wait_for_replenishment', return_value=False) as wait:
                state = execute_run(config, run_dir, ENTRY)
            wait.assert_called_once()
            self.assertEqual(state['stop_reason'], 'quota_exhausted')
            self.assertTrue(state['quota_exhausted'])
            self.assertEqual(len(state['failed']), 1)

    def test_real_quota_worker_leaving_a_child_never_waits_or_relaunches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake = root / 'quota-worker'
            fake.write_text('#!/usr/bin/env python3\nimport subprocess,sys\n'
                            'subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"])\n'
                            'print("rate limit reached for this window",file=sys.stderr)\nsys.exit(1)\n')
            fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
            config, run_dir, _ = self._plan(root, fake)
            with patch('burn_before_reset.runner._wait_for_replenishment', return_value=True) as wait:
                state = execute_run(config, run_dir, ENTRY)
            wait.assert_not_called()
            self.assertEqual(state['worker_calls'], 1)
            self.assertEqual(state['stop_reason'], 'descendant_cleanup_required')
            result = next(iter(state['task_results'].values()))
            self.assertTrue(result['quota_exhausted'])
            self.assertTrue(result['descendant_cleanup_required'])
            self.assertTrue(result['stop_confirmed'])
