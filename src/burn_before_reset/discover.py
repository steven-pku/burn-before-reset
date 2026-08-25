from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .paths import is_secret_like

# Where the traces of recent work actually live on a developer's machine, vault
# or no vault: agent session logs first — they exist for every Claude/Codex user
# by definition — then the working trees those sessions touched.
SKIP_DIR_NAMES = {
    "node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__",
    "Library", "Applications", "Pictures", "Music", "Movies",
}
WORK_BASES = ("Documents", "Desktop", "Projects", "dev", "src", "code", "repos")
MAX_WALK_DIRS = 4000
MAX_PROPOSALS = 15
RECENT_DAYS = 90


@dataclass(frozen=True)
class SourceProposal:
    source_type: str
    root: Path
    evidence: str
    last_activity: float

    def toml_block(self) -> str:
        extensions = {
            "claude_sessions": '[".jsonl"]',
            "codex_sessions": '[".jsonl"]',
            "git": '[".md", ".py", ".ts", ".tsx", ".js", ".go", ".rs"]',
            "markdown": '[".md"]',
        }[self.source_type]
        return (
            f"# {self.evidence} · last activity {datetime.fromtimestamp(self.last_activity).strftime('%Y-%m-%d')}\n"
            f"[[sources]]\n"
            f'type = "{self.source_type}"\n'
            f'root = "{self.root}"\n'
            f"extensions = {extensions}\n"
            f'exclude_fragments = [".git", ".obsidian", "node_modules", "private", "finance", "health", "clients"]\n'
        )


def _recent(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _session_proposal(root: Path, source_type: str, label: str) -> SourceProposal | None:
    if not root.is_dir():
        return None
    newest, count = 0.0, 0
    for entry in root.rglob("*.jsonl"):
        count += 1
        newest = max(newest, _recent(entry))
        if count >= 500:
            break
    if count == 0:
        return None
    return SourceProposal(source_type, root, f"{label}: {count}{'+' if count >= 500 else ''} session files", newest)


def _work_tree_proposals(home: Path, now: float) -> list[SourceProposal]:
    proposals: list[SourceProposal] = []
    seen_roots: list[Path] = []
    visited = 0
    cutoff = now - RECENT_DAYS * 86400
    for base_name in WORK_BASES:
        base = home / base_name
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            current = Path(dirpath)
            visited += 1
            if visited > MAX_WALK_DIRS:
                dirnames[:] = []
                continue
            depth = len(current.relative_to(base).parts)
            dirnames[:] = [
                name for name in sorted(dirnames)
                if depth < 3
                and not name.startswith(".")
                and name not in SKIP_DIR_NAMES
                and not is_secret_like(current / name)
            ]
            if any(current.is_relative_to(root) for root in seen_roots):
                dirnames[:] = []
                continue
            markdown = [name for name in filenames if name.endswith(".md")]
            is_git = (current / ".git").is_dir()
            if not is_git and len(markdown) < 5:
                continue
            newest = max((_recent(current / name) for name in markdown), default=_recent(current))
            if newest < cutoff:
                continue
            seen_roots.append(current)
            dirnames[:] = []
            if is_git:
                proposals.append(SourceProposal("git", current, f"git repository, {len(markdown)} markdown files", newest))
            else:
                proposals.append(SourceProposal("markdown", current, f"{len(markdown)} markdown files", newest))
    return proposals


def discover_sources(home: Path | None = None, *, now: float | None = None) -> list[SourceProposal]:
    """Propose read-only source roots from the traces on this machine.

    Proposals only: nothing is written, and choosing among them — plus tightening
    the exclude list — stays a human or agent judgment upstream of the config.
    """
    home = home or Path.home()
    current = now if now is not None else datetime.now().timestamp()
    proposals: list[SourceProposal] = []
    claude = _session_proposal(home / ".claude" / "projects", "claude_sessions", "Claude Code session logs")
    if claude:
        proposals.append(claude)
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    codex = _session_proposal(codex_home / "sessions", "codex_sessions", "Codex session logs")
    if codex:
        proposals.append(codex)
    proposals.extend(_work_tree_proposals(home, current))
    proposals.sort(key=lambda item: -item.last_activity)
    return proposals[:MAX_PROPOSALS]


def render_proposals(proposals: list[SourceProposal]) -> str:
    if not proposals:
        return "No candidate sources found. Point [[sources]] at a directory by hand.\n"
    lines = [
        "# Proposed read-only sources, most recently active first.",
        "# Review before use: drop anything sensitive, tighten exclude_fragments.",
        "",
    ]
    lines.extend(proposal.toml_block() for proposal in proposals)
    return "\n".join(lines)
