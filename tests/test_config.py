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

    def test_non_finite_durations_fail_closed(self) -> None:
        # TOML expresses inf and nan; neither is negative, so a sign check alone
        # lets them into deadline arithmetic and the SIGINT→SIGTERM→SIGKILL chain
        # loses its bounded-stop guarantee. Every duration must be finite at load.
        replacements = {
            "sigint_grace_seconds": "sigint_grace_seconds = 0.5",
            "sigterm_grace_seconds": "sigterm_grace_seconds = 0.5",
            "task_timeout_seconds": "task_timeout_seconds = 20",
            "max_tasks": "max_tasks = 3",
        }
        for field, line in replacements.items():
            for bad in ("inf", "-inf", "nan"):
                with self.subTest(field=field, value=bad), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    source = root / "source"
                    source.mkdir()
                    path = write_config(root / "config.toml", source, root / "output")
                    text = path.read_text(encoding="utf-8").replace(line, f"{field} = {bad}")
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ConfigError):
                        load_config(path)

    def test_non_finite_probe_interval_fails_closed(self) -> None:
        for bad in ("inf", "-inf", "nan"):
            with self.subTest(value=bad), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / "source"
                source.mkdir()
                path = write_config(root / "config.toml", source, root / "output")
                text = path.read_text(encoding="utf-8").replace(
                    'mode = "safe"',
                    f'mode = "safe"\nquota_replenish_probe_minutes = {bad}',
                )
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ConfigError):
                    load_config(path)


class ClaudeCliContractTests(unittest.TestCase):
    """`--safe-mode` is load-bearing but undocumented; preflight must probe for it.

    A CLI release that drops or renames the flag must be caught before any model
    call, not discovered as a mid-window worker exit — and never tolerated by
    silently launching without it, which reopens the MCP write-tool exposure.
    """

    def _claude_config(self, root: Path, fake: Path):
        import stat

        source = root / "source"
        source.mkdir()
        (source / "work.md").write_text("# W\n\nTODO: x.\n", encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        path = write_config(root / "config.toml", source, root / "output", enabled=True)
        text = path.read_text(encoding="utf-8").replace(
            "[execution]\nenabled = true",
            f'[execution]\nenabled = true\nprovider = "claude"\nclaude_binary = "{fake}"',
        )
        path.write_text(text, encoding="utf-8")
        return load_config(path)

    def test_preflight_accepts_a_cli_advertising_every_load_bearing_flag(self) -> None:
        from burn_before_reset.config import CLAUDE_LOAD_BEARING_FLAGS

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake = root / "fake-claude"
            flags = "\n".join(f"  {flag}  description" for flag in CLAUDE_LOAD_BEARING_FLAGS)
            fake.write_text(f"#!/bin/sh\nprintf '%s\\n' 'Usage: claude'\ncat <<'EOF'\n{flags}\nEOF\n", encoding="utf-8")
            config = self._claude_config(root, fake)
            assert_execution_environment(config, {})

    def test_preflight_fails_closed_when_safe_mode_is_not_advertised(self) -> None:
        from burn_before_reset.config import CLAUDE_LOAD_BEARING_FLAGS

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake = root / "fake-claude"
            flags = "\n".join(
                f"  {flag}  description" for flag in CLAUDE_LOAD_BEARING_FLAGS if flag != "--safe-mode"
            )
            fake.write_text(f"#!/bin/sh\ncat <<'EOF'\n{flags}\nEOF\n", encoding="utf-8")
            config = self._claude_config(root, fake)
            with self.assertRaisesRegex(ConfigError, "--safe-mode"):
                assert_execution_environment(config, {})

    def test_preflight_fails_closed_when_help_cannot_be_probed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fake = root / "fake-claude"
            # Executable but not runnable as a program: exec fails at probe time.
            fake.write_bytes(b"\x00\x01\x02")
            config = self._claude_config(root, fake)
            with self.assertRaises(ConfigError):
                assert_execution_environment(config, {})


if __name__ == "__main__":
    unittest.main()
