# SPDX-License-Identifier: GPL-3.0-or-later
"""Discover and preserve global fonts referenced by YAML themes.

The installer invokes this module with the system Python before replacing the
runtime tree, so it intentionally depends only on the Python standard library.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator


FONT_KEYS = frozenset({"FONT", "AXIS_FONT"})
FONT_SUFFIXES = frozenset({".otf", ".ttc", ".ttf"})


def normalize_font_reference(value: str) -> str | None:
    """Return a safe font path relative to ``res/fonts`` or ``None``."""
    text = str(value or "").strip()
    if not text:
        return None

    if text[:1] in {"'", '"'} and text[-1:] == text[:1]:
        text = text[1:-1].strip()
    else:
        text = text.split(" #", 1)[0].strip()

    text = text.replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts:
        return None
    if path.suffix.casefold() not in FONT_SUFFIXES:
        return None
    return path.as_posix()


def font_references_from_yaml_text(text: str) -> set[str]:
    """Extract the simple scalar font references used by the theme schema."""
    references: set[str] = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.lstrip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if key.strip().upper() not in FONT_KEYS:
            continue
        reference = normalize_font_reference(value)
        if reference:
            references.add(reference)
    return references


def theme_yaml_files(theme_roots: Iterable[Path]) -> Iterator[Path]:
    seen: set[Path] = set()
    for raw_root in theme_roots:
        root = Path(raw_root)
        if root.is_file() and root.suffix.casefold() in {".yaml", ".yml"}:
            candidates = (root,)
        elif root.is_dir():
            candidates = (*root.rglob("theme.yaml"), *root.rglob("theme.yml"))
        else:
            candidates = ()
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield candidate


def collect_theme_font_references(theme_roots: Iterable[Path]) -> set[str]:
    references: set[str] = set()
    for yaml_file in theme_yaml_files(theme_roots):
        try:
            text = yaml_file.read_text(encoding="utf-8")
        except OSError:
            continue
        references.update(font_references_from_yaml_text(text))
    return references


def preserve_referenced_fonts(
    *,
    theme_roots: Iterable[Path],
    fonts_root: Path,
    destination: Path,
) -> tuple[list[str], list[str]]:
    """Copy referenced installed fonts and return ``(copied, missing)`` paths."""
    fonts_root = Path(fonts_root).resolve()
    destination = Path(destination)
    copied: list[str] = []
    missing: list[str] = []

    for reference in sorted(collect_theme_font_references(theme_roots)):
        source = (fonts_root / reference).resolve()
        try:
            source.relative_to(fonts_root)
        except ValueError:
            missing.append(reference)
            continue
        if not source.is_file():
            missing.append(reference)
            continue
        target = destination / reference
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(reference)

    return copied, missing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--themes", type=Path, required=True)
    parser.add_argument("--fonts", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    copied, missing = preserve_referenced_fonts(
        theme_roots=(args.themes,),
        fonts_root=args.fonts,
        destination=args.destination,
    )
    print(f"Preserved {len(copied)} referenced theme font(s).")
    if missing:
        print("Referenced fonts not found: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
