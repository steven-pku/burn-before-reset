#!/usr/bin/env python3
"""Verify an installed wheel with mock workers, from a separate working directory."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo))
from importlib.metadata import metadata, version

from burn_before_reset import __version__, cli
from tests.helpers import write_config
from tests.test_consecutive_failures import FAKE_WORKER

assert 'site-packages' in cli.__file__, cli.__file__
import tomllib

assert __version__ == version('burn-before-reset')
assert version('burn-before-reset') == tomllib.loads((repo / 'pyproject.toml').read_text())['project']['version']
assert not metadata('burn-before-reset').get_all('Requires-Dist')
root = Path(sys.argv[2]).resolve()
root.mkdir(parents=True, exist_ok=True)
source = root / 'source notes'
source.mkdir(exist_ok=True)
for i in range(3):
    (source / f'todo{i}.md').write_text(f'# Item {i}\nTODO: recover work {i}\n')
fake = root / 'fake-worker'
fake.write_text(FAKE_WORKER.format(fail_first=1))
fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
config = write_config(root / 'run config.toml', source, root / 'output runs', enabled=True,
                      codex_binary=str(fake), max_tasks=3, max_consecutive_failures=3)
bbr = Path(sys.executable).with_name('bbr')
env = {**os.environ, 'PYTHONPATH': '', 'PYTHONDONTWRITEBYTECODE':'1'}
for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
    env.pop(key, None)

def call(*args, expected=0):
    result = subprocess.run([str(bbr), *args], cwd=root, env=env, text=True,
                            capture_output=True, check=False)
    assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
    return result.stdout.strip()

before = {p.name: p.read_bytes() for p in source.iterdir()}
call('validate-config', '--config', str(config))
run = Path(call('plan', '--config', str(config)))
call('run','--config',str(config),'--run-dir',str(run),'--execute', expected=1)
call('validate-run','--run-dir',str(run))
state = json.loads((run/'RUN_STATE.json').read_text())
assert len(state['completed']) == 2 and len(state['failed']) == 1
assert state['stop_reason'] == 'queue_exhausted'
recovery = Path(call('plan','--config',str(config)))
queue = json.loads((recovery/'QUEUE.json').read_text())
assert len(queue['tasks']) == 1, queue
call('run','--config',str(config),'--run-dir',str(recovery),'--execute')
call('validate-run','--run-dir',str(recovery))
state2 = json.loads((recovery/'RUN_STATE.json').read_text())
assert len(state2['completed']) == 1 and not state2['failed']
assert before == {p.name:p.read_bytes() for p in source.iterdir()}
print(json.dumps({'package': version('burn-before-reset'),'runtime_dependencies': [],
                  'first_run': {'completed':2,'failed':1,'exit':1},
                  'recovery': {'completed':1,'previous_successes_skipped':2},
                  'sources_unchanged':True,'module':cli.__file__},indent=2))
