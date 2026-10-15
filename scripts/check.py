#!/usr/bin/env python3
"""Run the same hermetic checks locally and in CI, from any working directory."""
from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-tag', help='also check that a proposed vX.Y.Z tag matches package metadata')
    args = parser.parse_args()
    if args.release_tag:
        version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
        module = ast.parse((ROOT / 'src/burn_before_reset/__init__.py').read_text())
        declared = next(ast.literal_eval(node.value) for node in module.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets))
        if declared != version:
            parser.error('package __version__ must match project.version')
        if f'[{version}]: ' not in (ROOT / 'CHANGELOG.md').read_text():
            parser.error('package version must have a CHANGELOG link definition')
        if f'## [{version}]' not in (ROOT / 'CHANGELOG.md').read_text():
            parser.error('package version must have a CHANGELOG release entry')
        if args.release_tag != f'v{version}':
            parser.error(f'release tag must be v{version}')
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-v'], cwd=ROOT, env=env, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
