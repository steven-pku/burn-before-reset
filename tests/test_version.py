from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from burn_before_reset import __version__


class VersionConsistencyTests(unittest.TestCase):
    def test_imported_version_matches_distribution_metadata(self):
        root = Path(__file__).resolve().parents[1]
        version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
        self.assertEqual(__version__, version)
