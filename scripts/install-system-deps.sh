#!/usr/bin/env bash
# Install the native system packages required by Turing Smart Screen.
#
# Supported distribution families:
#   arch    Arch Linux, CachyOS, Manjaro, EndeavourOS, Garuda, Artix (pacman)
#   debian  Debian, Ubuntu, Linux Mint, Pop!_OS, elementary, Zorin (apt-get)
#   fedora  Fedora, Nobara, RHEL/CentOS/Rocky/AlmaLinux (dnf)
#
# The HTML renderer always needs the PyGObject cairo integration
# (gi._gi_cairo): WebKitGTK 4.1 hands frame snapshots back as cairo surfaces.
# Several distributions ship it in a separate package, so it is listed
# explicitly for every family.
set -euo pipefail

OS_RELEASE_FILE="${TURING_OS_RELEASE_FILE:-/etc/os-release}"
PRINT_ONLY=0

usage() {
  cat <<'EOF'
Usage: scripts/install-system-deps.sh [--print]

Install the system packages required by Turing Smart Screen.

Options:
  --print     Show the detected distribution family, package manager and
              package list without installing anything
  -h, --help  Show this help
EOF
}

for arg in "$@"; do
  case "$arg" in
    --print) PRINT_ONLY=1 ;;
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

OS_ID=""
OS_LIKE=""
OS_NAME="Linux"
if [[ -r "$OS_RELEASE_FILE" ]]; then
  # Parse in a subshell so os-release variables cannot leak into this script.
  eval "$(
    # shellcheck disable=SC1090
    . "$OS_RELEASE_FILE"
    printf 'OS_ID=%q\nOS_LIKE=%q\nOS_NAME=%q\n' \
      "${ID:-}" "${ID_LIKE:-}" "${PRETTY_NAME:-${NAME:-Linux}}"
  )"
fi

detect_family() {
  local word
  for word in $OS_ID $OS_LIKE; do
    case "$word" in
      arch|archarm|cachyos|manjaro|endeavouros|garuda|artix) echo arch; return ;;
      debian|ubuntu|linuxmint|pop|elementary|zorin|raspbian|kali) echo debian; return ;;
      fedora|rhel|centos|rocky|almalinux|nobara|ultramarine) echo fedora; return ;;
    esac
  done
  # Unknown os-release identity: fall back to the available package manager.
  if command -v pacman >/dev/null 2>&1; then
    echo arch
  elif command -v apt-get >/dev/null 2>&1; then
    echo debian
  elif command -v dnf >/dev/null 2>&1; then
    echo fedora
  else
    echo unknown
  fi
}

FAMILY="$(detect_family)"
PACKAGES=()
case "$FAMILY" in
  arch)
    MANAGER="pacman"
    PACKAGES=(
      python python-pip python-virtualenv python-gobject python-cairo
      gtk3 gtk4 libadwaita webkitgtk-6.0 webkit2gtk-4.1
      ffmpeg rsync git python-pillow python-pyserial python-babel
      desktop-file-utils xdg-utils acl libusb
    )
    ;;
  debian)
    MANAGER="apt-get"
    PACKAGES=(
      python3 python3-venv python3-pip python3-gi python3-gi-cairo python3-cairo
      gir1.2-gtk-3.0 gir1.2-gtk-4.0 gir1.2-adw-1
      gir1.2-webkit-6.0 gir1.2-webkit2-4.1
      ffmpeg rsync git desktop-file-utils xdg-utils acl libusb-1.0-0
    )
    ;;
  fedora)
    MANAGER="dnf"
    # python3-gobject (not -base) carries gi._gi_cairo on Fedora.
    PACKAGES=(
      python3 python3-pip python3-gobject python3-cairo
      gtk3 gtk4 libadwaita webkitgtk6.0 webkit2gtk4.1
      rsync git desktop-file-utils xdg-utils acl libusb1
    )
    # Keep an existing (e.g. RPM Fusion) ffmpeg instead of forcing a swap.
    if ! command -v ffmpeg >/dev/null 2>&1; then
      PACKAGES+=(ffmpeg-free)
    fi
    ;;
  *)
    MANAGER=""
    ;;
esac

if [[ "$PRINT_ONLY" -eq 1 ]]; then
  echo "system: $OS_NAME"
  echo "family: $FAMILY"
  echo "manager: ${MANAGER:-none}"
  echo "packages: ${PACKAGES[*]:-}"
  exit 0
fi

if [[ "$FAMILY" == "unknown" ]]; then
  echo "Automatic dependency installation is not available for: $OS_NAME" >&2
  echo "Supported families: Arch (pacman), Debian/Ubuntu (apt-get), Fedora (dnf)." >&2
  echo "Install manually: Python 3 with venv and pip, PyGObject with its cairo integration (gi._gi_cairo)," >&2
  echo "pycairo, GTK 3/4 and Libadwaita introspection data, WebKitGTK 6.0 and 4.1 introspection data," >&2
  echo "FFmpeg/FFprobe with libx264, rsync, Git, libusb, desktop-file-utils, xdg-utils and acl." >&2
  echo "Then re-run ./install.sh --no-deps" >&2
  exit 0
fi

if ! command -v "$MANAGER" >/dev/null 2>&1; then
  echo "Detected $OS_NAME ($FAMILY family), but $MANAGER is not available." >&2
  exit 1
fi

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    echo "Root privileges are required to install packages: install sudo or run as root." >&2
    exit 1
  fi
}

echo "Installing $FAMILY-family dependencies for $OS_NAME with $MANAGER..."
case "$FAMILY" in
  arch)
    as_root pacman -S --needed "${PACKAGES[@]}"
    ;;
  debian)
    as_root apt-get update
    # Older releases may lack a WebKitGTK API version; skip what the
    # configured repositories do not provide instead of failing outright.
    AVAILABLE=()
    for package in "${PACKAGES[@]}"; do
      if apt-cache show --no-all-versions "$package" >/dev/null 2>&1; then
        AVAILABLE+=("$package")
      else
        echo "Warning: package not available in the configured repositories: $package" >&2
      fi
    done
    as_root apt-get install "${AVAILABLE[@]}"
    ;;
  fedora)
    if dnf --version 2>/dev/null | head -n 1 | grep -q -i dnf5; then
      as_root dnf install --skip-unavailable "${PACKAGES[@]}"
    else
      as_root dnf install --setopt=strict=0 "${PACKAGES[@]}"
    fi
    ;;
esac

# Media preparation encodes H.264 with libx264. Fedora's ffmpeg-free (and some
# minimal builds elsewhere) omit that encoder.
if command -v ffmpeg >/dev/null 2>&1 && ! ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libx264; then
  echo "Warning: the installed ffmpeg has no libx264 encoder; video preparation will not work." >&2
  if [[ "$FAMILY" == "fedora" ]]; then
    echo "On Fedora, enable RPM Fusion and run: sudo dnf swap ffmpeg-free ffmpeg --allowerasing" >&2
  fi
fi
