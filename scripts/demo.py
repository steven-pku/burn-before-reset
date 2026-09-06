#!/usr/bin/env python3
"""Create a real plan and a separate, clearly fictional report. No model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from burn_before_reset.config import ConfigError, assert_execution_environment, load_config
from burn_before_reset.planner import plan_run
from burn_before_reset.report_html import write_html_report
from burn_before_reset.validation import validate_run


def demo(destination: Path | None = None) -> Path:
    if destination is None:
        destination = Path(tempfile.mkdtemp(prefix="bbr-demo-")).resolve()
    else:
        destination = destination.expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=False)
    source = destination / "sample-source"
    source.mkdir()
    note = source / "release.md"
    note.write_text("# Sample release\n\n- [ ] TODO: prepare a rollback checklist.\n- [x] TODO: update the old badge.\n", encoding="utf-8")
    before = hashlib.sha256(note.read_bytes()).hexdigest()
    template = (ROOT / "examples/config.example.toml").read_text(encoding="utf-8").split('[[sources]]')[0]
    template = template.replace('REPLACE_WITH_CONFIRMED_ISO_TIMESTAMP', (datetime.now(UTC) + timedelta(hours=3)).isoformat())
    template = template.replace('CHOOSE_PROVIDER', 'codex').replace('~/burn-before-reset-runs', (destination / 'plans').as_posix())
    for key in ('subscription_auth_only', 'user_asserts_credit_balance_zero', 'user_asserts_auto_top_up_off'):
        template = template.replace(f'{key} = false', f'{key} = true')
    config_path = destination / "demo.toml"
    config_path.write_text('# FICTIONAL demo assertions. Execution is disabled. Do not reuse for real work.\n' + template +
                           '\n[[sources]]\ntype = "markdown"\nroot = ' + json.dumps(str(source)) + '\nextensions = [".md"]\n', encoding="utf-8")
    config = load_config(config_path)
    plan = plan_run(config)
    errors = validate_run(plan)
    if errors or hashlib.sha256(note.read_bytes()).hexdigest() != before:
        raise RuntimeError(f"demo plan validation failed: {errors}")
    try:
        assert_execution_environment(config, env={})
    except ConfigError as exc:
        if 'execution.enabled is false' not in str(exc):
            raise
    else:
        raise RuntimeError("demo execution gate did not refuse")

    # Display-only fixture: no fabricated RUN_STATE or worker receipts.
    preview = destination / "sample-report"
    (preview / "artifacts").mkdir(parents=True)
    tasks = []
    samples = [
        ('Frame the open decision so it can be made: Release rollback', '# Release rollback\n\nSample data — no model calls.\n\n## Options\n\n1. Release after a rollback rehearsal.\n2. Hold until the rollback owner is named.\n\n## Missing evidence\n\nNo rehearsal record is available in this fictional example.\n\n## Next action\n\nAsk the release owner to attach a rehearsal result before deciding.\n'),
        ('Verify the unverified claim: Migration readiness', '# Migration readiness\n\nSample data — no model calls.\n\n## Verdict\n\nUncheckable from here. No migration test evidence is available.\n\n## Next action\n\nCollect a test result; do not treat this review as verification of the claim.\n'),
    ]
    for index, (title, body) in enumerate(samples):
        task_id = f'task-{index:012x}'
        artifact = f'artifacts/{task_id}.md'
        (preview / artifact).write_text(body, encoding='utf-8')
        tasks.append({'id': task_id, 'title': title, 'deliverables': [artifact],
                      'source_refs': [{'source_type': 'markdown', 'root': '/sample/project', 'path': 'release.md', 'signals': ['todo']}]})
    (preview / 'QUEUE.json').write_text(json.dumps({'tasks': tasks}), encoding='utf-8')
    state = {'run_id': 'SAMPLE DATA · NO MODEL CALLS', 'phase': 'stopped', 'stop_reason': 'queue_exhausted',
             'completed': [task['id'] for task in tasks], 'failed': [], 'sample_data': True,
             'burn': {}, 'worker_calls': 0, 'rounds': [], 'task_results': {}}
    report = write_html_report(preview, state, language='en')
    write_html_report(preview, state, language='zh').replace(preview / 'REPORT.zh.html')
    write_html_report(preview, state, language='en')
    for page in (report, preview / 'REPORT.zh.html'):
        page.write_text(page.read_text(encoding='utf-8').replace(str(preview), '/sample/report'), encoding='utf-8')
    print('DEMO READY — no model, login or quota used')
    print(f'Plan validated; source unchanged; execution disabled.\nPlan: {plan}\nSample report: {report}')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new directory; refuses to overwrite an existing path')
    args = parser.parse_args()
    demo(args.output)
