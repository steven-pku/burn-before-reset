from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path


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


def iter_allowlisted_files(
    root: Path,
    *,
    extensions: tuple[str, ...],
    exclude_fragments: tuple[str, ...],
) -> Iterator[Path]:
    root = root.resolve(strict=True)
    excluded = {fragment.lower() for fragment in exclude_fragments}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        safe_dirs: list[str] = []
        for dirname in sorted(dirnames):
            candidate = current / dirname
            relative_parts = {part.lower() for part in candidate.relative_to(root).parts}
            if candidate.is_symlink() or relative_parts & excluded or is_secret_like(candidate):
                continue
            safe_dirs.append(dirname)
        dirnames[:] = safe_dirs
        for filename in sorted(filenames):
            candidate = current / filename
            if candidate.is_symlink() or is_secret_like(candidate):
                continue
            relative_parts = {part.lower() for part in candidate.relative_to(root).parts}
            if relative_parts & excluded:
                continue
            if extensions and candidate.suffix.lower() not in extensions:
                continue
            if not is_within(candidate, root):
                continue
            yield candidate
