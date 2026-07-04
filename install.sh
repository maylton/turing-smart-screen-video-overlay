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
CHECK_ONLY=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Install Turing Smart Screen as a native Linux desktop application.

Options:
  --system          Install in /opt and /usr/local (requires sudo)
  --no-deps         Do not install system packages
  --autostart       Start the application automatically after login
  --fresh           Replace installed themes/configuration instead of preserving them
  --check-only      Run installer readiness diagnostics without installing anything
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
    --check-only) CHECK_ONLY=1 ;;
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

status_line() {
  local label="$1"
  local value="$2"
  printf '  %-34s %s\n' "$label" "$value"
}

command_check() {
  local command_name="$1"
  if command -v "$command_name" >/dev/null 2>&1; then
    status_line "$command_name" "OK ($(command -v "$command_name"))"
    return 0
  fi
  status_line "$command_name" "missing"
  return 1
}

python_check() {
  local label="$1"
  local code="$2"
  if /usr/bin/python3 -c "$code" >/dev/null 2>&1; then
    status_line "$label" "OK"
    return 0
  fi
  status_line "$label" "missing or not importable"
  return 1
}

load_os_release() {
  OS_ID="unknown"
  OS_ID_LIKE=""
  OS_NAME="unknown Linux"
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_ID_LIKE="${ID_LIKE:-}"
    OS_NAME="${PRETTY_NAME:-${NAME:-unknown Linux}}"
  fi
}

detect_package_manager() {
  if command -v pacman >/dev/null 2>&1; then
    echo "pacman"
  elif command -v apt-get >/dev/null 2>&1; then
    echo "apt"
  elif command -v dnf >/dev/null 2>&1; then
    echo "dnf"
  elif command -v zypper >/dev/null 2>&1; then
    echo "zypper"
  else
    echo "unknown"
  fi
}

package_hint() {
  local manager="$1"
  case "$manager" in
    pacman)
      echo "sudo pacman -S --needed python python-pip python-virtualenv python-gobject gtk4 libadwaita ffmpeg rsync git tk python-pillow desktop-file-utils"
      ;;
    apt)
      echo "sudo apt install python3 python3-pip python3-venv python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 ffmpeg rsync git python3-tk python3-pil desktop-file-utils"
      ;;
    dnf)
      echo "sudo dnf install python3 python3-pip python3-virtualenv python3-gobject gtk4 libadwaita ffmpeg rsync git python3-tkinter python3-pillow desktop-file-utils"
      ;;
    zypper)
      echo "sudo zypper install python3 python3-pip python3-virtualenv python3-gobject gtk4 libadwaita ffmpeg rsync git python3-tk python3-Pillow desktop-file-utils"
      ;;
    *)
      echo "Install Python 3, pip, venv, PyGObject, GTK4, Libadwaita, ffmpeg, rsync, Git, Tk, Pillow and desktop-file-utils with your distro package manager."
      ;;
  esac
}

suggested_device_groups() {
  local os_key="${OS_ID} ${OS_ID_LIKE}"
  case "$os_key" in
    *arch*|*cachyos*|*manjaro*)
      echo "uucp lock"
      ;;
    *debian*|*ubuntu*|*linuxmint*|*pop*)
      echo "dialout plugdev"
      ;;
    *fedora*|*rhel*|*centos*|*rocky*|*almalinux*)
      echo "dialout lock"
      ;;
    *opensuse*|*suse*)
      echo "dialout uucp lock"
      ;;
    *)
      echo "dialout uucp plugdev lock"
      ;;
  esac
}

existing_groups_from_candidates() {
  local existing=()
  local group
  for group in "$@"; do
    if getent group "$group" >/dev/null 2>&1; then
      existing+=("$group")
    fi
  done
  printf '%s\n' "${existing[@]}"
}

user_in_group() {
  local group="$1"
  id -nG "$USER" 2>/dev/null | tr ' ' '\n' | grep -Fxq "$group"
}

