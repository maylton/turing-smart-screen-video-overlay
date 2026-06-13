python3 - <<'PY'
from pathlib import Path

p = Path("library/display.py")
s = p.read_text()

method = '''
    def start_theme_video(self):
        video_config = config.THEME_DATA.get("video", {})

        if not video_config.get("ENABLED", False):
            return

        if video_config.get("MODE", "native") != "native":
            logger.warning("Only native video mode is supported for now")
            return

        video_path = video_config.get("PATH", None)

        if not video_path:
            logger.warning("Theme video is enabled, but no PATH was provided")
            return

        if not hasattr(self.lcd, "StartVideoOverlay"):
            logger.warning("This display revision does not support native video overlay")
            return

        self.lcd.StartVideoOverlay(video_path)

'''

if "def start_theme_video" not in s:
    marker = "    def display_static_images"
    if marker not in s:
        raise SystemExit("Could not find display_static_images marker in library/display.py")
    s = s.replace(marker, method + marker)

p.write_text(s)
PY
