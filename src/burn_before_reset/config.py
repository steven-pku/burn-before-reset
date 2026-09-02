from __future__ import annotations

import math
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .paths import ExecutableError, resolve_executable


class ConfigError(ValueError):
    """Raised when a run configuration fails closed."""


# Flags the Claude worker command depends on for its read-only guarantee.
# `--safe-mode` is load-bearing (without it a probe reached a connected
# cloud-storage write tool) but absent from the documented CLI reference, so it
# cannot be treated as a stable contract: the preflight probes `claude --help`
# and refuses to run against a CLI that does not advertise every one of these.
# Dropping `--safe-mode` and relying on `--tools` alone is not an acceptable
# fallback — that reopens the MCP write-tool hole the flag exists to close.
CLAUDE_LOAD_BEARING_FLAGS = (
    "--safe-mode",
    "--restricted",
    "--strict-mcp-config",
    "--permission-mode",
    "--tools",
    "--add-dir",
)


@dataclass(frozen=True)
class RunSettings:
    reset_at: datetime
    hard_stop_at: datetime
    safety_buffer_minutes: int
    drain_window_minutes: int
    mode: str
    output_root: Path
    wait_for_replenish: bool
    quota_replenish_probe_minutes: float
    replan_when_queue_empty: bool
    output_language: str
    report_language: str


@dataclass(frozen=True)
class BillingSettings:
    subscription_auth_only: bool
    user_asserts_credit_balance_zero: bool
    user_asserts_auto_top_up_off: bool
    allow_api_key: bool
    allow_paid_credits: bool
    allow_provider_fallback: bool


@dataclass(frozen=True)
class ExecutionSettings:
    enabled: bool
    provider: str
    codex_binary: str
    claude_binary: str
    max_tasks: int
    max_worker_calls_per_run: int
    task_timeout_seconds: int
    sigint_grace_seconds: float
    sigterm_grace_seconds: float


@dataclass(frozen=True)
class SourceSettings:
    source_type: str
    root: Path
    extensions: tuple[str, ...]
    exclude_fragments: tuple[str, ...]
    max_file_bytes: int


@dataclass(frozen=True)
class TaskPolicy:
    minimum_score: int
    maximum_risk: int
    maximum_human_dependency: int
    max_candidates: int


@dataclass(frozen=True)
class AppConfig:
    run: RunSettings
    billing: BillingSettings
    execution: ExecutionSettings
    sources: tuple[SourceSettings, ...]
    task_policy: TaskPolicy


def _require_table(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"missing [{name}] table")
    return value


