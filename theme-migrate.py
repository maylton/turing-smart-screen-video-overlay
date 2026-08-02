#!/usr/bin/env python3
"""Analyze and non-destructively convert legacy YAML themes to HTML drafts."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from library.theme_engine import ThemeValidationError
from library.theme_package import ThemePackageError
from library.yaml_theme_converter import (
    convert_yaml_theme,
    converted_theme_name,
)
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

    convert = subparsers.add_parser(
        "convert",
        help="create a new HTML directory or portable .theme draft",
    )
    convert.add_argument("source", type=Path, help="theme directory or YAML file")
    convert.add_argument("destination", type=Path, help="new directory or .theme file")
    convert.add_argument(
        "--allow-partial",
        action="store_true",
        help="skip unsupported overlays and record them in migration-report.json",
    )
    convert.add_argument("--json", action="store_true", help="print JSON result")

    batch = subparsers.add_parser(
        "batch",
        help="convert every automatic theme below a themes directory",
    )
    batch.add_argument("source", type=Path, help="directory containing theme folders")
    batch.add_argument("destination", type=Path, help="new output directory")
    batch.add_argument(
        "--allow-partial",
        action="store_true",
        help="also create partial drafts for assisted/manual reports",
    )
    batch.add_argument("--json", action="store_true", help="print JSON result")
    return result


def _batch_sources(root: Path) -> tuple[Path, ...]:
    source = root.expanduser().resolve()
    if not source.is_dir():
        raise YamlThemeMigrationError(f"Theme collection does not exist: {source}")
    return tuple(
        sorted(
            {
                path.parent
                for path in (*source.glob("*/theme.yaml"), *source.glob("*/theme.yml"))
            }
        )
    )


def _batch_convert(args) -> dict[str, object]:
    destination = args.destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Batch destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.batch-",
            dir=str(destination.parent),
        )
    )
    converted = []
    skipped = []
    try:
        for source in _batch_sources(args.source):
            report = analyze_yaml_theme(source)
            if report.readiness != "automatic" and not args.allow_partial:
                skipped.append(
                    {
                        "theme": report.theme_name,
                        "readiness": report.readiness,
                    }
                )
                continue
            if args.allow_partial and not report.ready_overlays:
                skipped.append(
                    {
                        "theme": report.theme_name,
                        "readiness": report.readiness,
                        "reason": "no-supported-overlays",
                    }
                )
                continue
            target = temporary / f"{converted_theme_name(report.theme_name)}.theme"
            result = convert_yaml_theme(
                source,
                target,
                allow_partial=args.allow_partial,
            )
            converted_result = result.as_dict()
            converted_result["output"] = str(destination / target.name)
            converted.append(converted_result)
        payload: dict[str, object] = {
            "source": str(args.source.expanduser().resolve()),
            "destination": str(destination),
            "converted": converted,
            "skipped": skipped,
        }
        (temporary / "batch-report.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return payload
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "analyze":
            report = analyze_yaml_theme(args.source)
            if args.json:
                print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
            else:
                print(format_migration_report(report))
            return 0
        if args.command == "convert":
            result = convert_yaml_theme(
                args.source,
                args.destination,
                allow_partial=args.allow_partial,
            )
            if args.json:
                print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
            else:
                print(result.output)
            return 0
        payload = _batch_convert(args)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload["destination"])
        return 0
    except (
        YamlThemeMigrationError,
        ThemeValidationError,
        ThemePackageError,
        FileExistsError,
        OSError,
    ) as exc:
        print(f"Theme migration failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
