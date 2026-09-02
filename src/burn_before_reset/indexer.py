from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from .config import SourceSettings
from .model import SourceRef
from .paths import ExecutableError, iter_allowlisted_files, resolve_executable

SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("todo", re.compile(r"(?:\bTODO\b|待办|未完成)", re.IGNORECASE)),
    ("fixme", re.compile(r"(?:\bFIXME\b|待修|修复)", re.IGNORECASE)),
    ("next-step", re.compile(r"(?:下一步|next\s+step|后续|继续做)", re.IGNORECASE)),
    ("unverified", re.compile(r"(?:待验证|未验证|需要验证|pending\s+verification)", re.IGNORECASE)),
    ("blocked", re.compile(r"(?:阻塞|blocked|卡点)", re.IGNORECASE)),
    ("decision", re.compile(r"(?:需要.{0,8}决定|待决定|decision\s+needed)", re.IGNORECASE)),
)

EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def _redact(value: str, root: Path) -> str:
    clean = value.replace(str(root), "<SOURCE_ROOT>")
    clean = EMAIL.sub("<EMAIL>", clean)
    return " ".join(clean.strip().split())[:300]


def _title(text: str, fallback: str) -> str:
    frontmatter = re.search(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$", text[:4096])
    if frontmatter:
        return frontmatter.group(1).strip()[:120]
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", text[:8192])
    return (heading.group(1).strip() if heading else fallback)[:120]


def _read_bounded(path: Path, maximum: int) -> tuple[str, bytes]:
    with path.open("rb") as handle:
        raw = handle.read(maximum)
    return raw.decode("utf-8", errors="replace"), raw


def _content_digest(raw: bytes, size: int) -> str:
    # Size first: the indexer reads a bounded prefix, so an append past the bound
    # would otherwise leave the digest unchanged.
    return hashlib.sha256(f"{size}\0".encode("ascii") + raw).hexdigest()[:16]


def _is_codex_session(text: str) -> bool:
    first = text.splitlines()[0] if text.splitlines() else ""
    try:
        record = json.loads(first)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(record, dict)
        and record.get("type") == "session_meta"
        and isinstance(record.get("payload"), dict)
    )


def _is_claude_session(text: str) -> bool:
    """A Claude Code transcript: JSONL whose first record is a typed entry bound to a
    session. The shape is observed, not published — every transcript seen so far opens
    with a string `type` and a `sessionId`, `cwd` or `uuid`; a data export or a log that
    merely ends in .jsonl does not, and must not be read as a session."""
    first = text.splitlines()[0] if text.splitlines() else ""
    try:
        record = json.loads(first)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(record, dict)
        and isinstance(record.get("type"), str)
        and any(key in record for key in ("sessionId", "cwd", "uuid"))
    )


def _signals_and_snippets(text: str, root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    found: set[str] = set()
    snippets: list[str] = []
    for line in text.splitlines():
        line_signals = [name for name, pattern in SIGNALS if pattern.search(line)]
        if not line_signals:
            continue
        found.update(line_signals)
        if len(snippets) < 5:
            snippets.append(_redact(line, root))
    return tuple(sorted(found)), tuple(snippets)


def _git_status(source: SourceSettings) -> SourceRef | None:
    if source.source_type != "git" or not (source.root / ".git").exists():
        return None
    try:
        # --no-optional-locks stops `status` from refreshing the on-disk index.
        # Without it, git rewrites `.git/index` and changes its mtime, which is a
        # write inside a source root the planner promises never to modify.
        result = subprocess.run(
            [resolve_executable("git"), "--no-optional-locks", "-C", str(source.root), "status", "--porcelain", "--untracked-files=all"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired, ExecutableError):
        return None
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    # The freshness stamp is the newest dirty *file*, not the repository root: a
    # directory's mtime does not move when a tracked file's content changes, so a
    # root-based stamp let cross-run de-duplication skip a repository whose
    # uncommitted work had moved on (fourth audit round).
    stamps: list[float] = []
    for line in lines:
        target = line[3:].strip()
        if " -> " in target:
            target = target.split(" -> ", 1)[1]
        target = target.strip('"')
        try:
            stamps.append((source.root / target).stat().st_mtime)
        except OSError:
            continue
    newest = max(stamps) if stamps else source.root.stat().st_mtime
    modified = datetime.fromtimestamp(newest).astimezone().isoformat(timespec="seconds")
    # The dirty *set* is the identity: a deletion, an edit to a file that is not
    # the newest one, or a new untracked path all change it while the newest
    # mtime may not. De-duplication compares this alongside the stamp.
    fingerprint = hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()[:16]
    return SourceRef(
        source_type="git",
        root=str(source.root),
        path=".",
        modified_at=modified,
        title=source.root.name,
        signals=("git-dirty",),
        snippets=tuple(_redact(line, source.root) for line in lines[:5]),
        fingerprint=fingerprint,
    )


def index_source(source: SourceSettings) -> list[SourceRef]:
    records: list[SourceRef] = []
    git_record = _git_status(source)
    if git_record:
        records.append(git_record)
    for path in iter_allowlisted_files(
        source.root,
        extensions=source.extensions,
        exclude_fragments=source.exclude_fragments,
    ):
        try:
            text, raw = _read_bounded(path, source.max_file_bytes)
            stat = path.stat()
        except (OSError, UnicodeError):
            continue
        if source.source_type == "codex_sessions" and not _is_codex_session(text):
            continue
        if source.source_type == "claude_sessions" and not _is_claude_session(text):
            continue
        signals, snippets = _signals_and_snippets(text, source.root)
        if not signals:
            continue
        records.append(
            SourceRef(
                source_type=source.source_type,
                root=str(source.root),
                path=str(path.relative_to(source.root)),
                modified_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                title=_title(text, path.stem),
                signals=signals,
                snippets=snippets,
                content_sha256=_content_digest(raw, stat.st_size),
            )
        )
    return records


def index_all(sources: tuple[SourceSettings, ...]) -> list[SourceRef]:
    records: list[SourceRef] = []
    for source in sources:
        records.extend(index_source(source))
    return sorted(records, key=lambda item: (item.modified_at, item.path), reverse=True)
