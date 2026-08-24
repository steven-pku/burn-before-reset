from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from burn_before_reset.paths import is_secret_like, is_within, iter_allowlisted_files


class PathTests(unittest.TestCase):
    def test_secret_and_excluded_files_are_not_yielded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "root"
            root.mkdir()
            (root / "ok.md").write_text("TODO useful", encoding="utf-8")
            (root / ".env").write_text("SECRET=x", encoding="utf-8")
            private = root / "private"
            private.mkdir()
            (private / "hidden.md").write_text("TODO private", encoding="utf-8")
            files = list(iter_allowlisted_files(root, extensions=(".md",), exclude_fragments=("private",)))
            self.assertEqual(files, [(root / "ok.md").resolve()])
            self.assertTrue(is_secret_like(root / "auth.json"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_escape_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "root"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "leak.md").write_text("TODO leak", encoding="utf-8")
            (root / "escape").symlink_to(outside, target_is_directory=True)
            files = list(iter_allowlisted_files(root, extensions=(".md",), exclude_fragments=()))
            self.assertEqual(files, [])
            self.assertFalse(is_within(outside / "leak.md", root))


if __name__ == "__main__":
    unittest.main()
