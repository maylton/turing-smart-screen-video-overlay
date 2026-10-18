#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
BUILD_ID="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || printf '%s' local)"
OUTPUT="Turing-Smart-Screen-${VERSION}-x86_64.AppImage"

if [[ -n "${CONTAINER_ENGINE:-}" ]]; then
  ENGINE="$CONTAINER_ENGINE"
elif command -v podman >/dev/null 2>&1; then
  ENGINE="podman"
elif command -v docker >/dev/null 2>&1; then
  ENGINE="docker"
else
  echo "Podman or Docker is required to build the AppImage." >&2
  exit 1
fi

mkdir -p "$ROOT/dist"
rm -f "$ROOT/dist/$OUTPUT" "$ROOT/dist/$OUTPUT.sha256"

echo "Building Turing Smart Screen AppImage with $ENGINE..."
echo "Source: $ROOT"
echo "Version: $VERSION"
echo "Build: $BUILD_ID"

"$ENGINE" run --rm \
  -e DEBIAN_FRONTEND=noninteractive \
  -e APP_VERSION="$VERSION" \
  -e APP_BUILD_ID="$BUILD_ID" \
  -e HOST_UID="$(id -u)" \
  -e HOST_GID="$(id -g)" \
  -v "$ROOT:/src:rw" \
  ubuntu:24.04 \
  bash -lc '
    set -euxo pipefail

    apt-get update
    apt-get install -y --no-install-recommends \
      ca-certificates wget rsync git file desktop-file-utils \
      build-essential python3-dev python3-pip pkg-config libdrm-dev \
      gtk-update-icon-cache libgdk-pixbuf-2.0-bin libglib2.0-bin \
      shared-mime-info gstreamer1.0-tools

    wget -q \
      "https://github.com/AppImageCrafters/appimage-builder/releases/download/Continuous/appimage-builder-1.1.1.dev32%2Bg2709a3b-x86_64.AppImage" \
      -O /tmp/appimage-builder.AppImage
    chmod +x /tmp/appimage-builder.AppImage

    cd /src/packaging/appimage
    rm -rf AppDir
    find . -maxdepth 1 -type f -name "*.AppImage" -delete

    export APPIMAGE_EXTRACT_AND_RUN=1
    /tmp/appimage-builder.AppImage --recipe AppImageBuilder.yml

    built="$(find . -maxdepth 1 -type f -name "*.AppImage" ! -name "appimage-builder*" -print -quit)"
    test -n "$built"

    output="/src/dist/Turing-Smart-Screen-${APP_VERSION}-x86_64.AppImage"
    mv "$built" "$output"
    chmod +x "$output"

    APPIMAGE_EXTRACT_AND_RUN=1 "$output" --appimage-smoke-test
    sha256sum "$output" > "$output.sha256"

    chown "$HOST_UID:$HOST_GID" "$output" "$output.sha256" 2>/dev/null || true
    ls -lh "$output" "$output.sha256"
  '

echo
echo "AppImage ready:"
echo "  $ROOT/dist/$OUTPUT"
echo "Checksum:"
echo "  $ROOT/dist/$OUTPUT.sha256"
