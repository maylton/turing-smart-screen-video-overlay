#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping


RULES = {
    "cpu_percentage": [r"\bcpu\b", r"cpu.*(?:usage|load|percent|percentage)"],
    "cpu_temperature": [r"cpu.*(?:temp|temperature)", r"(?:temp|temperature).*cpu"],
    "gpu_percentage": [r"\bgpu\b", r"gpu.*(?:usage|load|percent|percentage)"],
    "gpu_temperature": [r"gpu.*(?:temp|temperature)", r"(?:temp|temperature).*gpu"],
    "memory": [r"\bram\b", r"\bmemory\b", r"\bmem\b"],
    "disk": [r"\bdisk\b", r"\bstorage\b", r"\bssd\b", r"\bhdd\b"],
    "network": [r"\bnet\b", r"\bnetwork\b", r"\bdownload\b", r"\bupload\b"],
    "date": [r"\bdate\b", r"\bday\b", r"\bmonth\b", r"\byear\b"],
    "time": [r"\btime\b", r"\bclock\b", r"\bhour\b", r"\bminute\b"],
}


def strings_from_bytes(data: bytes) -> list[str]:
    values = []

    for match in re.finditer(rb"[\x20-\x7e]{4,}", data):
        values.append(match.group(0).decode("utf-8", errors="ignore"))

    for match in re.finditer(rb"(?:[\x20-\x7e]\x00){4,}", data):
        values.append(match.group(0).decode("utf-16le", errors="ignore"))

    return values


def manifest_strings(manifest: Mapping[str, Any]) -> list[str]:
    values = []

    def walk(node):
        if isinstance(node, Mapping):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            values.append(node)

    walk(manifest)
    return values


def detect_hints(theme_path: Path | None, manifest: Mapping[str, Any]) -> dict[str, Any]:
    evidence = manifest_strings(manifest)

    if theme_path and theme_path.is_file():
        try:
            evidence.extend(strings_from_bytes(theme_path.read_bytes()))
        except OSError:
            pass

    cleaned = []
    seen = set()
    for item in evidence:
        item = " ".join(str(item).replace("\\", "/").split())
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

    haystack = "\n".join(cleaned).casefold()

    detected = {}
    for name, patterns in RULES.items():
        matches = [pattern for pattern in patterns if re.search(pattern, haystack, re.I)]
        detected[name] = {
            "detected": bool(matches),
            "confidence": round(min(1.0, len(matches) / max(1, len(patterns))), 2),
            "patterns": matches,
        }

    return {
        "version": 1,
        "detected": detected,
        "evidence_sample": cleaned[:80],
    }


def has(hints: Mapping[str, Any], key: str) -> bool:
    item = hints.get("detected", {}).get(key, {})
    return isinstance(item, Mapping) and bool(item.get("detected"))


def confidence(hints: Mapping[str, Any], key: str) -> float:
    item = hints.get("detected", {}).get(key, {})
    if not isinstance(item, Mapping):
        return 0.0
    try:
        return float(item.get("confidence") or 0.0)
    except Exception:
        return 0.0


def text_node(x, y, size=20):
    return {
        "SHOW": True,
        "SHOW_UNIT": True,
        "X": x,
        "Y": y,
        "FONT": "jetbrains-mono/JetBrainsMono-Bold.ttf",
        "FONT_SIZE": size,
        "FONT_COLOR": [255, 255, 255],
        "BACKGROUND_COLOR": [0, 0, 0, 0],
        "ALIGN": "left",
        "ANCHOR": "lt",
    }


def hidden_text():
    node = text_node(0, 0, 13)
    node["SHOW"] = False
    return node


def graph_node(x, y, width):
    return {
        "SHOW": True,
        "X": x,
        "Y": y,
        "WIDTH": width,
        "HEIGHT": 10,
        "BAR_COLOR": [255, 255, 255],
        "BAR_BACKGROUND_COLOR": [255, 255, 255, 45],
        "BACKGROUND_COLOR": [0, 0, 0, 0],
    }


def hidden_graph():
    node = graph_node(0, 0, 100)
    node["SHOW"] = False
    return node


def hidden_radial():
    return {
        "SHOW": False,
        "X": 0,
        "Y": 0,
        "RADIUS": 24,
        "WIDTH": 6,
        "SHOW_TEXT": False,
        "FONT_SIZE": 12,
        "FONT_COLOR": [255, 255, 255],
        "BAR_COLOR": [255, 255, 255],
        "BACKGROUND_COLOR": [0, 0, 0, 0],
    }


def hidden_line():
    return {
        "SHOW": False,
        "X": 0,
        "Y": 0,
        "WIDTH": 100,
        "HEIGHT": 42,
        "LINE_COLOR": [255, 255, 255],
        "BACKGROUND_COLOR": [0, 0, 0, 0],
    }


def metric_group(text=None, graph=None):
    return {
        "INTERVAL": 1,
        "TEXT": text or hidden_text(),
        "GRAPH": graph or hidden_graph(),
        "RADIAL": hidden_radial(),
        "LINE_GRAPH": hidden_line(),
    }


