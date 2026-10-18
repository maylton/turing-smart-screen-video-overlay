# Flatpak packaging

This directory contains the packaging support for the first direct GitHub
Flatpak preview of Turing Smart Screen.

## Scope

The first release targets **x86_64** and application version `0.9.0-dev1`.
The packaging revision is stored in `release-version.txt` so Flatpak packaging
fixes can be released without pretending that the core application version has
changed.

The bundle uses:

- `org.gnome.Platform//50` and `org.gnome.Sdk//50`;
- GTK4 + Libadwaita for the main application shell;
- GTK3 + WebKit2GTK 4.1 from the GNOME runtime for the integrated HTML renderer;
- Freedesktop `codecs-extra//25.08-extra` for the codec-enabled FFmpeg stack;
- Python dependencies generated offline with `flatpak-pip-generator`;
- `pyamdgpuinfo 2.1.8` for AMD GPU support on x86_64.

## Why there is a bootstrap layer

The current application intentionally treats its project root as writable:
`config.yaml`, installed themes, generated previews/media and editor operations
live beside the Python sources. Flatpak mounts `/app` read-only.

`./turing-smart-screen-bootstrap.py` therefore keeps the packaged source as an
immutable seed under `/app/share/turing-smart-screen` and maintains a writable
working copy under the app's private `XDG_DATA_HOME`. On a packaging update it
refreshes application-owned code/resources while preserving:

- `config.yaml`;
- existing theme directories;
- user video/media directories.

The launcher also gives code that uses `Path.home()` an app-private HOME instead
of granting the Flatpak access to the user's whole home directory.

## Hardware permissions

This application is unusual for a desktop Flatpak because its primary purpose
is to control USB hardware.

The manifest currently uses `--device=all`. That is deliberate: supported
models can appear both as `/dev/ttyACM*` / `/dev/ttyUSB*` serial devices and as
raw USB devices, and current Flatpak permissions do not provide a sufficiently
narrow tty rule for all of them.

`--device=all` does **not** replace host Unix permissions. A Flatpak cannot
install `/etc/udev/rules.d` from inside its sandbox, so the release also ships a
small hardware-setup archive containing:

- `scripts/configure-hardware-access.sh`;
- `packaging/70-turing-smart-screen.rules`.

Run that helper on the host when using a physical display.

## Generate Python dependency sources

Install the GNOME 50 SDK and the generator first:

```bash
flatpak remote-add --user --if-not-exists flathub \
  https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Platform//50 org.gnome.Sdk//50 \
  org.freedesktop.Platform.codecs-extra//25.08-extra
python3 -m pip install --user flatpak_pip_generator==2026.5.28
bash flatpak/generate-python-deps.sh
```

This creates `flatpak/python3-requirements.json`. It is generated immediately
before the build so Python-version markers and platform wheels are resolved
against the actual GNOME 50 SDK rather than the host Python installation.

## Build locally

After generating the dependency manifest:

```bash
BUILD_DIR="$(mktemp -d)"
REPO_DIR="$(mktemp -d)"

flatpak-builder --user --force-clean --default-branch=stable \
  --install-deps-from=flathub --repo="$REPO_DIR" \
  "$BUILD_DIR" io.github.turing.SmartScreen.yml

flatpak build-bundle --arch=x86_64 \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
  "$REPO_DIR" Turing-Smart-Screen.flatpak \
  io.github.turing.SmartScreen stable
```

Install the resulting bundle with:

```bash
flatpak install --user ./Turing-Smart-Screen.flatpak
flatpak run io.github.turing.SmartScreen
```

## CI validation

`.github/workflows/flatpak.yml` builds and installs the Flatpak, then verifies:

- all packaged Python imports;
- GTK4 and Libadwaita;
- GTK3 and WebKit2GTK 4.1;
- Python byte-compilation of the packaged project;
- writable-payload initialization;
- `ffmpeg` and `ffprobe` availability;
- the `libx264` encoder required by media preparation.

Only a build that passes those checks is eligible for the GitHub pre-release.

## Not yet a Flathub submission

This packaging is intentionally a direct GitHub preview first. Before a Flathub
submission, the project should do a separate review of application-ID ownership,
permission minimization, screenshots/AppStream presentation, hardware access on
more distributions, and aarch64 dependency/build coverage.
