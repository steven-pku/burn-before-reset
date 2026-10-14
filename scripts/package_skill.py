#!/usr/bin/env python3
"""Package the bounded Skill as ordinary files; no model or network required."""
from __future__ import annotations

import argparse
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / f'burn-before-reset-skill-{version}.zip'

    def files(path: Path, ancestors: tuple[Path, ...] = ()):
        resolved = path.resolve(strict=True)
        if resolved in ancestors:
            raise ValueError(f'recursive Skill resource: {path}')
        if resolved.is_dir():
            for child in sorted(path.iterdir()):
                if not child.name.startswith('.') and child.name != '__pycache__' and not child.name.endswith('.egg-info'):
                    yield from files(child, (*ancestors, resolved))
        else:
            yield path

    with ZipFile(target, 'w', compression=ZIP_DEFLATED) as archive:
        for path in files(ROOT / 'skill'):
            archive.write(path, Path('burn-before-reset') / path.relative_to(ROOT / 'skill'))
    print(target.resolve())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