def starter_stats_from_hints(hints: Mapping[str, Any], width=480, height=320) -> dict[str, Any]:
    width = int(width or 480)
    height = int(height or 320)
    square = abs(width - height) <= 8
    landscape = width >= height

    # TURZX temperature themes often contain generic CPU/GPU strings in the
    # serialized Windows object graph even when the visible layout is really a
    # CPU temperature + date/time design. In that case, avoid placing generic
    # percentage bars over decorative backgrounds.
    temp_clock_profile = (
        has(hints, "cpu_temperature")
        and (has(hints, "date") or has(hints, "time"))
        and not has(hints, "memory")
        and not has(hints, "disk")
        and not has(hints, "network")
    )

    stats = {}

    if square:
        left_x = int(width * 0.19)
        right_x = int(width * 0.64)
        top_y = int(height * 0.08)
        temp_y = int(height * 0.43)
        date_y = int(height * 0.81)
        time_y = int(height * 0.88)
        bar_w = int(width * 0.22)
    else:
        left_x = int(width * 0.08)
        right_x = int(width * 0.58) if landscape else left_x
        top_y = int(height * 0.08)
        temp_y = int(height * 0.38)
        date_y = int(height * 0.80)
        time_y = int(height * 0.87)
        bar_w = int(width * 0.32) if landscape else int(width * 0.72)

    show_cpu_percentage = has(hints, "cpu_percentage") and not temp_clock_profile
    show_cpu_temperature = has(hints, "cpu_temperature")

    if show_cpu_percentage or show_cpu_temperature:
        cpu = {}

        if show_cpu_percentage:
            cpu["PERCENTAGE"] = metric_group(
                text=text_node(left_x, top_y, 22),
                graph=graph_node(left_x, top_y + 32, bar_w),
            )

        if show_cpu_temperature:
            temp_text = text_node(left_x, temp_y, 42 if square else 44)
            if temp_clock_profile:
                # Many TURZX temperature themes already draw the °C symbol as
                # part of the background/artwork. Render only the numeric value.
                temp_text["SHOW_UNIT"] = False
            cpu["TEMPERATURE"] = metric_group(
                text=temp_text,
            )

        stats["CPU"] = cpu

    # GPU hints in TURZX object strings are often weaker false positives.
    # Only enable them automatically when the evidence is strong and the theme
    # does not look like a CPU temperature/clock layout.
    show_gpu_percentage = confidence(hints, "gpu_percentage") >= 0.75 and not temp_clock_profile
    show_gpu_temperature = confidence(hints, "gpu_temperature") >= 0.75 and not temp_clock_profile

    if show_gpu_percentage or show_gpu_temperature:
        gpu = {"INTERVAL": 1}

        if show_gpu_percentage:
            gpu["PERCENTAGE"] = metric_group(
                text=text_node(right_x, top_y, 22),
                graph=graph_node(right_x, top_y + 32, bar_w),
            )

        if show_gpu_temperature:
            gpu["TEMPERATURE"] = metric_group(
                text=text_node(right_x, temp_y, 34),
            )

        stats["GPU"] = gpu

    if has(hints, "memory") and not temp_clock_profile:
        stats["MEMORY"] = {
            "INTERVAL": 5,
            "VIRTUAL": {
                "PERCENT_TEXT": text_node(left_x, int(height * 0.66), 20),
                "GRAPH": graph_node(left_x, int(height * 0.66) + 30, bar_w),
                "RADIAL": hidden_radial(),
                "LINE_GRAPH": hidden_line(),
                "USED": hidden_text(),
                "FREE": hidden_text(),
                "TOTAL": hidden_text(),
            },
            "SWAP": {
                "GRAPH": hidden_graph(),
                "RADIAL": hidden_radial(),
                "LINE_GRAPH": hidden_line(),
            },
        }

    if has(hints, "disk") and not temp_clock_profile:
        stats["DISK"] = {
            "INTERVAL": 10,
            "USED": {
                "PERCENT_TEXT": text_node(right_x, int(height * 0.66), 20),
                "GRAPH": graph_node(right_x, int(height * 0.66) + 30, bar_w),
                "RADIAL": hidden_radial(),
                "LINE_GRAPH": hidden_line(),
                "TEXT": hidden_text(),
            },
            "TOTAL": {"TEXT": hidden_text()},
            "FREE": {"TEXT": hidden_text()},
        }

    if has(hints, "date") or has(hints, "time"):
        date = {"INTERVAL": 1}

        # Bottom-right works better for the 480x480 neon-ring TURZX themes.
        date_x = int(width * 0.58) if square else right_x
        if has(hints, "date"):
            date["DAY"] = {
                "TEXT": {
                    **text_node(date_x, date_y, 16),
                    "FORMAT": "medium",
                }
            }
        if has(hints, "time"):
            date["HOUR"] = {
                "TEXT": {
                    **text_node(date_x, time_y, 28),
                    "FORMAT": "short",
                }
            }

        stats["DATE"] = date

    return stats


def write_outputs(output_dir: Path, hints: Mapping[str, Any], width=480, height=320):
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "windows-theme-hints.json").write_text(
        json.dumps(hints, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    stats = starter_stats_from_hints(hints, width=width, height=height)
    (output_dir / "starter-stats-hints.json").write_text(
        json.dumps({"STATS": stats}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def analyze_extracted_theme(theme_path: Path | None, output_dir: Path, manifest: Mapping[str, Any]):
    return detect_hints(theme_path, manifest)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("--theme", type=Path)
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=320)
    return parser.parse_args()


def main():
    args = parse_args()
    manifest_path = args.target if args.target.is_file() else args.target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    theme_path = args.theme
    if theme_path is None and manifest.get("input"):
        theme_path = Path(str(manifest["input"]))

    hints = detect_hints(theme_path, manifest)
    write_outputs(manifest_path.parent, hints, width=args.width, height=args.height)

    manifest["windows_theme_hints"] = hints
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    detected = [
        key for key, value in hints["detected"].items()
        if value.get("detected")
    ]
    print("Detected:", ", ".join(detected) if detected else "none")


if __name__ == "__main__":
    main()
