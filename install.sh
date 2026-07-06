#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_ID="io.github.turing.SmartScreen"
APP_NAME="Turing Smart Screen"
COMMAND_NAME="turing-smart-screen"

MODE="user"
INSTALL_DEPS=1
ENABLE_AUTOSTART=0
PRESERVE_USER_DATA=1

usage() {
  cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Install Turing Smart Screen as a native Linux desktop application.

Options:
  --system          Install in /opt and /usr/local (requires sudo)
  --no-deps         Do not install system packages
  --autostart       Start the application automatically after login
  --fresh           Replace installed themes/configuration instead of preserving them
  -h, --help        Show this help

Default installation:
  Application: ~/.local/share/turing-smart-screen
  Launcher:    ~/.local/bin/turing-smart-screen
  Desktop:     ~/.local/share/applications/io.github.turing.SmartScreen.desktop
EOF
}

for arg in "$@"; do
  case "$arg" in
    --system) MODE="system" ;;
    --no-deps) INSTALL_DEPS=0 ;;
    --autostart) ENABLE_AUTOSTART=1 ;;
    --fresh) PRESERVE_USER_DATA=0 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$MODE" == "system" ]]; then
  PREFIX="/opt/turing-smart-screen"
  BIN_DIR="/usr/local/bin"
  DESKTOP_DIR="/usr/share/applications"
  ICON_BASE="/usr/share/icons/hicolor"
  SUDO="sudo"
else
  PREFIX="$HOME/.local/share/turing-smart-screen"
  BIN_DIR="$HOME/.local/bin"
  DESKTOP_DIR="$HOME/.local/share/applications"
  ICON_BASE="$HOME/.local/share/icons/hicolor"
  SUDO=""
fi

DESKTOP_FILE="$DESKTOP_DIR/$APP_ID.desktop"
ICON_64="$ICON_BASE/64x64/apps/$APP_ID.png"
ICON_128="$ICON_BASE/128x128/apps/$APP_ID.png"
LAUNCHER="$BIN_DIR/$COMMAND_NAME"

canonical_path() {
  if command -v realpath >/dev/null 2>&1; then
    realpath -m "$1"
  else
    python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$1"
  fi
}

copy_if_different() {
  local src="$1"
  local dest="$2"
  local mode="${3:-}"

  if [[ ! -f "$src" ]]; then
    return 1
  fi

  local src_real
  local dest_real
  src_real="$(canonical_path "$src")"
  dest_real="$(canonical_path "$dest")"

  if [[ "$src_real" == "$dest_real" ]]; then
    echo "Keeping $(basename "$dest"): source and destination are already the same file."
  else
    $SUDO cp "$src" "$dest"
  fi

  if [[ -n "$mode" ]]; then
    $SUDO chmod "$mode" "$dest"
  fi
}

SOURCE_REAL="$(canonical_path "$SOURCE_DIR")"
PREFIX_REAL="$(canonical_path "$PREFIX")"
SELF_INSTALL=0
if [[ "$SOURCE_REAL" == "$PREFIX_REAL" ]]; then
  SELF_INSTALL=1
fi

if [[ "$INSTALL_DEPS" -eq 1 ]]; then
  if command -v pacman >/dev/null 2>&1; then
    echo "Installing Arch/CachyOS dependencies..."
    sudo pacman -S --needed \
      python python-pip python-virtualenv python-gobject \
      gtk4 libadwaita ffmpeg rsync git tk python-pillow \
      python-pyserial python-babel desktop-file-utils
  else
    echo "Automatic dependency installation currently supports Arch/CachyOS." >&2
    echo "Required: Python 3, PyGObject, GTK4, Libadwaita, ffmpeg, rsync, Git, Tk, Pillow, pyserial and Babel." >&2
  fi
fi

if [[ ! -f "$SOURCE_DIR/main.py" ]]; then
  echo "main.py was not found in: $SOURCE_DIR" >&2
  echo "Run install.sh from the complete project directory." >&2
  exit 1
fi

echo "Installing $APP_NAME in: $PREFIX"

