#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! /usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1")' >/dev/null 2>&1; then
  echo "GTK4/Libadwaita Python bindings are missing." >&2
  echo "Install them with:" >&2
  echo "  sudo pacman -S python-gobject gtk4 libadwaita" >&2
  exit 1
fi

exec /usr/bin/python3 configure-gtk.py "$@"
