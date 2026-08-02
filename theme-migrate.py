#!/usr/bin/env python3
"""Analyze legacy YAML themes before a future HTML conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from library.yaml_theme_migration import (
    YamlThemeMigrationError,
    analyze_yaml_theme,
    format_migration_report,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser(
        "analyze",
        help="inspect a theme without modifying it",
    )
    analyze.add_argument("source", type=Path, help="theme directory or YAML file")
    analyze.add_argument(
        "--json",
        action="store_true",
        help="print the complete machine-readable report",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = analyze_yaml_theme(args.source)
    except YamlThemeMigrationError as exc:
        print(f"Theme analysis failed: {exc}")
        return 2
    if args.json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_migration_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
