#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-safe, structured CLI for native Rev. C video operations."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any

from library.runtime import DeviceBusyError, DeviceLock
from library.video_media import (
    IncompatibleMediaError,
    MediaProbeError,
    normalize_remote_path,
    probe_video,
    remote_path_for_local,
)

ROOT = Path(__file__).resolve().parent
BACKEND_MODULE = ROOT / "video_manager_backend.py"


def load_backend():
    spec = importlib.util.spec_from_file_location(
        "turing_video_manager_backend", BACKEND_MODULE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BACKEND_MODULE.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Native video manager for Turing Smart Screen Rev. C."
    )
    parser.add_argument(
        "--port",
        default="AUTO",
        help='Serial port, for example /dev/ttyACM0. Default: "AUTO".',
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a stable JSON response for graphical clients.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--internal", action="store_true")

    size_parser = subparsers.add_parser("size")
    size_parser.add_argument("remote")

    upload_parser = subparsers.add_parser("upload")
    upload_parser.add_argument("local", type=Path)
    upload_parser.add_argument("--remote")
    upload_parser.add_argument("--internal", action="store_true")
    upload_parser.add_argument("--overwrite", action="store_true")
    upload_parser.add_argument("--play", action="store_true")
    upload_parser.add_argument("--packet-delay", type=float, default=0.0)
    upload_parser.add_argument(
        "--skip-probe",
        action="store_true",
        help="Upload without compatibility validation (advanced use only).",
    )

    delete_parser = subparsers.add_parser("delete")
    delete_parser.add_argument("remote")

    play_parser = subparsers.add_parser("play")
    play_parser.add_argument("remote")

    subparsers.add_parser("stop")

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("local", type=Path)
    return parser


def human_size(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB")
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{value} B"


def success(command: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "command": command, "data": data}


def failure(command: str, exc: Exception) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "command": command,
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
    }
    if isinstance(exc, DeviceBusyError):
        data["error"]["owner"] = {
            "pid": exc.owner.pid,
            "role": exc.owner.role,
            "root": exc.owner.root,
        }
    if isinstance(exc, IncompatibleMediaError):
        data["error"]["probe"] = exc.probe.to_dict()
    return data


def print_response(payload: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return

    if not payload.get("ok"):
        print(payload["error"]["message"], file=sys.stderr)
        return

    command = payload["command"]
    data = payload["data"]
    if command == "list":
        print("Directories:", data["directories"] or "(none)")
        print("Files:", data["files"] or "(none)")
    elif command == "size":
        print(f"{data['bytes']} bytes ({data['human']})")
    elif command == "probe":
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(data.get("message", "Operation completed."))


def run_probe(args) -> dict[str, Any]:
    probe = probe_video(args.local)
    return success("probe", probe.to_dict())


def run_device_command(args, backend) -> dict[str, Any]:
    manager = None
    captured = io.StringIO()
    output_context = (
        contextlib.redirect_stdout(captured)
        if args.json
        else contextlib.nullcontext()
    )

    try:
        manager = backend.VideoManager(com_port=args.port)
        with output_context:
            if args.command == "self-test":
                backend.run_self_test(manager)
                data = {"message": "Self-test completed successfully."}

            elif args.command == "list":
                directories, files = manager.list_videos(
                    internal=args.internal
                )
                data = {
                    "storage": "internal" if args.internal else "sd",
                    "directories": directories,
                    "files": files,
                }

            elif args.command == "size":
                remote = normalize_remote_path(args.remote)
                size = manager.get_size(remote)
                data = {
                    "remote": remote,
                    "bytes": size,
                    "human": human_size(size),
                }

            elif args.command == "upload":
                local = args.local.expanduser().resolve()
                if not local.is_file():
                    raise FileNotFoundError(
                        f"Local media file was not found: {local}"
                    )
                remote = normalize_remote_path(
                    args.remote
                    or remote_path_for_local(local, internal=args.internal)
                )
                media_probe = None
                if not args.skip_probe:
                    media_probe = probe_video(local)
                    if not media_probe.compatible:
                        raise IncompatibleMediaError(media_probe)

                manager.upload(
                    local_path=local,
                    remote_path=remote,
                    overwrite=args.overwrite,
                    packet_delay=max(0.0, args.packet_delay),
                )
                if args.play:
                    manager.play(remote)
                remote_size = manager.get_size(remote)
                data = {
                    "message": f"Upload complete: {local.name}",
                    "local": str(local),
                    "remote": remote,
                    "bytes": remote_size,
                    "human": human_size(remote_size),
                    "probe": (
                        media_probe.to_dict() if media_probe is not None else None
                    ),
                    "playing": bool(args.play),
                }

            elif args.command == "delete":
                remote = normalize_remote_path(args.remote)
                manager.delete(remote)
                data = {
                    "message": f"Deleted {remote}",
                    "remote": remote,
                }

            elif args.command == "play":
                remote = normalize_remote_path(args.remote)
                manager.play(remote)
                data = {
                    "message": f"Playing {remote}",
                    "remote": remote,
                }

            elif args.command == "stop":
                manager.stop()
                data = {"message": "Video stopped."}

            else:  # pragma: no cover - argparse enforces commands
                raise RuntimeError(f"Unsupported command: {args.command}")

        if args.json and captured.getvalue().strip():
            data["backend_log"] = captured.getvalue().strip()
        return success(args.command, data)
    finally:
        if manager is not None:
            manager.close()


def cli() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "probe":
            payload = run_probe(args)
        else:
            backend = load_backend()
            with DeviceLock(role="video-manager", root=ROOT):
                payload = run_device_command(args, backend)
        print_response(payload, args.json)
        return 0
    except DeviceBusyError as exc:
        print_response(failure(args.command, exc), args.json)
        return 3
    except (IncompatibleMediaError, MediaProbeError) as exc:
        print_response(failure(args.command, exc), args.json)
        return 2
    except KeyboardInterrupt:
        exc = RuntimeError("Operation interrupted.")
        print_response(failure(args.command, exc), args.json)
        return 130
    except Exception as exc:
        print_response(failure(args.command, exc), args.json)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
