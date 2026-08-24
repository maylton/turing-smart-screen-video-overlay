#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Pin the official generator implementation instead of depending on a console
# script being exposed by a PyPI wrapper. This keeps local and CI generation
# reproducible while still resolving packages against the installed GNOME SDK.
GENERATOR_COMMIT="737c0085912f9f7dabf9341d4608e2a77a51a73a"
GENERATOR_URL="https://raw.githubusercontent.com/flatpak/flatpak-builder-tools/${GENERATOR_COMMIT}/pip/flatpak-pip-generator.py"
CACHE_ROOT="${XDG_CACHE_HOME:-${HOME}/.cache}/turing-smart-screen-flatpak"
GENERATOR_PATH="${CACHE_ROOT}/flatpak-pip-generator-${GENERATOR_COMMIT}.py"

if ! python3 -c 'import requirements, packaging' >/dev/null 2>&1; then
  echo "Python modules requirements-parser and packaging are required." >&2
  echo "Install them with: python3 -m pip install --user requirements-parser packaging" >&2
  exit 1
fi

if ! flatpak info --user org.gnome.Sdk//50 >/dev/null 2>&1 && \
   ! flatpak info --system org.gnome.Sdk//50 >/dev/null 2>&1; then
  echo "org.gnome.Sdk//50 must be installed before generating dependencies." >&2
  exit 1
fi

mkdir -p "$CACHE_ROOT"
if [[ ! -s "$GENERATOR_PATH" ]]; then
  GENERATOR_URL="$GENERATOR_URL" GENERATOR_PATH="$GENERATOR_PATH" python3 - <<'PY'
import os
import pathlib
import urllib.request

url = os.environ["GENERATOR_URL"]
target = pathlib.Path(os.environ["GENERATOR_PATH"])
temporary = target.with_suffix(target.suffix + ".tmp")
with urllib.request.urlopen(url, timeout=60) as response:
    temporary.write_bytes(response.read())
temporary.replace(target)
PY
fi

rm -f flatpak/python3-requirements.json
python3 "$GENERATOR_PATH" \
  --runtime='org.gnome.Sdk//50' \
  --requirements-file=flatpak/requirements-flatpak.txt \
  --output=flatpak/python3-requirements \
  --prefer-wheels=psutil,pycryptodome,pillow,numpy,pyamdgpuinfo \
  --wheel-arches=x86_64

test -s flatpak/python3-requirements.json
echo "Generated flatpak/python3-requirements.json with flatpak-builder-tools ${GENERATOR_COMMIT}"
