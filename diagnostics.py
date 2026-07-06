#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe diagnostics collector for the GTK Turing Smart Screen app.

This command intentionally does not open the display serial port. It only reads
configuration files, enumerates serial descriptors, and reports process/theme
state so it can be used while the monitor is running.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from library.display_lifecycle import get_display_lifecycle_state


ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.yaml"
THEMES_DIR = ROOT / "res" / "themes"
MAIN_PROGRAM = ROOT / "main.py"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_scalar_from_yaml_text(path: Path, key: str) -> str:
    content = _read_text(path)
    match = re.search(rf'(?m)^\s*{re.escape(key)}\s*:\s*["\']?([^"\'\n#]+)', content)
    return match.group(1).strip() if match else ""


def read_current_theme() -> str:
    return _read_scalar_from_yaml_text(CONFIG_FILE, "THEME")


def normalize_display_size(value: str) -> str:
    value = str(value or "").strip().lower().replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    return match.group(1) if match else ""


def selected_display_size() -> str:
    for key in ("DISPLAY_SIZE", "SCREEN_SIZE", "SIZE"):
        value = normalize_display_size(_read_scalar_from_yaml_text(CONFIG_FILE, key))
        if value:
            return value

    current = read_current_theme()
    if current:
        yaml_path = theme_yaml_path(current)
        if yaml_path is not None:
            value = normalize_display_size(_read_scalar_from_yaml_text(yaml_path, "DISPLAY_SIZE"))
            if value:
                return value

    return ""


def theme_yaml_path(theme_name: str) -> Path | None:
    if not theme_name:
        return None
    theme_dir = THEMES_DIR / theme_name
    for filename in ("theme.yaml", "theme.yml"):
        candidate = theme_dir / filename
        if candidate.is_file():
            return candidate
    return None


def theme_preview_path(theme_name: str) -> Path | None:
    if not theme_name:
        return None
    theme_dir = THEMES_DIR / theme_name
    ignored = {
        "video-preview.png",
        "video_preview.png",
        "preview-background.png",
        "preview_background.png",
    }

    for candidate in (theme_dir / "preview.png", theme_dir / "background.png"):
        if candidate.is_file() and candidate.name.casefold() not in ignored:
            return candidate

    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        for candidate in sorted(theme_dir.glob(pattern)):
            if candidate.name.casefold() not in ignored and not candidate.name.startswith("."):
                return candidate
    return None


def parse_theme_video(theme_name: str) -> dict[str, Any]:
    yaml_path = theme_yaml_path(theme_name)
    if yaml_path is None:
        return {"configured": False, "reason": "theme YAML missing"}

    text = _read_text(yaml_path)
    match = re.search(r"(?ms)^video:\s*(.*?)(?:\n\S|\Z)", text)
    if match is None:
        return {"configured": False, "reason": "video block missing"}

    block = match.group(1)

    def read_key(*keys: str) -> str:
        for key in keys:
            value_match = re.search(
                rf'(?mi)^\s*{re.escape(key)}\s*:\s*["\']?([^"\'\n#]+)',
                block,
            )
            if value_match:
                return value_match.group(1).strip()
        return ""

    enabled_text = read_key("ENABLED", "SHOW")
    enabled = enabled_text.casefold() in {"true", "yes", "on", "1"}
    local_text = read_key("LOCAL_PATH", "PATH")
    remote_text = read_key("REMOTE_PATH", "REMOTE")

    local_path = Path(local_text).expanduser()
    if local_text and not local_path.is_absolute():
        local_path = (yaml_path.parent / local_path).resolve()

    return {
        "configured": bool(enabled and local_text),
        "enabled": enabled,
        "local": str(local_path) if local_text else "",
        "local_exists": local_path.is_file() if local_text else False,
        "remote": remote_text,
    }


def list_serial_ports() -> list[dict[str, Any]]:
    try:
        from serial.tools import list_ports
    except Exception as exc:
        return [{"error": f"pyserial unavailable: {exc}"}]

    ports = []
    for port in list_ports.comports():
        haystack = " ".join(
            str(getattr(port, attr, "") or "")
            for attr in ("description", "manufacturer", "product", "interface")
        ).casefold()
        ports.append(
            {
                "device": port.device,
                "description": port.description,
                "manufacturer": getattr(port, "manufacturer", None),
                "product": getattr(port, "product", None),
                "serial_number": getattr(port, "serial_number", None),
                "vid": getattr(port, "vid", None),
                "pid": getattr(port, "pid", None),
                "is_tty_acm": str(port.device).startswith("/dev/ttyACM"),
                "is_usb_monitor": "usbmonitor" in haystack,
            }
        )
    return ports


def monitor_pids() -> list[int]:
    patterns = [
        str(MAIN_PROGRAM),
        r"[m]ain.py",
    ]
    pids: set[int] = set()
    current_pid = os.getpid()

    for pattern in patterns:
        try:
            result = subprocess.run(
                ["pgrep", "-f", pattern],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                timeout=3,
                check=False,
            )
        except Exception:
            continue

        for line in result.stdout.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid != current_pid:
                pids.add(pid)

    return sorted(pids)


