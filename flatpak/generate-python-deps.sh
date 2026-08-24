#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v flatpak-pip-generator >/dev/null 2>&1; then
  echo "flatpak-pip-generator is required." >&2
  echo "Install it with: python3 -m pip install --user flatpak_pip_generator==2026.5.28" >&2
  exit 1
fi

if ! flatpak info --user org.gnome.Sdk//50 >/dev/null 2>&1 && \
   ! flatpak info --system org.gnome.Sdk//50 >/dev/null 2>&1; then
  echo "org.gnome.Sdk//50 must be installed before generating dependencies." >&2
  exit 1
fi

rm -f flatpak/python3-requirements.json
flatpak-pip-generator \
  --runtime='org.gnome.Sdk//50' \
  --requirements-file=flatpak/requirements-flatpak.txt \
  --output=flatpak/python3-requirements \
  --prefer-wheels=psutil,pycryptodome,pillow,numpy,pyamdgpuinfo \
  --wheel-arches=x86_64

test -s flatpak/python3-requirements.json
echo "Generated flatpak/python3-requirements.json"