def _require_bool(table: dict[str, Any], key: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be true or false")
    return value


def _finite_number(raw: Any, field: str, *, minimum: float, maximum: float) -> float:
    """Every duration, timeout, grace period, and probe interval passes here.

    TOML happily expresses `inf` and `nan`; neither is negative, so a plain
    sign check lets them through into deadline arithmetic, where `inf` makes an
    escalation wait never expire and `nan` makes every comparison false. The
    core safety property is a *bounded* stop after the hard deadline — a
    non-finite bound is no bound at all, so these fail closed at load.
    """
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ConfigError(f"{field} must be a finite number")
    value = float(raw)
    if not math.isfinite(value):
        raise ConfigError(f"{field} must be a finite number")
    if not minimum <= value <= maximum:
        raise ConfigError(f"{field} must be between {minimum:g} and {maximum:g}")
    return value


def _absolute_path(raw: Any, field: str, *, must_exist: bool) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigError(f"{field} must be a non-empty absolute path")
    expanded = os.path.expanduser(os.path.expandvars(raw))
    if "$" in expanded:
        raise ConfigError(f"{field} contains an unresolved environment variable")
    path = Path(expanded)
    if not path.is_absolute():
        raise ConfigError(f"{field} must be absolute")
    resolved = path.resolve(strict=False)
    if must_exist and (not resolved.exists() or not resolved.is_dir()):
        raise ConfigError(f"{field} must be an existing directory: {resolved}")
    return resolved


def _parse_reset_at(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise ConfigError("run.reset_at must be an ISO-8601 string with timezone")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigError("run.reset_at must be valid ISO-8601") from exc
    if value.tzinfo is None or value.utcoffset() is None:
        raise ConfigError("run.reset_at must include an explicit timezone")
    return value


def _overlaps(a: Path, b: Path) -> bool:
    return a == b or a.is_relative_to(b) or b.is_relative_to(a)


def load_config(path: str | Path, *, now: datetime | None = None) -> AppConfig:
    config_path = Path(path)
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot read config: {exc}") from exc

    run_data = _require_table(data, "run")
    billing_data = _require_table(data, "billing")
    execution_data = _require_table(data, "execution")
    policy_data = _require_table(data, "task_policy")

    reset_at = _parse_reset_at(run_data.get("reset_at"))
    safety = run_data.get("safety_buffer_minutes", 15)
    drain = run_data.get("drain_window_minutes", 30)
    mode = run_data.get("mode", "safe")
    if not isinstance(safety, int) or safety < 10:
        raise ConfigError("safety_buffer_minutes must be at least 10")
    if not isinstance(drain, int) or drain <= safety:
        raise ConfigError("drain_window_minutes must be greater than the safety buffer")
    if mode not in {"safe", "balanced"}:
        raise ConfigError("run.mode must be safe or balanced")
    wait_for_replenish = run_data.get("wait_for_replenish", True)
    if not isinstance(wait_for_replenish, bool):
        raise ConfigError("run.wait_for_replenish must be true or false")
    probe_minutes = _finite_number(
        run_data.get("quota_replenish_probe_minutes", 20),
        "run.quota_replenish_probe_minutes",
        minimum=0.005,
        maximum=180,
    )
    replan_when_queue_empty = run_data.get("replan_when_queue_empty", True)
    if not isinstance(replan_when_queue_empty, bool):
        raise ConfigError("run.replan_when_queue_empty must be true or false")
    # This tool is written in English; the work it reads usually is not. Left alone the
    # worker answers in the prompt's language, which hands a Chinese-language project a
    # night of English reports its owner has to translate before they can even triage.
    # "auto" makes the artifact follow the language of the sources actually read.
    output_language = run_data.get("output_language", "auto")
    if not isinstance(output_language, str) or not output_language.strip():
        raise ConfigError("run.output_language must be a non-empty string")
    output_language = output_language.strip()
    if len(output_language) > 60:
        raise ConfigError("run.output_language must be at most 60 characters")
    # The report is for the user, so it speaks the user's language — which only the
    # orchestrating agent knows, from the conversation. "auto" follows the artifacts.
    report_language = run_data.get("report_language", "auto")
    if not isinstance(report_language, str) or not report_language.strip():
        raise ConfigError("run.report_language must be a non-empty string")
    report_language = report_language.strip()
    if len(report_language) > 60:
        raise ConfigError("run.report_language must be at most 60 characters")
    output_root = _absolute_path(run_data.get("output_root"), "run.output_root", must_exist=False)
    hard_stop_at = reset_at - timedelta(minutes=safety)
    current = now or datetime.now(tz=reset_at.tzinfo)
    if current.tzinfo is None:
        current = current.replace(tzinfo=reset_at.tzinfo)
    if hard_stop_at <= current:
        raise ConfigError("hard stop is not in the future")
    if hard_stop_at - current < timedelta(minutes=20):
        raise ConfigError("fewer than 20 minutes remain before hard stop")

    billing = BillingSettings(
        subscription_auth_only=_require_bool(billing_data, "subscription_auth_only"),
        user_asserts_credit_balance_zero=_require_bool(billing_data, "user_asserts_credit_balance_zero"),
        user_asserts_auto_top_up_off=_require_bool(billing_data, "user_asserts_auto_top_up_off"),
        allow_api_key=_require_bool(billing_data, "allow_api_key"),
        allow_paid_credits=_require_bool(billing_data, "allow_paid_credits"),
        allow_provider_fallback=_require_bool(billing_data, "allow_provider_fallback"),
    )
    if not (
        billing.subscription_auth_only
        and billing.user_asserts_credit_balance_zero
        and billing.user_asserts_auto_top_up_off
    ):
        raise ConfigError("billing safety assertions must all be true")
    if billing.allow_api_key or billing.allow_paid_credits or billing.allow_provider_fallback:
        raise ConfigError("API keys, paid credits, and provider fallback must be disabled")

    provider = str(execution_data.get("provider", "codex"))
    if provider not in {"codex", "claude"}:
        raise ConfigError("execution.provider must be codex or claude")
    if provider == "claude" and mode != "safe":
        # The Claude worker's read-only story rests on withholding every write tool.
        # A balanced variant would have to hand some back, and that path is unproven.
        raise ConfigError("execution.provider = claude supports run.mode = safe only")
    execution = ExecutionSettings(
        enabled=_require_bool(execution_data, "enabled"),
        provider=provider,
        codex_binary=str(execution_data.get("codex_binary", "codex")),
        claude_binary=str(execution_data.get("claude_binary", "claude")),
        max_tasks=int(
            _finite_number(
                execution_data.get("max_tasks", 3),
                "execution.max_tasks",
                minimum=1,
                maximum=200,
            )
        ),
        max_worker_calls_per_run=int(
            _finite_number(
                execution_data.get("max_worker_calls_per_run", 500),
                "execution.max_worker_calls_per_run",
                minimum=1,
                maximum=2000,
            )
        ),
        task_timeout_seconds=int(
            _finite_number(
                execution_data.get("task_timeout_seconds", 900),
                "execution.task_timeout_seconds",
                minimum=10,
                maximum=86400,
            )
        ),
        sigint_grace_seconds=_finite_number(
            execution_data.get("sigint_grace_seconds", 20),
            "execution.sigint_grace_seconds",
            minimum=0,
            maximum=600,
        ),
        sigterm_grace_seconds=_finite_number(
            execution_data.get("sigterm_grace_seconds", 10),
            "execution.sigterm_grace_seconds",
            minimum=0,
            maximum=600,
        ),
    )
    # The real bounds on a run are the hard stop, the drain window, and the per-task
    # timeout. A cap of 10 made the tool unable to fill the window it exists to fill:
    # ten tasks of a few minutes each leave a nine-hour window almost entirely idle.
    # These stay only as runaway backstops: max_tasks bounds one queue,
    # max_worker_calls_per_run bounds every worker launch a run may ever make —
    # quota retries and re-planned rounds included.
    drain_budget_seconds = (drain - safety) * 60
    if execution.task_timeout_seconds > drain_budget_seconds:
        raise ConfigError("execution.task_timeout_seconds exceeds the drain-to-hard-stop budget")

    source_rows = data.get("sources")
    if not isinstance(source_rows, list) or not source_rows:
        raise ConfigError("at least one [[sources]] table is required")
    sources: list[SourceSettings] = []
    for index, row in enumerate(source_rows):
        if not isinstance(row, dict):
            raise ConfigError(f"sources[{index}] must be a table")
        source_type = row.get("type")
        if source_type not in {"markdown", "codex_sessions", "claude_sessions", "git"}:
            raise ConfigError(f"unsupported sources[{index}].type")
        root = _absolute_path(row.get("root"), f"sources[{index}].root", must_exist=True)
        extensions_raw = row.get("extensions", [".md", ".txt", ".jsonl"])
        excludes_raw = row.get("exclude_fragments", [])
        if not isinstance(extensions_raw, list) or not all(isinstance(x, str) for x in extensions_raw):
            raise ConfigError(f"sources[{index}].extensions must be a string list")
        if not isinstance(excludes_raw, list) or not all(isinstance(x, str) for x in excludes_raw):
            raise ConfigError(f"sources[{index}].exclude_fragments must be a string list")
        max_bytes = int(row.get("max_file_bytes", 262144))
        if max_bytes < 1024 or max_bytes > 1_048_576:
            raise ConfigError("max_file_bytes must be between 1024 and 1048576")
        sources.append(
            SourceSettings(
                source_type=source_type,
                root=root,
                extensions=tuple(x.lower() for x in extensions_raw),
                exclude_fragments=tuple(excludes_raw),
                max_file_bytes=max_bytes,
            )
        )
    if any(_overlaps(output_root, source.root) for source in sources):
        raise ConfigError("run.output_root must not overlap any source root")

    task_policy = TaskPolicy(
        minimum_score=int(policy_data.get("minimum_score", 30)),
        maximum_risk=int(policy_data.get("maximum_risk", 2)),
        maximum_human_dependency=int(policy_data.get("maximum_human_dependency", 1)),
        max_candidates=int(policy_data.get("max_candidates", 50)),
    )
    if task_policy.max_candidates < 1 or task_policy.max_candidates > 500:
        raise ConfigError("task_policy.max_candidates must be between 1 and 500")
    if not 0 <= task_policy.maximum_risk <= 5:
        raise ConfigError("maximum_risk must be between 0 and 5")
    if not 0 <= task_policy.maximum_human_dependency <= 5:
        raise ConfigError("maximum_human_dependency must be between 0 and 5")

    return AppConfig(
        run=RunSettings(
            reset_at=reset_at,
            hard_stop_at=hard_stop_at,
            safety_buffer_minutes=safety,
            drain_window_minutes=drain,
            mode=mode,
            output_root=output_root,
            wait_for_replenish=wait_for_replenish,
            quota_replenish_probe_minutes=probe_minutes,
            replan_when_queue_empty=replan_when_queue_empty,
            output_language=output_language,
            report_language=report_language,
        ),
        billing=billing,
        execution=execution,
        sources=tuple(sources),
        task_policy=task_policy,
    )


def assert_execution_environment(
    config: AppConfig,
    env: dict[str, str] | None = None,
    *,
    now: datetime | None = None,
) -> None:
    environment = os.environ if env is None else env
    if not config.execution.enabled:
        raise ConfigError("execution.enabled is false")
    current = now or datetime.now(tz=config.run.reset_at.tzinfo)
    if current.tzinfo is None:
        current = current.replace(tzinfo=config.run.reset_at.tzinfo)
    if config.run.hard_stop_at - current < timedelta(minutes=60):
        raise ConfigError("fewer than 60 minutes remain before hard stop; execution is plan-only")
    present = [name for name in ("OPENAI_API_KEY", "CODEX_API_KEY") if environment.get(name)]
    if present:
        raise ConfigError(f"API key environment variable present: {', '.join(present)}")
    # Resolve every helper the run will need now. A missing binary discovered mid-window
    # burns the window; discovered here it costs nothing.
    worker_binary = (
        config.execution.claude_binary
        if config.execution.provider == "claude"
        else config.execution.codex_binary
    )
    resolved_worker = ""
    for binary in (worker_binary, "git", "ps"):
        try:
            resolved = resolve_executable(binary)
        except ExecutableError as exc:
            raise ConfigError(str(exc)) from exc
        if binary == worker_binary:
            resolved_worker = resolved
    if config.execution.provider == "claude":
        assert_claude_cli_contract(resolved_worker)


def assert_claude_cli_contract(binary: str) -> None:
    """Probe `claude --help` for every flag the read-only worker command needs.

    An installed CLI that silently dropped `--safe-mode` would otherwise be
    discovered only when the worker exits mid-window — or worse, tolerated a
    renamed flag and launched with MCP write tools visible. The probe runs once
    at preflight and fails closed on any missing flag.
    """
    try:
        probe = subprocess.run(
            [binary, "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigError(f"cannot probe {binary} --help: {exc}") from exc
    advertised = probe.stdout + probe.stderr
    # Whole-flag match: "--tools" appears inside the prose of other flags' help
    # text, so a bare substring test could pass with the real flag removed.
    missing = [
        flag for flag in CLAUDE_LOAD_BEARING_FLAGS
        if not re.search(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])", advertised)
    ]
    if missing:
        raise ConfigError(
            f"{binary} --help does not advertise {', '.join(missing)}; "
            "the Claude worker's read-only guarantee depends on these flags, "
            "so the run is refused rather than launched without them"
        )
