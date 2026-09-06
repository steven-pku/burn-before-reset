from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from burn_before_reset.cli import _parser
from burn_before_reset.config import ConfigError, assert_execution_environment, load_config
from burn_before_reset.discover import discover_sources
from burn_before_reset.indexer import _signals_and_snippets
from burn_before_reset.planner import plan_run
from burn_before_reset.runner import execute_run

from .helpers import write_config


class CommunityReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.path = write_config(self.root / 'config.toml', self.source, self.root / 'output', enabled=True)

    def test_distant_reset_is_rejected(self):
        write_config(self.path, self.source, self.root / 'output', reset_at=datetime(2099, 1, 1, tzinfo=UTC))
        with self.assertRaisesRegex(ConfigError, '24 hours'):
            load_config(self.path)

    def test_runtime_ceiling_applies_before_reset(self):
        now = datetime.now(UTC)
        write_config(self.path, self.source, self.root / 'output', reset_at=now + timedelta(hours=20))
        config = load_config(self.path, now=now)
        self.assertLessEqual(config.run.hard_stop_at, now + timedelta(hours=12))

    def test_execution_requires_named_provider(self):
        self.path.write_text(self.path.read_text().replace('provider = "codex"\n', ''))
        with self.assertRaisesRegex(ConfigError, 'explicit'):
            assert_execution_environment(load_config(self.path), env={})

    def test_cli_requires_reviewed_queue_or_autopilot(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            _parser().parse_args(['run', '--config', str(self.path), '--execute'])
        self.assertEqual(raised.exception.code, 2)

    def test_reviewed_queue_does_not_replan(self):
        config = load_config(self.path)
        run_dir = plan_run(config)
        with patch('burn_before_reset.runner.plan_followup_round', return_value=None) as replan:
            execute_run(config, run_dir, Path(__file__))
        replan.assert_not_called()

    def test_reload_cannot_extend_frozen_deadline(self):
        config = load_config(self.path)
        run_dir = plan_run(config)
        frozen = json.loads((run_dir / 'RUN_STATE.json').read_text())['hard_stop_at']
        later = replace(config, run=replace(config.run, hard_stop_at=config.run.hard_stop_at + timedelta(hours=1)))
        with patch('burn_before_reset.runner._work_queue', return_value='queue_exhausted') as work:
            execute_run(later, run_dir, Path(__file__))
        self.assertEqual(work.call_args.args[0].run.hard_stop_at.isoformat(), frozen)

    def test_changed_provider_invalidates_plan(self):
        config = load_config(self.path)
        run_dir = plan_run(config)
        changed = replace(config, execution=replace(config.execution, provider='claude'))
        with self.assertRaisesRegex(ValueError, 'configuration'):
            execute_run(changed, run_dir, Path(__file__))

    def test_completed_cancelled_quoted_and_example_tasks_are_not_work(self):
        signals, _ = _signals_and_snippets('- [x] TODO: shipped\n- [-] TODO: cancelled\n> TODO: historical quote\n```md\nTODO: example\n```', self.source)
        self.assertEqual(signals, ())
        signals, snippets = _signals_and_snippets('- [x] TODO: shipped\n- [ ] TODO: still open', self.source)
        self.assertIn('todo', signals)
        self.assertEqual(len(snippets), 1)

    def test_gitfile_worktree_is_discovered(self):
        repo = self.root / 'Documents' / 'worktree'
        repo.mkdir(parents=True)
        (repo / '.git').write_text('gitdir: /example/repository/.git/worktrees/worktree\n')
        proposals = discover_sources(self.root)
        self.assertTrue(any(item.root == repo and item.source_type == 'git' for item in proposals))
