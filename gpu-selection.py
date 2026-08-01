#!/usr/bin/env python3
"""Inspect or configure the AMD GPU used by the sensor backend."""

from __future__ import annotations

import argparse
import json
from typing import Any

from library.gpu_selection import (
    GpuPreference,
    enumerate_amd_gpus,
    load_preference,
    preference_for_candidate,
    save_preference,
    selection_summary,
)

try:
    import pyamdgpuinfo
except Exception:
    pyamdgpuinfo = None


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subparsers = result.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list detected AMD adapters")
    subparsers.add_parser("show", help="show the effective preference and selection")

    setter = subparsers.add_parser("set", help="persist auto or a detected index")
    setter.add_argument("selection", help="auto or a zero-based AMD GPU index")
    return result


def preference_for(selection: str) -> GpuPreference:
    value = str(selection or "").strip().lower()
    if value == "auto":
        return GpuPreference()
    try:
        index = int(value)
    except ValueError as exc:
        raise ValueError("Selection must be 'auto' or a non-negative index") from exc
    if index < 0:
        raise ValueError("GPU index must be zero or greater")
    return GpuPreference(mode="index", amd_index=index)


def main(argv: Any = None) -> int:
    args = parser().parse_args(argv)

    if args.command == "list":
        payload = [candidate.to_dict() for candidate in enumerate_amd_gpus(pyamdgpuinfo)]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload else 1

    if args.command == "show":
        print(json.dumps(selection_summary(pyamdgpuinfo), indent=2, sort_keys=True))
        return 0

    try:
        preference = preference_for(args.selection)
    except ValueError as exc:
        parser().error(str(exc))
        return 2

    candidates = enumerate_amd_gpus(pyamdgpuinfo)
    if preference.mode == "index":
        candidate = next(
            (
                candidate
                for candidate in candidates
                if candidate.index == preference.amd_index
            ),
            None,
        )
        if candidate is None:
            available = [candidate.index for candidate in candidates]
            print(
                f"AMD GPU index {preference.amd_index} is not currently available. "
                f"Detected indices: {available}"
            )
            return 2
        preference = preference_for_candidate(candidate)

    path = save_preference(preference)
    effective = load_preference(path)
    print(f"Saved {effective.mode} AMD GPU preference to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
