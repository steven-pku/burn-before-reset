from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from burn_before_reset.cli import main

from .helpers import write_config


class CliTests(unittest.TestCase):
    def test_run_directory_must_be_inside_configured_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            outside = root / "outside"
            outside.mkdir()
            config_path = write_config(root / "config.toml", source, root / "output", enabled=True)
            stderr = io.StringIO()
            with (
                patch.dict(os.environ, {"OPENAI_API_KEY": "", "CODEX_API_KEY": ""}),
                redirect_stderr(stderr),
            ):
                result = main(
                    [
                        "run",
                        "--config",
                        str(config_path),
                        "--run-dir",
                        str(outside),
                        "--execute",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertIn("inside run.output_root", stderr.getvalue())

    def test_non_queue_stop_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            output = root / "output"
            run_dir = output / "run-existing"
            run_dir.mkdir(parents=True)
            config_path = write_config(root / "config.toml", source, output, enabled=True)
            stdout = io.StringIO()
            with (
                patch.dict(os.environ, {"OPENAI_API_KEY": "", "CODEX_API_KEY": ""}),
                patch("burn_before_reset.cli.execute_run", return_value={"stop_reason": "drain_window", "failed": []}),
                redirect_stdout(stdout),
            ):
                result = main(
                    [
                        "run",
                        "--config",
                        str(config_path),
                        "--run-dir",
                        str(run_dir),
                        "--execute",
                    ]
                )
            self.assertEqual(result, 1)
            self.assertIn("drain_window", stdout.getvalue())

    def test_clean_queue_exhaustion_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            output = root / "output"
            run_dir = output / "run-existing"
            run_dir.mkdir(parents=True)
            config_path = write_config(root / "config.toml", source, output, enabled=True)
            with (
                patch.dict(os.environ, {"OPENAI_API_KEY": "", "CODEX_API_KEY": ""}),
                patch(
                    "burn_before_reset.cli.execute_run",
                    return_value={"stop_reason": "queue_exhausted", "failed": []},
                ),
                redirect_stdout(io.StringIO()),
            ):
                result = main(
                    [
                        "run",
                        "--config",
                        str(config_path),
                        "--run-dir",
                        str(run_dir),
                        "--execute",
                    ]
                )
            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
