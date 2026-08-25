from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Tests must not depend on codex or claude being installed on the machine running
# them — the first real CI run failed on exactly that assumption. The interpreter
# binary is an absolute, always-executable stand-in for tests that never launch a
# worker; tests that do launch one pass their own fake script explicitly.
HERMETIC_BINARY = sys.executable


def write_config(
    path: Path,
    source: Path,
    output: Path,
    *,
    source_type: str = "markdown",
    enabled: bool = False,
    codex_binary: str = HERMETIC_BINARY,
    reset_at: datetime | None = None,
    safety: int = 15,
    mode: str = "safe",
    max_tasks: int = 3,
) -> Path:
    reset = reset_at or datetime.now(UTC) + timedelta(hours=3)
    path.write_text(
        f"""[run]
reset_at = "{reset.isoformat()}"
safety_buffer_minutes = {safety}
drain_window_minutes = 30
mode = "{mode}"
output_root = "{output}"

[billing]
subscription_auth_only = true
user_asserts_credit_balance_zero = true
user_asserts_auto_top_up_off = true
allow_api_key = false
allow_paid_credits = false
allow_provider_fallback = false

[execution]
enabled = {str(enabled).lower()}
codex_binary = "{codex_binary}"
max_tasks = {max_tasks}
task_timeout_seconds = 20
sigint_grace_seconds = 0.5
sigterm_grace_seconds = 0.5

[task_policy]
minimum_score = 12
maximum_risk = 2
maximum_human_dependency = 1
max_candidates = 50

[[sources]]
type = "{source_type}"
root = "{source}"
extensions = [".md", ".txt", ".jsonl", ".py"]
exclude_fragments = [".git", "private"]
max_file_bytes = 65536
""",
        encoding="utf-8",
    )
    return path
