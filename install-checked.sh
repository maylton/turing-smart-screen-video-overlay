#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="user"

for arg in "$@"; do
  case "$arg" in
    --system) MODE="system" ;;
  esac
done

if [[ "$MODE" == "system" ]]; then
  PREFIX="/opt/turing-smart-screen"
  WRITE_COMMAND=(sudo /usr/bin/python3)
else
  PREFIX="$HOME/.local/share/turing-smart-screen"
  WRITE_COMMAND=(/usr/bin/python3)
fi

/usr/bin/python3 "$SOURCE_DIR/scripts/installation-report.py" verify "$SOURCE_DIR"

bash "$SOURCE_DIR/install.sh" "$@"

"${WRITE_COMMAND[@]}" \
  "$SOURCE_DIR/scripts/installation-report.py" write \
  --source "$SOURCE_DIR" \
  --install-root "$PREFIX" \
  --mode "$MODE"

/usr/bin/python3 "$SOURCE_DIR/scripts/installation-report.py" verify "$PREFIX"

if [[ "$MODE" == "system" ]]; then
  sudo /usr/bin/python3 "$SOURCE_DIR/scripts/installation-report.py" show "$PREFIX"
else
  /usr/bin/python3 "$SOURCE_DIR/scripts/installation-report.py" show "$PREFIX"
fi