def collect_diagnostics() -> dict[str, Any]:
    current_theme = read_current_theme()
    theme_dir = THEMES_DIR / current_theme if current_theme else None
    yaml_path = theme_yaml_path(current_theme)
    preview_path = theme_preview_path(current_theme)
    serial_ports = list_serial_ports()
    real_tty_acm = [
        port.get("device")
        for port in serial_ports
        if port.get("is_tty_acm") and not port.get("is_usb_monitor")
    ]
    usb_monitor = [
        port.get("device")
        for port in serial_ports
        if port.get("is_usb_monitor")
    ]
    pids = monitor_pids()
    display_lifecycle = get_display_lifecycle_state(
        ROOT,
        serial_ports=serial_ports,
        monitor_processes=pids,
    )

    return {
        "root": str(ROOT),
        "config": {
            "path": str(CONFIG_FILE),
            "exists": CONFIG_FILE.is_file(),
            "theme": current_theme,
            "display_size": selected_display_size(),
        },
        "theme": {
            "directory": str(theme_dir) if theme_dir else "",
            "directory_exists": theme_dir.is_dir() if theme_dir else False,
            "yaml": str(yaml_path) if yaml_path else "",
            "yaml_exists": yaml_path.is_file() if yaml_path else False,
            "preview": str(preview_path) if preview_path else "",
            "preview_exists": preview_path.is_file() if preview_path else False,
            "video": parse_theme_video(current_theme) if current_theme else {"configured": False, "reason": "no active theme"},
        },
        "runtime": {
            "monitor_running": bool(pids),
            "monitor_pids": pids,
        },
        "serial": {
            "ports": serial_ports,
            "real_tty_acm": real_tty_acm,
            "usb_monitor": usb_monitor,
        },
        "display_lifecycle": display_lifecycle.to_dict(),
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = []
    config = payload["config"]
    theme = payload["theme"]
    video = theme["video"]
    runtime = payload["runtime"]
    serial = payload["serial"]
    lifecycle = payload.get("display_lifecycle", {})

    lines.append("Turing Smart Screen diagnostics")
    lines.append("=" * 34)
    lines.append(f"Root: {payload['root']}")
    lines.append(f"Config: {'OK' if config['exists'] else 'missing'} · {config['path']}")
    lines.append(f"Active theme: {config['theme'] or 'not configured'}")
    lines.append(f"Display size: {config['display_size'] or 'unknown'}")
    lines.append("")
    lines.append("Theme")
    lines.append(f"- Directory: {'OK' if theme['directory_exists'] else 'missing'} · {theme['directory'] or '—'}")
    lines.append(f"- YAML: {'OK' if theme['yaml_exists'] else 'missing'} · {theme['yaml'] or '—'}")
    lines.append(f"- Preview: {'OK' if theme['preview_exists'] else 'missing'} · {theme['preview'] or '—'}")
    if video.get("configured"):
        lines.append(f"- Video: configured · local exists: {'yes' if video.get('local_exists') else 'no'}")
        lines.append(f"  local: {video.get('local') or '—'}")
        lines.append(f"  remote: {video.get('remote') or '—'}")
    else:
        lines.append(f"- Video: not configured · {video.get('reason', 'missing/disabled')}")
    lines.append("")
    lines.append("Runtime")
    lines.append(f"- Monitor: {'running' if runtime['monitor_running'] else 'stopped'}")
    if runtime["monitor_pids"]:
        lines.append(f"- PID(s): {', '.join(map(str, runtime['monitor_pids']))}")
    lines.append("")
    lines.append("Display lifecycle")
    lines.append(f"- State: {lifecycle.get('state', 'unknown')}")
    lines.append(f"- Label: {lifecycle.get('label', 'Display: unknown')}")
    lines.append(f"- Details: {lifecycle.get('details', 'No lifecycle details available')}")
    if lifecycle.get("busy_pids"):
        lines.append(f"- Busy PID(s): {', '.join(map(str, lifecycle['busy_pids']))}")
    if lifecycle.get("warnings"):
        lines.append("- Warning(s):")
        for warning in lifecycle["warnings"]:
            lines.append(f"  · {warning}")
    lines.append("")
    lines.append("Serial")
    lines.append(f"- Real ttyACM candidate(s): {', '.join(serial['real_tty_acm']) if serial['real_tty_acm'] else 'none'}")
    lines.append(f"- UsbMonitor port(s): {', '.join(serial['usb_monitor']) if serial['usb_monitor'] else 'none'}")
    if serial["ports"]:
        lines.append("- Ports:")
        for port in serial["ports"]:
            if "error" in port:
                lines.append(f"  · {port['error']}")
                continue
            role = "UsbMonitor" if port.get("is_usb_monitor") else ("display candidate" if port.get("is_tty_acm") else "other")
            lines.append(f"  · {port.get('device')} · {role} · {port.get('description') or ''}")
    else:
        lines.append("- Ports: none")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect safe app/display diagnostics.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    payload = collect_diagnostics()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