if [[ "$SELF_INSTALL" -eq 1 ]]; then
  echo "Source directory is already the install directory; project file synchronization will be skipped."
fi

$SUDO mkdir -p \
  "$PREFIX" \
  "$BIN_DIR" \
  "$DESKTOP_DIR" \
  "$ICON_BASE/64x64/apps" \
  "$ICON_BASE/128x128/apps"

BACKUP_DIR=""
if [[ "$SELF_INSTALL" -eq 0 ]] && [[ -d "$PREFIX" ]] && [[ "$PRESERVE_USER_DATA" -eq 1 ]]; then
  BACKUP_DIR="$(mktemp -d)"

  [[ -f "$PREFIX/config.yaml" ]] && \
    cp "$PREFIX/config.yaml" "$BACKUP_DIR/config.yaml"

  [[ -d "$PREFIX/res/themes" ]] && \
    cp -a "$PREFIX/res/themes" "$BACKUP_DIR/themes"

  [[ -d "$PREFIX/res/video" ]] && \
    cp -a "$PREFIX/res/video" "$BACKUP_DIR/video"

  [[ -d "$PREFIX/res/videos" ]] && \
    cp -a "$PREFIX/res/videos" "$BACKUP_DIR/videos"
fi

RSYNC_ARGS=(
  -a
  --delete
  --exclude '.git/'
  --exclude 'venv/'
  --exclude '.venv/'
  --exclude '__pycache__/'
  --exclude '*.pyc'
  --exclude '*.pcapng'
  --exclude '.gtk-ui-backups/'
  --exclude '.theme-editor-backups/'
  --exclude '.test-environment/'
  --exclude '.test-media/'
  --exclude '.packaging-test/'
  --exclude 'res/themes/*/theme.yaml.tmp'
  --exclude 'res/themes/*/theme.yaml.editor-backup'
  --exclude 'res/themes/*/theme.yaml.before-sequence-repair'
)

if [[ "$SELF_INSTALL" -eq 0 ]]; then
  if [[ "$MODE" == "system" ]]; then
    sudo rsync "${RSYNC_ARGS[@]}" "$SOURCE_DIR/" "$PREFIX/"
  else
    rsync "${RSYNC_ARGS[@]}" "$SOURCE_DIR/" "$PREFIX/"
  fi
fi

# The backend venv disables Python's automatic usercustomize import.  For test
# branch UI hooks, explicitly load the installed usercustomize.py from the
# already-imported sitecustomize.py.  This keeps the hook scoped to the installed
# test build and avoids depending on Python user-site behavior.
if [[ -f "$PREFIX/sitecustomize.py" ]] && [[ -f "$PREFIX/usercustomize.py" ]]; then
  if ! grep -q 'Test-branch optional hooks' "$PREFIX/sitecustomize.py"; then
    $SUDO tee -a "$PREFIX/sitecustomize.py" >/dev/null <<'PY'

# Test-branch optional hooks.
try:
    import usercustomize
except Exception as exc:  # pragma: no cover - defensive startup guard
    import sys
    print(
        f"[usercustomize] could not load optional hooks: {exc}",
        file=sys.stderr,
        flush=True,
    )
PY
  fi
fi

# Install the latest consolidated GTK interface from this installer bundle.
if [[ -f "$SOURCE_DIR/configure-gtk-final.py" ]]; then
  copy_if_different "$SOURCE_DIR/configure-gtk-final.py" "$PREFIX/configure-gtk.py"
elif [[ -f "$SOURCE_DIR/configure-gtk.py" ]]; then
  :
else
  echo "configure-gtk.py was not found." >&2
  exit 1
fi

# The runtime launcher patches Settings after loading configure_gtk_app.py.
# Install the diagnostics integration after those runtime patches as well;
# otherwise the runtime Settings replacement hides the test Diagnostics row.
if [[ -f "$PREFIX/configure-gtk.py" ]] && [[ -f "$PREFIX/library/main_app_diagnostics_integration.py" ]]; then
  $SUDO /usr/bin/python3 - "$PREFIX/configure-gtk.py" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
