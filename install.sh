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

if [[ "$INSTALL_DEPS" -eq 1 ]]; then
  if command -v pacman >/dev/null 2>&1; then
    echo "Installing Arch/CachyOS dependencies..."
    sudo pacman -S --needed \
      python python-pip python-virtualenv python-gobject \
      gtk4 libadwaita ffmpeg rsync git tk python-pillow \
      desktop-file-utils
  else
    echo "Automatic dependency installation currently supports Arch/CachyOS." >&2
    echo "Required: Python 3, PyGObject, GTK4, Libadwaita, ffmpeg, rsync, Git, Tk and Pillow." >&2
  fi
fi

if [[ ! -f "$SOURCE_DIR/main.py" ]]; then
  echo "main.py was not found in: $SOURCE_DIR" >&2
  echo "Run install.sh from the complete project directory." >&2
  exit 1
fi

if [[ ! -f "$SOURCE_DIR/configure-gtk.py" ]]; then
  echo "configure-gtk.py was not found." >&2
  exit 1
fi

echo "Installing $APP_NAME in: $PREFIX"

$SUDO mkdir -p \
  "$PREFIX" \
  "$BIN_DIR" \
  "$DESKTOP_DIR" \
  "$ICON_BASE/64x64/apps" \
  "$ICON_BASE/128x128/apps"

BACKUP_DIR=""
if [[ -d "$PREFIX" ]] && [[ "$PRESERVE_USER_DATA" -eq 1 ]]; then
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

if [[ "$MODE" == "system" ]]; then
  sudo rsync "${RSYNC_ARGS[@]}" "$SOURCE_DIR/" "$PREFIX/"
else
  rsync "${RSYNC_ARGS[@]}" "$SOURCE_DIR/" "$PREFIX/"
fi

# Use the current GTK launcher from the checked-out branch. Do not prefer
# configure-gtk-final.py here: local leftover files with that name can mask the
# branch's real configure-gtk.py and make installed smoke tests exercise stale UI.

if [[ -f "$SOURCE_DIR/main-final.py" ]]; then
  $SUDO cp "$SOURCE_DIR/main-final.py" "$PREFIX/main.py"
fi

if [[ -f "$SOURCE_DIR/screen-control.py" ]]; then
  $SUDO cp "$SOURCE_DIR/screen-control.py" "$PREFIX/screen-control.py"
  $SUDO chmod +x "$PREFIX/screen-control.py"
fi

if [[ -f "$SOURCE_DIR/gtk-checkup.py" ]]; then
  $SUDO cp "$SOURCE_DIR/gtk-checkup.py" "$PREFIX/gtk-checkup.py"
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
import PIL
import ruamel.yaml
print("Project venv GTK, Pillow and ruamel.yaml imports OK")
'

PYTHON_ENTRYPOINTS=(
  sitecustomize.py
  theme_gallery_card_polish.py
  turing-smart-screen-main.py
  configure-gtk.py
  configure_gtk_app.py
  main.py
  screen-control.py
  theme-editor-gtk.py
  theme-gallery-gtk.py
  turing-smart-screen-gtk.py
  video-manager-gtk.py
  video_manager_gtk_app.py
  video_manager.py
  video_manager_backend.py
  media-preparation-gtk.py
  media_preparation_gtk_app.py
  media-preparation.py
  display-detection.py
  gtk-checkup.py
  library/runtime.py
  library/theme_gallery.py
  library/embedded_theme_editor.py
  library/embedded_theme_editor_runtime.py
  library/embedded_video_manager.py
  library/embedded_video_manager_runtime.py
  library/main_app_ui_polish.py
  library/theme_preview_mock_data.py
  library/theme_preview_renderer.py
  library/runtime_rev_c_image_guard.py
  library/video_media.py
  library/media_preparation.py
  library/media_profiles.py
  library/display_detection.py
)

for relative in "${PYTHON_ENTRYPOINTS[@]}"; do
  [[ -f "$PREFIX/$relative" ]] || continue
  $SUDO "$PREFIX/venv/bin/python3" -m py_compile "$PREFIX/$relative"
done

if [[ -f "$PREFIX/gtk-checkup.py" ]]; then
  echo "Running installed application checkup..."
  (
    cd "$PREFIX"
    /usr/bin/python3 "$PREFIX/gtk-checkup.py" "$PREFIX"
  )
fi

# Native launcher.
TMP_LAUNCHER="$(mktemp)"
cat > "$TMP_LAUNCHER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export TURING_SMART_SCREEN_HOME="$PREFIX"
export PYTHONPATH="$PREFIX\${PYTHONPATH:+:\$PYTHONPATH}"
cd "$PREFIX"
exec /usr/bin/python3 "$PREFIX/turing-smart-screen-main.py" "\$@"
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

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$DESKTOP_FILE" || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q "$ICON_BASE" >/dev/null 2>&1 || true
fi

if [[ "$ENABLE_AUTOSTART" -eq 1 ]]; then
  AUTOSTART_DIR="$HOME/.config/autostart"
  AUTOSTART_FILE="$AUTOSTART_DIR/$APP_ID.desktop"
  mkdir -p "$AUTOSTART_DIR"
  cp "$DESKTOP_FILE" "$AUTOSTART_FILE"
  echo "Autostart enabled: $AUTOSTART_FILE"
fi

echo "Installed successfully."
echo "Run: $COMMAND_NAME"
