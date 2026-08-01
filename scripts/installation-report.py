#!/usr/bin/env python3
"""Verify a project tree and write/read installation release metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from library.release_info import release_summary, validate_project_tree, write_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="validate required application files")
    verify.add_argument("root", type=Path)

    write = subparsers.add_parser("write", help="write installed release metadata")
    write.add_argument("--source", type=Path, required=True)
    write.add_argument("--install-root", type=Path, required=True)
    write.add_argument("--mode", choices=("user", "system", "portable"), required=True)

    show = subparsers.add_parser("show", help="print release metadata as JSON")
    show.add_argument("root", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "verify":
        missing = validate_project_tree(args.root)
        if missing:
            print("Incomplete Turing Smart Screen tree:", file=sys.stderr)
            for relative in missing:
                print(f"  - {relative}", file=sys.stderr)
            return 2
        print(f"Project tree OK: {args.root.resolve()}")
        return 0

    if args.command == "write":
        missing = validate_project_tree(args.install_root)
        if missing:
            print("Refusing to record an incomplete installation:", file=sys.stderr)
            for relative in missing:
                print(f"  - {relative}", file=sys.stderr)
            return 2
        destination = write_metadata(
            source_root=args.source,
            install_root=args.install_root,
            install_mode=args.mode,
        )
        print(destination)
        return 0

    if args.command == "show":
        print(json.dumps(release_summary(args.root), indent=2, sort_keys=True))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
