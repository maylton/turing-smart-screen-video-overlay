#!/usr/bin/env python3
from pathlib import Path

path = Path("theme-editor-gtk.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    text = text.replace(old, new, 1)


if "def find_theme_file(theme_dir: Path)" not in text:
    replace_once(
        "def available_themes() -> list[str]:\n",
        "def find_theme_file(theme_dir: Path) -> Path | None:\n"
        "    \"\"\"Return the supported YAML file for a theme directory.\"\"\"\n"
        "    for filename in (\"theme.yaml\", \"theme.yml\"):\n"
        "        candidate = theme_dir / filename\n"
        "        if candidate.is_file():\n"
        "            return candidate\n"
        "    return None\n\n\n"
        "def available_themes() -> list[str]:\n",
        "theme file helper",
    )

replace_once(
    "        for path in THEMES_DIR.iterdir():\n"
    "            if not path.is_dir():\n"
    "                continue\n"
    "            if (path / \"theme.yaml\").is_file() or (path / \"theme.yml\").is_file():\n"
    "                themes.append(path.name)\n",
    "        for path in THEMES_DIR.iterdir():\n"
    "            if path.is_dir() and find_theme_file(path) is not None:\n"
    "                themes.append(path.name)\n",
    "available theme scan",
)

replace_once(
    "        self.theme_name = theme_name\n"
    "        self.theme_dir = THEMES_DIR / theme_name\n"
    "        self.theme_file = self.theme_dir / \"theme.yaml\"\n"
    "        self.preview_file = self.theme_dir / \"preview.png\"\n\n"
    "        if not self.theme_file.is_file():\n"
    "            raise FileNotFoundError(self.theme_file)\n",
    "        self.theme_name = theme_name\n"
    "        self.theme_dir = THEMES_DIR / theme_name\n"
    "        theme_file = find_theme_file(self.theme_dir)\n"
    "        if theme_file is None:\n"
    "            raise FileNotFoundError(\n"
    "                f\"No theme.yaml or theme.yml found in {self.theme_dir}\"\n"
    "            )\n"
    "        self.theme_file = theme_file\n"
    "        self.preview_file = self.theme_dir / \"preview.png\"\n",
    "initial theme lookup",
)

replace_once(
    "                    destination / \"theme.yaml\",\n",
    "                    destination / self.theme_file.name,\n",
    "save-as filename",
)

replace_once(
    "        theme_dir = THEMES_DIR / theme_name\n"
    "        theme_file = theme_dir / \"theme.yaml\"\n"
    "        if not theme_file.is_file():\n"
    "            self.error_dialog(\n"
    "                \"Could not change theme\",\n"
    "                f\"{theme_file} was not found.\",\n"
    "            )\n"
    "            return False\n",
    "        theme_dir = THEMES_DIR / theme_name\n"
    "        theme_file = find_theme_file(theme_dir)\n"
    "        if theme_file is None:\n"
    "            self.error_dialog(\n"
    "                \"Could not change theme\",\n"
    "                f\"No theme.yaml or theme.yml was found in {theme_dir}.\",\n"
    "            )\n"
    "            return False\n",
    "switch theme lookup",
)

replace_once(
    "        def change_selected_theme(*_args):\n"
    "            index = theme_dropdown.get_selected()\n"
    "            if index < 0 or index >= len(theme_names):\n"
    "                self.toast(\"Choose a theme first\")\n"
    "                return\n"
    "            self.switch_theme(theme_names[index])\n\n"
    "        change_theme.connect(\"clicked\", change_selected_theme)\n",
    "        def change_selected_theme(*_args):\n"
    "            index = theme_dropdown.get_selected()\n"
    "            if index < 0 or index >= len(theme_names):\n"
    "                self.toast(\"Choose a theme first\")\n"
    "                return\n"
    "            if self.switch_theme(theme_names[index]):\n"
    "                dialog.close()\n\n"
    "        change_theme.connect(\"clicked\", change_selected_theme)\n",
    "video dialog switch",
)

path.write_text(text, encoding="utf-8")
