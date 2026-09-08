from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from burn_before_reset.paths import (
    audit_exclusions,
    is_secret_like,
    is_within,
    iter_allowlisted_files,
)


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


class ExclusionFragmentTests(unittest.TestCase):
    """`exclude_fragments` has to mean what it is called.

    Until 2026-09-08 an entry was intersected against whole path components, so it
    could only ever match a complete directory or file name. A `claude_sessions`
    root flattens a whole project path into one segment
    (`-Users-me-Documents-Projects-Finance`), so on those sources no entry could
    express "exclude the Finance project" at all — the same config line silently
    meant different things on different source types.
    """

    def test_a_fragment_inside_a_segment_excludes_the_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "projects"
            root.mkdir()
            flattened = root / "-Users-me-Documents-Projects-Finance"
            flattened.mkdir()
            (flattened / "session.md").write_text("TODO money", encoding="utf-8")
            keep = root / "-Users-me-Documents-Projects-Alpha"
            keep.mkdir()
            (keep / "session.md").write_text("TODO alpha", encoding="utf-8")
            files = list(iter_allowlisted_files(root, extensions=(".md",), exclude_fragments=("finance",)))
            self.assertEqual(files, [(keep / "session.md").resolve()])

    def test_a_fragment_inside_a_file_name_excludes_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "notes"
            root.mkdir()
            (root / "2026-finance-review.md").write_text("TODO money", encoding="utf-8")
            (root / "2026-alpha-review.md").write_text("TODO alpha", encoding="utf-8")
            files = list(iter_allowlisted_files(root, extensions=(".md",), exclude_fragments=("finance",)))
            self.assertEqual(files, [(root / "2026-alpha-review.md").resolve()])

    def test_a_slash_anchors_an_entry_to_a_whole_segment(self) -> None:
        """`.git` as a fragment also catches `.github`; `/.git/` catches only `.git`.

        Substring matching is the right default — it is what the option is named
        for — but it has a cost the previous whole-segment rule did not: an entry
        meant as a directory name starts catching longer names that contain it.
        Anchoring is how an operator says "this exact segment" without giving up
        fragments everywhere else.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            (root / ".git").mkdir(parents=True)
            (root / ".git" / "notes.md").write_text("TODO internal", encoding="utf-8")
            (root / ".github").mkdir()
            (root / ".github" / "notes.md").write_text("TODO workflow", encoding="utf-8")
            anchored = list(iter_allowlisted_files(root, extensions=(".md",), exclude_fragments=("/.git/",)))
            self.assertEqual(anchored, [(root / ".github" / "notes.md").resolve()])
            bare = list(iter_allowlisted_files(root, extensions=(".md",), exclude_fragments=(".git",)))
            self.assertEqual(bare, [])

    def test_an_anchored_entry_still_matches_at_any_depth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            (root / "packages" / "web" / "node_modules").mkdir(parents=True)
            (root / "packages" / "web" / "node_modules" / "dep.md").write_text("TODO dep", encoding="utf-8")
            (root / "packages" / "web" / "app.md").write_text("TODO app", encoding="utf-8")
            files = list(iter_allowlisted_files(root, extensions=(".md",), exclude_fragments=("/node_modules/",)))
            self.assertEqual(files, [(root / "packages" / "web" / "app.md").resolve()])

    def test_the_source_root_name_is_never_matched(self) -> None:
        """Matching is relative to the root, so a root called `private` still indexes."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "private"
            root.mkdir()
            (root / "note.md").write_text("TODO keep", encoding="utf-8")
            files = list(iter_allowlisted_files(root, extensions=(".md",), exclude_fragments=("private",)))
            self.assertEqual(files, [(root / "note.md").resolve()])


class ExclusionAuditTests(unittest.TestCase):
    """A silently inert safety control is the danger; name what each entry catches."""

    def test_an_entry_that_matches_nothing_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "projects"
            root.mkdir()
            (root / "-Users-me-Documents-Projects-Finance").mkdir()
            audit = audit_exclusions(root, ("finance", "node_modules"))
            self.assertEqual(audit.matches["finance"], ["-Users-me-Documents-Projects-Finance"])
            self.assertEqual(audit.matches["node_modules"], [])

    def test_every_matching_entry_is_credited_not_only_the_first(self) -> None:
        """Found against the real session root: two entries matched the same 55
        directories, and crediting only the first reported the other as inert. An
        entry that is working must never be reported as matching nothing."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "projects"
            root.mkdir()
            (root / "-Users-me-runs-run-1-staging-task-2").mkdir()
            audit = audit_exclusions(root, ("-staging-", "runs"))
            self.assertEqual(len(audit.matches["-staging-"]), 1)
            self.assertEqual(len(audit.matches["runs"]), 1)

    def test_a_truncated_walk_says_so_instead_of_reporting_nothing(self) -> None:
        """A partial walk must not read as "this exclusion is inert"."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "projects"
            root.mkdir()
            for index in range(5):
                (root / f"dir{index}").mkdir()
            audit = audit_exclusions(root, ("dir4",), limit=1)
            self.assertTrue(audit.truncated)
            complete = audit_exclusions(root, ("dir4",))
            self.assertFalse(complete.truncated)
            self.assertEqual(complete.matches["dir4"], ["dir4"])

    def test_an_excluded_directory_is_not_descended_into(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "projects"
            root.mkdir()
            outer = root / "private"
            (outer / "private-inner").mkdir(parents=True)
            audit = audit_exclusions(root, ("private",))
            self.assertEqual(audit.matches["private"], ["private"])


if __name__ == "__main__":
    unittest.main()
