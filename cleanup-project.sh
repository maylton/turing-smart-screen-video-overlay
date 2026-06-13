#!/usr/bin/env bash
set -euo pipefail

PROJECT="${1:-$PWD}"
MODE="${2:---dry-run}"

if [[ ! -f "$PROJECT/main.py" ]]; then
  echo "This does not look like the project directory: $PROJECT" >&2
  exit 1
fi

case "$MODE" in
  --dry-run|--apply) ;;
  *)
    echo "Usage: $0 PROJECT [--dry-run|--apply]" >&2
    exit 2
    ;;
esac

declare -a TARGETS=()

add_if_exists() {
  local path="$1"
  [[ -e "$path" ]] && TARGETS+=("$path")
}

# Backup directories created during our iterative patches.
add_if_exists "$PROJECT/.gtk-ui-backups"
add_if_exists "$PROJECT/.theme-editor-backups"

# Python caches.
while IFS= read -r -d '' path; do
  TARGETS+=("$path")
done < <(
  find "$PROJECT" \
    -type d -name '__pycache__' -print0 2>/dev/null
)

while IFS= read -r -d '' path; do
  TARGETS+=("$path")
done < <(
  find "$PROJECT" \
    -type f \( -name '*.pyc' -o -name '*.pyo' \) -print0 2>/dev/null
)

# Temporary and old repair files created by the editors.
while IFS= read -r -d '' path; do
  TARGETS+=("$path")
done < <(
  find "$PROJECT/res/themes" \
    -type f \( \
      -name 'theme.yaml.tmp' -o \
      -name 'theme.yml.tmp' -o \
      -name '*.editor-backup' -o \
      -name '*.before-sequence-repair' -o \
      -name '*.tmp~' \
    \) -print0 2>/dev/null
)

# Common editor leftovers.
while IFS= read -r -d '' path; do
  TARGETS+=("$path")
done < <(
  find "$PROJECT" \
    -maxdepth 3 \
    -type f \( \
      -name '*~' -o \
      -name '*.swp' -o \
      -name '*.swo' -o \
      -name '.DS_Store' \
    \) -print0 2>/dev/null
)

# Old launchers/icons inside the source tree, if accidentally copied there.
add_if_exists "$PROJECT/turing-smart-screen.desktop"

if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "No disposable files were found."
  exit 0
fi

echo "The following disposable files/directories were found:"
printf '  %s\n' "${TARGETS[@]}"

echo
echo "Preserved:"
echo "  config.yaml"
echo "  res/themes/"
echo "  res/video/"
echo "  res/videos/"
echo "  venv/"
echo "  source files and installer files"

if [[ "$MODE" == "--dry-run" ]]; then
  echo
  echo "Dry run only. Nothing was removed."
  echo "Run again with --apply to delete these items."
  exit 0
fi

for path in "${TARGETS[@]}"; do
  rm -rf -- "$path"
done

echo
echo "Cleanup completed."