serial_devices() {
  local candidate
  for candidate in /dev/ttyACM* /dev/ttyUSB* /dev/serial/by-id/*; do
    [[ -e "$candidate" ]] || continue
    printf '%s\n' "$candidate"
  done | sort -u
}

run_device_permission_check() {
  echo
  echo "Hardware permission readiness:"
  local groups_text
  groups_text="$(suggested_device_groups)"
  # shellcheck disable=SC2206
  local candidate_groups=( $groups_text )
  mapfile -t existing_groups < <(existing_groups_from_candidates "${candidate_groups[@]}")

  if [[ "${#existing_groups[@]}" -gt 0 ]]; then
    status_line "Distro group candidates" "${existing_groups[*]}"
  else
    status_line "Distro group candidates" "$groups_text (none of these groups exist yet)"
  fi

  mapfile -t devices < <(serial_devices)
  if [[ "${#devices[@]}" -eq 0 ]]; then
    status_line "Serial devices" "none detected now"
    echo "  Connect the display and rerun: ./install.sh --check-only"
    if [[ "${#existing_groups[@]}" -gt 0 ]]; then
      echo "  If the display later appears as /dev/ttyACM* or /dev/ttyUSB*, the likely fix is one of:"
      local group
      for group in "${existing_groups[@]}"; do
        if user_in_group "$group"; then
          echo "    already in $group"
        else
          echo "    sudo usermod -aG $group \"$USER\""
        fi
      done
      echo "  Group changes require logout/login before they affect new sessions."
    fi
    return 0
  fi

  local device owner group mode
  for device in "${devices[@]}"; do
    owner="$(stat -Lc '%U' "$device" 2>/dev/null || echo unknown)"
    group="$(stat -Lc '%G' "$device" 2>/dev/null || echo unknown)"
    mode="$(stat -Lc '%A' "$device" 2>/dev/null || echo unknown)"
    status_line "$device" "owner=$owner group=$group mode=$mode"
    if [[ "$group" != "unknown" ]] && user_in_group "$group"; then
      status_line "Access group $group" "current user is already a member"
    elif [[ "$group" != "unknown" ]] && getent group "$group" >/dev/null 2>&1; then
      status_line "Access group $group" "current user is not a member"
      echo "  Suggested fix: sudo usermod -aG $group \"$USER\""
      echo "  Then log out and log in again."
    else
      status_line "Access group" "could not determine a usable group for $device"
    fi
  done
}

run_readiness_check() {
  load_os_release
  local manager
  manager="$(detect_package_manager)"

  echo "$APP_NAME installer readiness check"
  echo "======================================"
  status_line "Source directory" "$SOURCE_DIR"
  status_line "Install mode" "$MODE"
  status_line "Install prefix" "$PREFIX"
  status_line "Launcher" "$LAUNCHER"
  status_line "Desktop file" "$DESKTOP_FILE"
  status_line "OS" "$OS_NAME"
  status_line "Package manager" "$manager"
  status_line "Dependency hint" "$(package_hint "$manager")"

  echo
  echo "Project files:"
  [[ -f "$SOURCE_DIR/main.py" ]] && status_line "main.py" "OK" || status_line "main.py" "missing"
  [[ -f "$SOURCE_DIR/configure-gtk.py" ]] && status_line "configure-gtk.py" "OK" || status_line "configure-gtk.py" "missing"
  [[ -f "$SOURCE_DIR/requirements.txt" ]] && status_line "requirements.txt" "OK" || status_line "requirements.txt" "missing"
  if [[ -f "$SOURCE_DIR/requirements.txt" ]] && grep -q 'git+' "$SOURCE_DIR/requirements.txt"; then
    status_line "requirements network" "contains git-based dependency; Git/network may be required during pip install"
  fi

  echo
  echo "Command readiness:"
  command_check python3 || true
  command_check rsync || true
  command_check git || true
  command_check ffmpeg || true
  command_check desktop-file-validate || true
  command_check update-desktop-database || true
  command_check gtk-update-icon-cache || true

  echo
  echo "Python/runtime readiness:"
  if /usr/bin/python3 -m venv --help >/dev/null 2>&1; then
    status_line "python3 -m venv" "OK"
  else
    status_line "python3 -m venv" "missing; install python venv support for your distro"
  fi
  python_check "GTK4/Libadwaita" 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); from gi.repository import Adw, Gtk' || true
  python_check "Pillow" 'import PIL' || true
  python_check "PyYAML" 'import yaml' || true

  if [[ -x "$PREFIX/venv/bin/python3" ]]; then
    if "$PREFIX/venv/bin/python3" -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); from gi.repository import Adw, Gtk; import PIL; import yaml; import ruamel.yaml' >/dev/null 2>&1; then
      status_line "installed venv" "OK"
    else
      status_line "installed venv" "exists, but one or more runtime imports failed"
    fi
  else
    status_line "installed venv" "not present yet; install.sh will create it"
  fi

  echo
  echo "PATH readiness:"
  case ":$PATH:" in
    *":$BIN_DIR:"*) status_line "$BIN_DIR in PATH" "OK" ;;
    *)
      status_line "$BIN_DIR in PATH" "missing"
      echo "  Add this to your shell profile if the command is not found after install:"
      echo "    export PATH=\"$BIN_DIR:\$PATH\""
      ;;
  esac

  run_device_permission_check

  echo
  echo "Check complete. No files were installed or modified."
}

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  run_readiness_check
  exit 0
fi

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
    echo "Run ./install.sh --check-only to see a distro-specific dependency hint." >&2
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
import yaml
import ruamel.yaml
print("Project venv GTK, Pillow, PyYAML and ruamel.yaml imports OK")
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
  library/theme_export_preflight.py
  library/theme_generated_media.py
  library/theme_media_transform.py
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
