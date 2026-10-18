#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
APP_ID="io.github.turing.SmartScreen"
SOURCE_APPIMAGE="${1:-$ROOT/dist/Turing-Smart-Screen-${VERSION}-x86_64.AppImage}"
INSTALL_DIR="$HOME/.local/opt/turing-smart-screen"
INSTALLED_APPIMAGE="$INSTALL_DIR/Turing-Smart-Screen.AppImage"
BIN_DIR="$HOME/.local/bin"
BIN_LAUNCHER="$BIN_DIR/turing-smart-screen"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/$APP_ID.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/128x128/apps"
ICON_FILE="$ICON_DIR/$APP_ID.png"
FLATPAK_DATA="$HOME/.var/app/$APP_ID"

if [[ ! -f "$SOURCE_APPIMAGE" ]]; then
  echo "AppImage not found: $SOURCE_APPIMAGE" >&2
  echo "Build it first with:" >&2
  echo "  bash packaging/appimage/build-appimage-container.sh" >&2
  exit 1
fi

chmod +x "$SOURCE_APPIMAGE"

# Validate the bundle before removing the installed Flatpak.
echo "Validating AppImage runtime..."
APPIMAGE_EXTRACT_AND_RUN=1 "$SOURCE_APPIMAGE" --appimage-smoke-test

echo
echo "Stopping and uninstalling the Flatpak package..."
if command -v flatpak >/dev/null 2>&1; then
  flatpak kill "$APP_ID" 2>/dev/null || true

  if flatpak info --user "$APP_ID" >/dev/null 2>&1; then
    flatpak uninstall --user -y "$APP_ID"
  elif flatpak info --system "$APP_ID" >/dev/null 2>&1; then
    flatpak uninstall --system -y "$APP_ID"
  else
    echo "Flatpak package is already absent."
  fi
fi

# Intentionally keep ~/.var/app/... until the AppImage has launched once: the
# AppImage migrates config.yaml, themes and video assets from that directory.
if [[ -d "$FLATPAK_DATA" ]]; then
  echo "Keeping Flatpak user data temporarily for automatic first-run migration:"
  echo "  $FLATPAK_DATA"
fi

# Remove only generated Flatpak build products, never the source checkout.
rm -rf \
  "$ROOT/build-flatpak" \
  "$ROOT/flatpak-repo" \
  "$ROOT/.flatpak-builder"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"
install -m0755 "$SOURCE_APPIMAGE" "$INSTALLED_APPIMAGE"

# Use extract-and-run so the installed app does not depend on host libfuse2.
rm -f "$BIN_LAUNCHER"
cat > "$BIN_LAUNCHER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export APPIMAGE_EXTRACT_AND_RUN=1
exec "$INSTALLED_APPIMAGE" "\$@"
EOF
chmod 0755 "$BIN_LAUNCHER"

install -m0644 \
  "$ROOT/res/icons/monitor-icon-17865/128.png" \
  "$ICON_FILE"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Turing Smart Screen
GenericName=Hardware Monitor Display
Comment=Configure and manage the Turing Smart Screen display
Exec=$BIN_LAUNCHER
Icon=$ICON_FILE
Terminal=false
Categories=Settings;System;Utility;
StartupNotify=true
StartupWMClass=$APP_ID
DBusActivatable=false
X-GNOME-UsesNotifications=false
EOF
chmod 0644 "$DESKTOP_FILE"

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate "$DESKTOP_FILE"
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" || true
fi

echo
echo "Turing Smart Screen AppImage installed successfully."
echo "Run it with:"
echo "  $BIN_LAUNCHER"
echo
echo "On first launch, keep the old Flatpak data until migration completes."
echo "After you confirm your config/themes are present, old Flatpak data may be removed with:"
echo "  rm -rf '$FLATPAK_DATA'"
