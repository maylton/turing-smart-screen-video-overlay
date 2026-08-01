#!/usr/bin/env python3
"""List or restore Theme Editor YAML backups."""

from __future__ import annotations

import argparse
from pathlib import Path

from library.theme_editor_backups import backup_files, restore_backup


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list")
    listing.add_argument("theme_file", type=Path)

    restore = subparsers.add_parser("restore")
    restore.add_argument("theme_file", type=Path)
    restore.add_argument("backup", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.command == "list":
        for path in backup_files(args.theme_file):
            print(path)
        return 0

    restore_backup(args.backup, args.theme_file)
    print(args.theme_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