marker = "install_main_app_diagnostics_integration(app)"
if marker not in text:
    old = "    install_runtime_patches(app)\n    return app.main()\n"
    new = """    install_runtime_patches(app)\n    try:\n        from library.main_app_diagnostics_integration import (\n            install_main_app_diagnostics_integration,\n        )\n\n        install_main_app_diagnostics_integration(app)\n    except Exception as exc:  # pragma: no cover - defensive startup guard\n        print(\n            f\"[diagnostics] could not install main app integration after runtime patches: {exc}\",\n            file=sys.stderr,\n            flush=True,\n        )\n    return app.main()\n"""
    if old not in text:
        raise SystemExit("Could not patch configure-gtk.py diagnostics integration hook")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
fi

if [[ -f "$SOURCE_DIR/main-final.py" ]]; then
  copy_if_different "$SOURCE_DIR/main-final.py" "$PREFIX/main.py"
fi

if [[ -f "$SOURCE_DIR/screen-control.py" ]]; then
  copy_if_different "$SOURCE_DIR/screen-control.py" "$PREFIX/screen-control.py" "+x"
fi

if [[ -f "$SOURCE_DIR/gtk-checkup.py" ]]; then
  copy_if_different "$SOURCE_DIR/gtk-checkup.py" "$PREFIX/gtk-checkup.py"
fi

# Restore the user's existing configuration, custom themes and videos.
if [[ -n "$BACKUP_DIR" ]]; then
  if [[ -f "$BACKUP_DIR/config.yaml" ]]; then
    $SUDO cp "$BACKUP_DIR/config.yaml" "$PREFIX/config.yaml"
  fi

  if [[ -d "$BACKUP_DIR/themes" ]]; then
    $SUDO mkdir -p "$PREFIX/res/themes"
    $SUDO cp -a "$BACKUP_DIR/themes/." "$PREFIX/res/themes/"
  fi

  if [[ -d "$BACKUP_DIR/video" ]]; then
    $SUDO mkdir -p "$PREFIX/res/video"
    $SUDO cp -a "$BACKUP_DIR/video/." "$PREFIX/res/video/"
  fi

  if [[ -d "$BACKUP_DIR/videos" ]]; then
    $SUDO mkdir -p "$PREFIX/res/videos"
    $SUDO cp -a "$BACKUP_DIR/videos/." "$PREFIX/res/videos/"
  fi

  rm -rf "$BACKUP_DIR"
fi

# Recreate the backend virtual environment so dependencies match the installed release.
$SUDO rm -rf "$PREFIX/venv"

if [[ "$MODE" == "system" ]]; then
  sudo /usr/bin/python3 -m venv --system-site-packages "$PREFIX/venv"
  if [[ -f "$PREFIX/requirements.txt" ]]; then
    sudo "$PREFIX/venv/bin/python3" -m pip install --upgrade pip
    sudo "$PREFIX/venv/bin/python3" -m pip install -r "$PREFIX/requirements.txt"
  fi
else
  /usr/bin/python3 -m venv --system-site-packages "$PREFIX/venv"
  if [[ -f "$PREFIX/requirements.txt" ]]; then
    "$PREFIX/venv/bin/python3" -m pip install --upgrade pip
    "$PREFIX/venv/bin/python3" -m pip install -r "$PREFIX/requirements.txt"
  fi
fi

# Validate both the system GTK runtime and the project backend environment.
echo "Validating GTK4, Libadwaita and project dependencies..."
/usr/bin/python3 -c '
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
print("System GTK4 and Libadwaita imports OK")
'

$SUDO "$PREFIX/venv/bin/python3" -c '
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
import babel
import PIL
import ruamel.yaml
import serial
print("Project venv GTK, Pillow, pyserial, Babel and ruamel.yaml imports OK")
'

