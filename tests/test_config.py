from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from burn_before_reset.config import (
    ConfigError,
    assert_execution_environment,
    load_config,
)

from .helpers import write_config


class ConfigTests(unittest.TestCase):
    def test_valid_config_computes_hard_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            output = root / "output"
            reset = datetime.now(UTC) + timedelta(hours=3)
            path = write_config(root / "config.toml", source, output, reset_at=reset)
            config = load_config(path)
            self.assertEqual(config.run.hard_stop_at, reset - timedelta(minutes=15))
            self.assertFalse(config.execution.enabled)

    def test_timezone_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            path = write_config(root / "config.toml", source, root / "output")
            text = path.read_text(encoding="utf-8")
            text = text.replace("+00:00", "")
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "timezone"):
                load_config(path)

    def test_reset_timestamp_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            path = write_config(root / "config.toml", source, root / "output")
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("reset_at =")]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "ISO-8601"):
                load_config(path)

    def test_past_hard_stop_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            reset = datetime.now(UTC) + timedelta(minutes=5)
            path = write_config(root / "config.toml", source, root / "output", reset_at=reset)
            with self.assertRaisesRegex(ConfigError, "hard stop is not in the future"):
                load_config(path)

    def test_short_buffer_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            path = write_config(root / "config.toml", source, root / "output", safety=9)
            with self.assertRaisesRegex(ConfigError, "at least 10"):
                load_config(path)

    def test_output_must_not_overlap_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            path = write_config(root / "config.toml", source, source / "runs")
            with self.assertRaisesRegex(ConfigError, "must not overlap"):
                load_config(path)

    def test_execution_requires_double_gate_and_no_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            disabled = load_config(write_config(root / "disabled.toml", source, root / "out-a"))
            with self.assertRaisesRegex(ConfigError, "enabled is false"):
                assert_execution_environment(disabled, {})
            enabled = load_config(write_config(root / "enabled.toml", source, root / "out-b", enabled=True))
            with self.assertRaisesRegex(ConfigError, "API key"):
                assert_execution_environment(enabled, {"CODEX_API_KEY": "secret"})
            assert_execution_environment(enabled, {})

    def test_false_billing_assertion_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            path = write_config(root / "config.toml", source, root / "output")
            text = path.read_text(encoding="utf-8").replace(
                "user_asserts_credit_balance_zero = true",
                "user_asserts_credit_balance_zero = false",
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "billing safety assertions"):
                load_config(path)

    def test_execution_is_plan_only_inside_sixty_minutes_of_hard_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            now = datetime.now(UTC)
            reset = now + timedelta(minutes=70)
            config = load_config(
                write_config(root / "config.toml", source, root / "output", reset_at=reset, enabled=True),
                now=now,
            )
            with self.assertRaisesRegex(ConfigError, "plan-only"):
                assert_execution_environment(config, {}, now=now)

    def test_execution_is_allowed_at_exactly_sixty_minutes_before_hard_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            now = datetime.now(UTC)
            reset = now + timedelta(minutes=75)
            config = load_config(
                write_config(root / "config.toml", source, root / "output", reset_at=reset, enabled=True),
                now=now,
            )
            assert_execution_environment(config, {}, now=now)

    def test_task_timeout_must_fit_between_drain_and_hard_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            path = write_config(root / "config.toml", source, root / "output")
            text = path.read_text(encoding="utf-8").replace(
                "task_timeout_seconds = 20",
                "task_timeout_seconds = 901",
            )
            path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "drain-to-hard-stop"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
