#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULE_SOURCE="$SOURCE_DIR/packaging/70-turing-smart-screen.rules"
RULE_DEST="/etc/udev/rules.d/70-turing-smart-screen.rules"

TARGET_USER="${TURING_INSTALL_USER:-${SUDO_USER:-${USER:-}}}"
if [[ -z "$TARGET_USER" ]]; then
  TARGET_USER="$(id -un)"
fi
if [[ "$TARGET_USER" == "root" && -n "${SUDO_USER:-}" ]]; then
  TARGET_USER="$SUDO_USER"
fi

OS_ID="unknown"
OS_LIKE=""
OS_NAME="Linux"
if [[ -r /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_LIKE="${ID_LIKE:-}"
  OS_NAME="${PRETTY_NAME:-${NAME:-Linux}}"
fi

echo "Detected system: $OS_NAME"
echo "Configuring Turing Smart Screen hardware access for user: $TARGET_USER"

declare -a SERIAL_GROUPS=()

add_group_candidate() {
  local group="$1"
  [[ -n "$group" ]] || return 0
  [[ "$group" == "root" ]] && return 0
  if getent group "$group" >/dev/null 2>&1; then
    local existing
    for existing in "${SERIAL_GROUPS[@]:-}"; do
      [[ "$existing" == "$group" ]] && return 0
    done
    SERIAL_GROUPS+=("$group")
  fi
}

# Prefer the group actually owning a connected serial endpoint.
shopt -s nullglob
for device in /dev/ttyACM* /dev/ttyUSB*; do
  [[ -e "$device" ]] || continue
  group="$(stat -c '%G' "$device" 2>/dev/null || true)"
  add_group_candidate "$group"
done
shopt -u nullglob

# Add the distro convention as a persistent fallback for future reconnects.
case " $OS_ID $OS_LIKE " in
  *" arch "*|*" cachyos "*|*" manjaro "*|*" endeavouros "*|*" artix "*)
    add_group_candidate "uucp"
    ;;
  *" debian "*|*" ubuntu "*|*" fedora "*|*" rhel "*|*" centos "*|*" suse "*|*" opensuse "*)
    add_group_candidate "dialout"
    ;;
  *)
    add_group_candidate "uucp"
    add_group_candidate "dialout"
    ;;
esac

if [[ -f "$RULE_SOURCE" ]] && command -v udevadm >/dev/null 2>&1; then
  echo "Installing udev hardware-access rules..."
  sudo install -Dm0644 "$RULE_SOURCE" "$RULE_DEST"
  sudo udevadm control --reload-rules

  # Re-apply rules to already connected devices so a fresh install can work
  # immediately when systemd-logind/uaccess is available.
  sudo udevadm trigger --subsystem-match=tty --action=change || true
  sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=1cbe --action=change || true
  sudo udevadm settle || true
else
  echo "udev rules could not be installed; falling back to serial groups." >&2
fi

GROUP_MEMBERSHIP_CHANGED=0
SESSION_REFRESH_NEEDED=0
CURRENT_USER="$(id -un)"

for group in "${SERIAL_GROUPS[@]:-}"; do
  [[ -n "$group" ]] || continue
  if id -nG "$TARGET_USER" | tr ' ' '\n' | grep -Fxq "$group"; then
    echo "User already belongs to serial access group: $group"
    if [[ "$TARGET_USER" == "$CURRENT_USER" ]] && ! id -nG | tr ' ' '\n' | grep -Fxq "$group"; then
      SESSION_REFRESH_NEEDED=1
    fi
    continue
  fi

  echo "Adding $TARGET_USER to serial access group: $group"
  sudo usermod -aG "$group" "$TARGET_USER"
  GROUP_MEMBERSHIP_CHANGED=1
  SESSION_REFRESH_NEEDED=1
done

ACCESSIBLE=0
FOUND_SERIAL=0
shopt -s nullglob
for device in /dev/ttyACM* /dev/ttyUSB*; do
  [[ -e "$device" ]] || continue
  FOUND_SERIAL=1
  if [[ ! -r "$device" || ! -w "$device" ]]; then
    # Group changes only reach new login sessions. Apply a user ACL to the
    # currently connected endpoint so installation can finish with a usable
    # display immediately; udev/group rules cover future reconnects.
    if command -v setfacl >/dev/null 2>&1; then
      sudo setfacl -m "u:${TARGET_USER}:rw" "$device" || true
    fi
  fi

  if [[ -r "$device" && -w "$device" ]]; then
    echo "Serial endpoint is accessible now: $device"
    ACCESSIBLE=1
  else
    owner="$(stat -c '%U:%G %a' "$device" 2>/dev/null || true)"
    echo "Serial endpoint is not accessible in this process yet: $device ($owner)" >&2
  fi
done
shopt -u nullglob

if [[ "$FOUND_SERIAL" -eq 0 ]]; then
  echo "No ttyACM/ttyUSB endpoint is connected right now; persistent access rules are installed."
elif [[ "$ACCESSIBLE" -eq 0 && ( "$GROUP_MEMBERSHIP_CHANGED" -eq 1 || "$SESSION_REFRESH_NEEDED" -eq 1 ) ]]; then
  echo
  echo "Hardware access was configured, but this login session has not inherited the new group yet." >&2
  echo "The udev uaccess rule may make the device available immediately; otherwise sign out and back in once." >&2
fi