PYTHON_ENTRYPOINTS=(
  configure-gtk.py
  configure_gtk_app.py
  main.py
  screen-control.py
  theme-editor-gtk.py
  video-manager-gtk.py
  video_manager_gtk_app.py
  video_manager.py
  video_manager_backend.py
  media-preparation-gtk.py
  media_preparation_gtk_app.py
  media-preparation.py
  display-detection.py
  gtk-checkup.py
  diagnostics.py
  diagnostics-gtk.py
  usercustomize.py
  library/runtime.py
  library/video_media.py
  library/media_preparation.py
  library/media_profiles.py
  library/display_detection.py
  library/main_app_diagnostics_integration.py
  tools/turzx_extract_assets.py
)

for relative in "${PYTHON_ENTRYPOINTS[@]}"; do
  [[ -f "$PREFIX/$relative" ]] || continue
  $SUDO "$PREFIX/venv/bin/python3" -m py_compile "$PREFIX/$relative"
done

if [[ -f "$PREFIX/gtk-checkup.py" ]]; then
  echo "Running installed application checkup..."
  (
    cd "$PREFIX"
    $SUDO "$PREFIX/venv/bin/python3" "$PREFIX/gtk-checkup.py" "$PREFIX"
  )
fi

# Native launcher.
TMP_LAUNCHER="$(mktemp)"
cat > "$TMP_LAUNCHER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export TURING_SMART_SCREEN_HOME="$PREFIX"
cd "$PREFIX"
exec "$PREFIX/venv/bin/python3" "$PREFIX/configure-gtk.py" "\$@"
EOF
chmod +x "$TMP_LAUNCHER"
$SUDO cp "$TMP_LAUNCHER" "$LAUNCHER"
rm -f "$TMP_LAUNCHER"

# Canonical desktop identity. The filename, Icon and GTK application ID must
# match for Wayland/Niri docks to associate the running window correctly.
TMP_DESKTOP="$(mktemp)"
cat > "$TMP_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$APP_NAME
GenericName=Hardware Monitor Display
Comment=Configure and manage the Turing Smart Screen display
Exec=$LAUNCHER
Icon=$APP_ID
Terminal=false
Categories=Settings;System;Utility;
StartupNotify=true
StartupWMClass=$APP_ID
DBusActivatable=false
X-GNOME-UsesNotifications=false
EOF
$SUDO cp "$TMP_DESKTOP" "$DESKTOP_FILE"
rm -f "$TMP_DESKTOP"

# Remove old mismatched launcher identities.
$SUDO rm -f "$DESKTOP_DIR/turing-smart-screen.desktop"
$SUDO rm -f \
  "$ICON_BASE/64x64/apps/turing-smart-screen.png" \
  "$ICON_BASE/128x128/apps/turing-smart-screen.png"

# Install icon using the same name as APP_ID for launcher, dock and tray.
ICON_SOURCE=""
for candidate in \
  "$PREFIX/res/icons/monitor-icon-17865/128.png" \
  "$PREFIX/res/icons/monitor-icon-17865/64.png" \
  "$PREFIX/res/icons/monitor-icon-17865/icon.png"
do
  if [[ -f "$candidate" ]]; then
    ICON_SOURCE="$candidate"
    break
  fi
done

if [[ -n "$ICON_SOURCE" ]]; then
  $SUDO cp "$ICON_SOURCE" "$ICON_64"
  $SUDO cp "$ICON_SOURCE" "$ICON_128"
else
  echo "Warning: application icon source was not found." >&2
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  $SUDO gtk-update-icon-cache -q "$(dirname "$(dirname "$ICON_BASE/64x64/apps")")" || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  $SUDO update-desktop-database "$DESKTOP_DIR" || true
fi

if [[ "$ENABLE_AUTOSTART" -eq 1 ]]; then
  if [[ "$MODE" == "system" ]]; then
    AUTOSTART_DIR="$HOME/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"
    cp "$DESKTOP_FILE" "$AUTOSTART_DIR/$APP_ID.desktop"
  else
    AUTOSTART_DIR="$HOME/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"
    cp "$DESKTOP_FILE" "$AUTOSTART_DIR/$APP_ID.desktop"
  fi
fi

echo
echo "$APP_NAME installed successfully."
echo "Run it with: $COMMAND_NAME"
echo "Or open it from your application launcher."
