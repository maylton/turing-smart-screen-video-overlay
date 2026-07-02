#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from library.display_detection import auto_configure

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description="Safely detect supported smart displays")
parser.add_argument("--json", action="store_true")
parser.add_argument("command", choices=("scan", "apply"))
args = parser.parse_args()

try:
    report = auto_configure(ROOT, apply=args.command == "apply")
    payload = {"ok": True, "command": args.command, "data": report.to_dict()}
    status = 0
except Exception as exc:
    payload = {"ok": False, "command": args.command, "error": {"type": type(exc).__name__, "message": str(exc)}}
    status = 1

if args.json:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
elif payload["ok"]:
    print(payload["data"]["message"])
else:
    print(payload["error"]["message"], file=sys.stderr)
raise SystemExit(status)
