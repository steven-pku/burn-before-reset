from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_discovered_skill_can_be_copied_and_run_independently(self):
        for surface in ('.agents', '.claude'):
            with self.subTest(surface=surface), tempfile.TemporaryDirectory() as temporary:
                source = ROOT / surface / 'skills' / 'burn-before-reset'

                def assert_acyclic(path, ancestors=()):
                    resolved = path.resolve()
                    self.assertNotIn(resolved, ancestors, f'recursive Skill copy at {path}')
                    if resolved.is_dir():
                        for child in path.iterdir():
                            assert_acyclic(child, (*ancestors, resolved))

                assert_acyclic(source)
                destination = Path(temporary) / 'installed skill'
                shutil.copytree(source, destination)
                self.assertLess(len(list(destination.rglob('*'))), 150)
                self.assertFalse(any(path.is_symlink() for path in destination.rglob('*')))
                self.assertFalse((destination / '.git').exists())
                for reference in ('SKILL.md', 'references/risk-policy.md', 'task-packs/thread-recovery.md'):
                    self.assertTrue((destination / reference).is_file(), reference)
                env = {**os.environ, 'PYTHONPATH': '', 'PYTHONDONTWRITEBYTECODE': '1'}
                result = subprocess.run(
                    [sys.executable, str(destination / 'scripts' / 'demo.py'), '--output',
                     str(Path(temporary) / 'demo output')],
                    cwd=temporary, env=env, capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('DEMO READY', result.stdout)

    def test_release_skill_zip_contains_only_independent_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts' / 'package_skill.py'), '--output', temporary],
                cwd=temporary, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with ZipFile(result.stdout.strip()) as archive:
                names = archive.namelist()
                self.assertLess(len(names), 100)
                self.assertFalse(any('.egg-info/' in name or '.ruff_cache/' in name for name in names))
                self.assertFalse(any((item.external_attr >> 16) & 0o170000 == 0o120000
                                     for item in archive.infolist()))
                archive.extractall(temporary)
            copied = Path(temporary) / 'burn-before-reset'
            demo = subprocess.run(
                [sys.executable, str(copied / 'scripts' / 'demo.py'), '--output',
                 str(Path(temporary) / 'zip demo')],
                cwd=temporary, capture_output=True, text=True, check=False,
            )
            self.assertEqual(demo.returncode, 0, demo.stderr)
            self.assertIn('DEMO READY', demo.stdout)
