from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from .config import SourceSettings
from .model import SourceRef
from .paths import (
    ExecutableError,
    is_own_output_location,
    is_within,
    iter_allowlisted_files,
    resolve_executable,
)

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


def _declared_cwd(text: str) -> str | None:
    """The working directory a session transcript records for itself, if any.

    Codex writes it as `session_meta.payload.cwd`; a Claude transcript carries it
    on some record shapes and not others. It is read where present because it is
    exact, and never relied on alone because it is often absent.
    """
    first = text.splitlines()[0] if text.splitlines() else ""
    try:
        record = json.loads(first)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict):
        return None
    payload = record.get("payload")
    for holder in (record, payload if isinstance(payload, dict) else {}):
        value = holder.get("cwd")
        if isinstance(value, str) and value:
            return value
    return None


def _is_own_output(path: Path, text: str, exhaust_root: Path) -> bool:
    """Whether this file is something a run of this tool produced.

    Two independent detectors, unioned so either one alone is enough: the file's
    own location — including the flattened working-directory name a session
    directory is given — and the working directory the transcript declares. On
    2026-09-08 a re-planning round queued a task against a worker transcript from
    round 2 of the same run; it burned the full task timeout, timed out, and
    stopped the run 79 minutes early. Seven further tasks that night completed
    against the same exhaust and were reported as validated work. Neither
    detector depends on the operator having written an exclusion, and both cover
    any run under `output_root`, not only the current one.
    """
    if is_own_output_location(path, exhaust_root):
        return True
    declared = _declared_cwd(text)
    return bool(declared) and is_within(Path(declared), exhaust_root)


def _signals_and_snippets(text: str, root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    found: set[str] = set()
    snippets: list[str] = []
    fence_char = ""
    fence_length = 0
    for line in text.splitlines():
        stripped = line.lstrip()
        fence = re.match(r"(`{3,}|~{3,})", stripped)
        if fence:
            marker = fence.group(1)
            if not fence_char:
                fence_char, fence_length = marker[0], len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = ""
            continue
        if fence_char or stripped.startswith(">"):
            continue
        if re.match(r"(?:[-*+]|\d+[.)])\s+\[[xX-]\]", stripped):
            continue
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


def index_source(
    source: SourceSettings,
    *,
    exhaust_root: Path | None = None,
    own_output: list[str] | None = None,
) -> list[SourceRef]:
    """Index one source root.

    `exhaust_root` is the run output root. Anything this tool wrote there — in
    particular its own workers' session transcripts — is dropped by construction
    rather than by an operator-supplied exclusion, and each drop is appended to
    `own_output` so the run plan can name it instead of silently losing it.
    """
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
        if exhaust_root is not None and _is_own_output(path, text, exhaust_root):
            if own_output is not None:
                own_output.append(str(path.relative_to(source.root)))
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


def index_all(
    sources: tuple[SourceSettings, ...],
    *,
    exhaust_root: Path | None = None,
    own_output: list[str] | None = None,
) -> list[SourceRef]:
    records: list[SourceRef] = []
    for source in sources:
        records.extend(index_source(source, exhaust_root=exhaust_root, own_output=own_output))
    return sorted(records, key=lambda item: (item.modified_at, item.path), reverse=True)
