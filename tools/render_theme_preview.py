#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a theme preview using the same pipeline as the GTK Theme Editor."
    )
    parser.add_argument("theme_name")
    parser.add_argument("output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))

    from library import config

    config.CONFIG_DATA["config"]["HW_SENSORS"] = "STATIC"
    config.CONFIG_DATA["config"]["THEME"] = str(args.theme_name)
    config.load_theme()
    config.CONFIG_DATA["display"]["REVISION"] = "SIMU"

    from library.display import display

    display.initialize_display()

    video = config.THEME_DATA.get("video", {})
    preview_background = video.get("PREVIEW_BACKGROUND", "background.png")
    bg_path = Path(config.THEME_DATA["PATH"]) / str(preview_background)

    if bg_path.is_file():
        image = Image.open(bg_path).convert("RGB").resize(
            (display.lcd.get_width(), display.lcd.get_height())
        )
        display.lcd.screen_image = image

    display.display_static_images()

    from library.theme_video_background import theme_uses_video_overlay

    if theme_uses_video_overlay(config.THEME_DATA):
        display.lcd.video_overlay_enabled = True

    display.display_static_text()

    import library.stats as stats

    callbacks = [
        (("STATS", "CPU", "PERCENTAGE"), stats.CPU.percentage),
        (("STATS", "CPU", "FREQUENCY"), stats.CPU.frequency),
        (("STATS", "CPU", "LOAD"), stats.CPU.load),
        (("STATS", "CPU", "TEMPERATURE"), stats.CPU.temperature),
        (("STATS", "CPU", "FAN_SPEED"), stats.CPU.fan_speed),
        (("STATS", "GPU"), stats.Gpu.stats),
        (("STATS", "MEMORY"), stats.Memory.stats),
        (("STATS", "DISK"), stats.Disk.stats),
        (("STATS", "NET"), stats.Net.stats),
        (("STATS", "DATE"), stats.Date.stats),
        (("STATS", "UPTIME"), stats.SystemUptime.stats),
        (("STATS", "CUSTOM"), stats.Custom.stats),
        (("STATS", "WEATHER"), stats.Weather.stats),
        (("STATS", "PING"), stats.Ping.stats),
    ]

    for path, callback in callbacks:
        node = config.THEME_DATA
        try:
            for part in path:
                node = node[part]
            if isinstance(node, dict) and node.get("INTERVAL", 0) > 0:
                callback()
        except Exception:
            pass

    args.output.parent.mkdir(parents=True, exist_ok=True)
    display.lcd.screen_image.save(args.output, "PNG")

    try:
        display.lcd.closeSerial()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
