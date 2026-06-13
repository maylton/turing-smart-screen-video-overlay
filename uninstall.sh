#!/usr/bin/env bash
set -euo pipefail

APP_ID="io.github.turing.SmartScreen"
MODE="${1:-user}"

if [[ "$MODE" == "--system" || "$MODE" == "system" ]]; then
  sudo rm -rf /opt/turing-smart-screen
  sudo rm -f /usr/local/bin/turing-smart-screen
  sudo rm -f "/usr/share/applications/$APP_ID.desktop"
  sudo rm -f /usr/share/applications/turing-smart-screen.desktop
  sudo rm -f "/usr/share/icons/hicolor/64x64/apps/$APP_ID.png"
  sudo rm -f "/usr/share/icons/hicolor/128x128/apps/$APP_ID.png"
else
  rm -rf "$HOME/.local/share/turing-smart-screen"
  rm -f "$HOME/.local/bin/turing-smart-screen"
  rm -f "$HOME/.local/share/applications/$APP_ID.desktop"
  rm -f "$HOME/.local/share/applications/turing-smart-screen.desktop"
  rm -f "$HOME/.local/share/icons/hicolor/64x64/apps/$APP_ID.png"
  rm -f "$HOME/.local/share/icons/hicolor/128x128/apps/$APP_ID.png"
  rm -f "$HOME/.config/autostart/$APP_ID.desktop"
fi

echo "Turing Smart Screen and its installed helpers were removed."
