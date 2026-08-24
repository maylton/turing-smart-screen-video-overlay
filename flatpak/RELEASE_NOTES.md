# Turing Smart Screen — first Flatpak preview

This is the first x86_64 Flatpak packaging preview of the Linux GTK application.
It packages the GTK4/Libadwaita app shell, GTK3/WebKit2 HTML renderer support,
Python runtime dependencies, FFmpeg/H.264 media preparation, and the writable
payload compatibility layer required by the current YAML/theme architecture.

## Install

1. Download the `.flatpak` bundle from this release.
2. Install it with `flatpak install --user ./Turing-Smart-Screen-*.flatpak`.
3. For physical USB/serial displays, also download and extract the
   `turing-smart-screen-flatpak-hardware-setup-*.tar.gz` asset and run
   `./scripts/configure-hardware-access.sh` from the extracted directory.
4. Launch with `flatpak run io.github.turing.SmartScreen` or from the desktop menu.

## Important limitations

- This is a development/pre-release build, matching application version
  `0.9.0-dev1`.
- The first release is built and smoke-tested on x86_64.
- Flatpak currently has no narrow tty permission that covers this application's
  serial devices. The manifest therefore uses `--device=all`; host udev rules
  still control actual device access.
- NVIDIA sensor data that depends on the host `nvidia-smi` executable may not be
  available inside the sandbox. AMD `pyamdgpuinfo` support is packaged and is
  tested at import/build level; physical GPU sensor visibility still depends on
  what the host exposes to Flatpak.
- This is a direct GitHub Flatpak bundle, not a Flathub submission yet.

The release workflow validates Python imports, GTK4/Libadwaita, GTK3/WebKit2
4.1, writable-payload initialization, `ffmpeg`/`ffprobe`, and availability of
the `libx264` encoder before publishing the bundle.
