from __future__ import annotations

import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple


class ExecutableError(ValueError):
    """Raised when a required helper binary cannot be resolved."""


def resolve_executable(name: str) -> str:
    """Resolve a helper binary to an absolute path before running it.

    Passing a bare name leaves the choice of binary to whatever PATH happens to
    hold, which is the wrong posture for a tool that fails closed on every other
    uncertainty. Resolving here also turns "codex is not installed" into an error
    at preflight rather than one discovered mid-window with the clock running.
    """
    if os.path.isabs(name):
        if os.path.isfile(name) and os.access(name, os.X_OK):
            return name
        raise ExecutableError(f"{name} is not an executable file")
    found = shutil.which(name)
    if not found:
        raise ExecutableError(f"{name} was not found on PATH")
    return found


SECRET_NAMES = {
    ".env",
    "auth.json",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
    "known_hosts",
}
SECRET_PARTS = {".ssh", ".gnupg", "keychain", "cookies", "browser data"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


def is_within(path: Path, root: Path) -> bool:
    resolved = path.resolve(strict=False)
    root_resolved = root.resolve(strict=False)
    return resolved == root_resolved or resolved.is_relative_to(root_resolved)


def is_secret_like(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    return (
        name in SECRET_NAMES
        or path.suffix.lower() in SECRET_SUFFIXES
        or bool(parts & SECRET_PARTS)
        or name.startswith(".env.")
    )


def _normalised_fragments(exclude_fragments: tuple[str, ...]) -> tuple[str, ...]:
    """Lowercase, de-blanked exclusion entries.

    A blank entry is a substring of every path and would silently empty a source
    root. `load_config` rejects one outright; dropping it here keeps any other
    caller from tripping over the same edge.
    """
    return tuple(sorted({fragment.strip().lower() for fragment in exclude_fragments if fragment.strip()}))


def _match_text(relative: Path) -> str:
    """The root-relative path an entry is matched against, wrapped in separators.

    One rule does two jobs. An entry is a case-insensitive substring of this text,
    so `finance` catches `Finance/`, `2026-finance-review.md` and the flattened
    session segment `-Users-me-Documents-Projects-Finance` alike — which is what
    the option is named for, and the only form that can express "exclude this
    project" on a session source. Writing a `/` at either end of the entry anchors
    it to a path-segment boundary, because the text it is matched against carries
    those separators: `/.git/` catches the `.git` directory at any depth and does
    not catch `.github/`, while a bare `.git` catches both. Without the wrapping
    an anchored entry could never match the first or last segment.
    """
    return "/" + relative.as_posix().lower() + "/"


def _matching_fragments(relative: Path, fragments: tuple[str, ...]) -> list[str]:
    """Every entry that excludes this root-relative path.

    All matches, not the first: the audit credits each entry that would have
    caught a path. Stopping at the first would report a working entry as matching
    nothing whenever another entry happened to sort ahead of it — which is the
    same "looks inert but is not" confusion the audit exists to remove.
    """
    text = _match_text(relative)
    return [fragment for fragment in fragments if fragment in text]


def _is_excluded(relative: Path, fragments: tuple[str, ...]) -> bool:
    """Whether any entry excludes this root-relative path. Stops at the first hit."""
    text = _match_text(relative)
    return any(fragment in text for fragment in fragments)


def iter_allowlisted_files(
    root: Path,
    *,
    extensions: tuple[str, ...],
    exclude_fragments: tuple[str, ...],
) -> Iterator[Path]:
    root = root.resolve(strict=True)
    excluded = _normalised_fragments(exclude_fragments)
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        safe_dirs: list[str] = []
        for dirname in sorted(dirnames):
            candidate = current / dirname
            if candidate.is_symlink() or is_secret_like(candidate):
                continue
            if _is_excluded(candidate.relative_to(root), excluded):
                continue
            safe_dirs.append(dirname)
        dirnames[:] = safe_dirs
        for filename in sorted(filenames):
            candidate = current / filename
            if candidate.is_symlink() or is_secret_like(candidate):
                continue
            if _is_excluded(candidate.relative_to(root), excluded):
                continue
            if extensions and candidate.suffix.lower() not in extensions:
                continue
            if not is_within(candidate, root):
                continue
            yield candidate


# How a session-recording CLI turns a working directory into a single directory
# name: every character that is not a letter or a digit becomes a hyphen, so
# `/Users/me/runs/run-1/staging/task-2` is stored as
# `-Users-me-runs-run-1-staging-task-2`. Observed on disk rather than published,
# and applied to both sides of every comparison so a disagreement about any one
# character class cannot make the check miss.
_FLATTEN = re.compile(r"[^A-Za-z0-9]")


def flatten_workspace_name(value: str | Path) -> str:
    """Collapse a path into the single lowercase segment a session directory uses."""
    return _FLATTEN.sub("-", str(value)).lower()


def is_own_output_location(candidate: Path, output_root: Path) -> bool:
    """True when `candidate` is inside `output_root`, or encodes a path that is.

    A worker runs pinned to `<output_root>/<run>/staging/<task>`, and its own
    transcript is written to a directory named after that working directory. Left
    unfiltered the planner reads those transcripts back as fresh source material
    and queues work against the tool's own exhaust — which is what happened on
    2026-09-08. Matching the *encoded* form is what makes this hold for a run
    other than the current one, including a previous night's run sharing the same
    output root.

    The encoding is lossy: `/a/b/c` and `/a/b-c` flatten alike, so a sibling whose
    name extends the output root's own (`~/runs-archive` beside `~/runs`) is
    excluded too. That is the fail-closed side of an ambiguity the name cannot
    resolve; requiring the separator is the tightest rule the encoding supports.
    """
    if is_within(candidate, output_root):
        return True
    marker = flatten_workspace_name(output_root.resolve(strict=False))
    return any(
        flattened == marker or flattened.startswith(marker + "-")
        for flattened in (flatten_workspace_name(part) for part in candidate.parts)
    )


class ExclusionAudit(NamedTuple):
    """What the exclusion entries catch under one root, and whether the walk finished.

    `truncated` is not decoration: a walk that stopped early reports entries as
    matching nothing when they may match further down, which is the same false
    "this exclusion is inert" reading the audit exists to prevent. Callers must
    say so rather than print a clean result over a partial walk.
    """

    matches: dict[str, list[str]]
    truncated: bool


def audit_exclusions(root: Path, exclude_fragments: tuple[str, ...], *, limit: int = 200000) -> ExclusionAudit:
    """What each `exclude_fragments` entry actually catches under one source root.

    An exclusion that matches nothing is indistinguishable from an exclusion that
    is working, which is how a deliberately added safety entry ran inert for a
    whole night on 2026-09-08. Reporting the matches — including the empty ones —
    is what turns that into something the operator can see before launching.

    Directory names and file names only; nothing is read. `limit` bounds the walk
    so auditing a large root cannot become the slow part of a preflight.
    """
    fragments = _normalised_fragments(exclude_fragments)
    matches: dict[str, list[str]] = {fragment: [] for fragment in fragments}
    empty = ExclusionAudit({fragment: [] for fragment in exclude_fragments}, False)
    if not fragments:
        return empty
    try:
        root = root.resolve(strict=True)
    except OSError:
        return empty
    visited = 0
    truncated = False
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        kept: list[str] = []
        for dirname in sorted(dirnames):
            candidate = current / dirname
            if candidate.is_symlink() or is_secret_like(candidate):
                continue
            visited += 1
            relative = candidate.relative_to(root)
            hits = _matching_fragments(relative, fragments)
            if not hits:
                kept.append(dirname)
                continue
            # Pruned, exactly as the walker prunes it: nothing below an excluded
            # directory is reachable, so nothing below it can match either.
            for hit in hits:
                matches[hit].append(relative.as_posix())
        dirnames[:] = kept
        for filename in sorted(filenames):
            candidate = current / filename
            if candidate.is_symlink() or is_secret_like(candidate):
                continue
            visited += 1
            relative = candidate.relative_to(root)
            for hit in _matching_fragments(relative, fragments):
                matches[hit].append(relative.as_posix())
        if visited >= limit:
            truncated = True
            break
    # Report against the entries as the operator wrote them, not the normalised form.
    return ExclusionAudit(
        {original: list(matches.get(original.strip().lower(), [])) for original in exclude_fragments},
        truncated,
    )
