#!/usr/bin/env python3
"""Run the same hermetic checks locally and in CI, from any working directory."""
from __future__ import annotations

import argparse
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
        if args.release_tag != f'v{version}':
            parser.error(f'release tag must be v{version}')
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-v'], cwd=ROOT, env=env, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
