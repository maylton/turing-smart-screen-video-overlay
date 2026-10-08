# Turing Smart Screen for Linux

<p align="center">
  <strong>A Linux-first GTK4/Libadwaita desktop application for Turing Smart Screen-compatible displays</strong><br />
  Theme Gallery · Theme Editor · HTML/YAML themes · native video workflows · system monitoring
</p>

<p align="center">
  <img alt="Linux" src="https://img.shields.io/badge/Linux-focused-FCC624?style=for-the-badge&logo=linux&logoColor=black" />
  <img alt="Version" src="https://img.shields.io/badge/version-0.9.0-2ea44f?style=for-the-badge" />
  <img alt="Flatpak" src="https://img.shields.io/badge/Flatpak-x86__64-4A86CF?style=for-the-badge&logo=flatpak&logoColor=white" />
  <img alt="GTK4" src="https://img.shields.io/badge/GTK4%20%2B%20Libadwaita-desktop%20UI-4A86CF?style=for-the-badge" />
</p>

---

<!-- MAYLTON_FORK_OVERVIEW -->
## What is this?

This repository is a Linux-focused fork of
[`mathoudebine/turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python),
built around a GTK4/Libadwaita desktop experience while keeping the upstream
Python display and theme foundations.

The application brings the most common workflows into one interface:

- start, stop and monitor the connected display;
- automatically detect compatible hardware;
- browse and activate themes from a visual Theme Gallery;
- edit YAML themes with an embedded Theme Editor;
- run HTML themes and transparent overlays;
- prepare GIF/video media for compatible displays;
- manage native video on validated Rev. C hardware;
- inspect system telemetry, including AMD GPU metrics on Linux;
- keep monitor execution available from the system tray.

The project is **not official vendor software** and is not maintained by the
upstream project.

---

## Screenshots

<p align="center">
  <img src="docs/screenshots/overview.png" alt="Overview page showing active theme, monitor process, connected display, and quick actions" width="48%" />
  <img src="docs/screenshots/theme-gallery.png" alt="Theme Gallery showing installed compatible themes" width="48%" />
</p>

<p align="center">
  <img src="docs/screenshots/theme-editor.png" alt="Embedded Theme Editor with live preview and theme properties" width="96%" />
</p>

<p align="center">
  <em>Overview, Theme Gallery, and embedded Theme Editor running on Linux.</em>
</p>

---

## Current status: 0.9.0

The application version is **0.9.0** and `main` is the canonical branch.

> [!IMPORTANT]
> No prebuilt package is published yet. The Flatpak and AppImage CI builds on
> `main` are currently failing, so the
> [Releases page](https://github.com/maylton/turing-smart-screen-video-overlay/releases)
> has no downloadable bundle. Use the native installer below, or build the
> Flatpak locally from [`packaging/flatpak`](packaging/flatpak/README.md).

### Native install

```bash
git clone https://github.com/maylton/turing-smart-screen-video-overlay.git
cd turing-smart-screen-video-overlay

./install.sh

turing-smart-screen
```

The installer:

- installs system packages for **Arch** (`pacman`), **Debian/Ubuntu** (`apt-get`)
  and **Fedora** (`dnf`) family distributions, including derivatives such as
  CachyOS, Manjaro, Linux Mint, Pop!_OS and Nobara;
- installs the udev rule and serial-group access for the display;
- creates a per-user application under `~/.local/share/turing-smart-screen`
  with a virtual environment that reuses the system PyGObject/GTK/WebKit
  bindings;
- runs an installed checkup, including the HTML renderer dependencies.

Preview the system packages for your distribution without installing anything:

```bash
scripts/install-system-deps.sh --print
```

Updates (`git pull --ff-only && ./install.sh --no-deps`) preserve
`config.yaml`, custom themes and local media. See
[`docs/INSTALLATION.md`](docs/INSTALLATION.md) for the full workflow, the
system-wide mode and troubleshooting.

> [!TIP]
> If the monitor reports a successful start but an HTML theme leaves the display
> dark, check `~/.local/share/turing-smart-screen/log.log` for
> `Couldn't find foreign struct converter for 'cairo.Surface'`. That means the
> PyGObject cairo integration is missing (`python3-gi-cairo` on Debian/Ubuntu);
> re-run `scripts/install-system-deps.sh`.

---

## Hardware validation

The upstream project supports multiple families of small USB displays. This fork
inherits much of that support, but fork-specific features have a narrower
physical validation scope.

| Area | Current status |
| --- | --- |
| Linux GTK4/Libadwaita app | Stable in 0.9.0 |
| Native installer | Arch, Debian/Ubuntu and Fedora families |
| Flatpak x86_64 packaging | Manifest available; CI build failing, no published bundle |
| AppImage packaging | CI job present; build failing, no published AppImage |
| Theme Gallery / Theme Manager | Implemented |
| Embedded Theme Editor | Implemented |
| HTML themes / overlays | Implemented |
| System tray control | Implemented |
| AMD GPU telemetry in Flatpak | Validated with app-local libdrm |
| Native Rev. C video/storage | Physically validated on one 2.1-inch profile |
| Broad hardware-family validation | Ongoing |
| Flathub distribution | Not submitted yet |

### Physically validated fork-specific profile

| Device/profile | Validation |
| --- | --- |
| Turing Smart Screen Rev. C 2.1-inch, ROM 88 | Physically validated |
| Native video playback/storage management | Validated on the profile above |
| HTML theme + native video overlay | Validated on the profile above |
| Raw USB reset/recovery permissions in Flatpak | Validated with host udev rules |
| Other Turing/TURZX revisions and sizes | Monitor support may work; media operations are not guaranteed |
| XuanFang / Kipye / WeAct / other devices | Inherited support may work; fork-specific media operations are not guaranteed |

---

## Main features

### GTK desktop app

The Overview provides display state, active theme, detected hardware, monitor PID
and quick actions. The monitor can keep running while the main window is hidden,
and the tray exposes display controls without requiring the window to stay open.

### Theme Gallery

The visual gallery supports:

- preview cards and current-theme state;
- compatibility information;
- import from folders, `.theme` packages and legacy archives;
- duplicate, rename and delete flows;
- export with preflight checks for missing or generated assets.

### Embedded Theme Editor

The editor keeps themes editable as project files while adding safer desktop
workflows:

- guarded/atomic saves;
- external change detection;
- element navigation and layer ordering;
- image transforms and crop controls;
- text/effect presets;
- generated-media tracking.

### HTML themes and overlays

HTML themes run through an offscreen WebKitGTK renderer in a separate worker
process and can be combined with native video on supported hardware. The
monitor restarts the worker with backoff if it stops, and the Rev. C transport
recovers from serial write stalls and transient kernel I/O errors. Renderer
failures are recorded in `log.log`. Authoring details live in
[`docs/HTML_THEME_AUTHORING_GUIDE.md`](docs/HTML_THEME_AUTHORING_GUIDE.md) and
[`docs/HTML_OVERLAY_DOCUMENT.md`](docs/HTML_OVERLAY_DOCUMENT.md).

### Media and native video

The media workflow can inspect source media with FFprobe, prepare device-sized
outputs, preview framing, and manage compatible native video storage. Hardware-
writing operations remain intentionally limited to validated profiles.

### AMD GPU telemetry in Flatpak

The Flatpak manifest bundles a current libdrm and builds `pyamdgpuinfo` from
source against the app-local libraries. This avoids the private manylinux libdrm copies
that previously looked for a missing `/usr/share/libdrm/amdgpu.ids` inside the
sandbox.

---

## Development and validation

Before publishing changes, run the release-readiness helper (it includes the
unit tests):

```bash
./scripts/verify-release-readiness.sh
```

`scripts/test-install.py --root <empty-dir>` exercises the native installer in an
isolated `HOME` without touching your real installation.

For Flatpak work, the repository also contains
[`packaging/flatpak/README.md`](packaging/flatpak/README.md) and a GitHub Actions
workflow that builds the repository, smoke-checks the exported app, creates a
single-file bundle and validates that `pyamdgpuinfo` is not using its bundled
manylinux `libdrm` copies.

---

## Important safety notice

> [!WARNING]
> Features that write to real display storage or change hardware state should be
> treated carefully. Fork-specific native media operations have not been
> physically validated across every supported display family.

Keep backups of custom themes/configuration and review commands before using
hardware-writing utilities. Ambiguous display detection is not used to silently
reconfigure the device.

---

## Development process disclosure

This fork has been developed through an iterative, heavily AI-assisted workflow,
with changes tested and refined in small loops. That speeds up experimentation,
but does not replace hardware validation or human code review. Contributions and
independent testing are welcome.

---

## Documentation

Useful project documentation includes:

- [`docs/INSTALLATION.md`](docs/INSTALLATION.md)
- [`docs/DISPLAY_DETECTION.md`](docs/DISPLAY_DETECTION.md)
- [`docs/DISPLAY_LIFECYCLE.md`](docs/DISPLAY_LIFECYCLE.md)
- [`docs/GPU_SELECTION.md`](docs/GPU_SELECTION.md)
- [`docs/HTML_THEME_AUTHORING_GUIDE.md`](docs/HTML_THEME_AUTHORING_GUIDE.md)
- [`docs/HTML_OVERLAY_DOCUMENT.md`](docs/HTML_OVERLAY_DOCUMENT.md)
- [`docs/MEDIA_PREPARATION.md`](docs/MEDIA_PREPARATION.md)
- [`docs/THEME_PACKAGE_FORMAT.md`](docs/THEME_PACKAGE_FORMAT.md)
- [`docs/YAML_THEME_MIGRATION.md`](docs/YAML_THEME_MIGRATION.md)
- [`CHANGELOG.md`](CHANGELOG.md)

---

## Relationship with upstream

This fork is based on and deeply indebted to
[`mathoudebine/turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python).

The fork intentionally has a broader Linux desktop scope than upstream. Small,
self-contained fixes and hardware findings may still be suitable for upstream
contribution when they can be separated cleanly.

---

## Contributing

Bug reports, hardware validation results, documentation fixes and focused code
contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and use this
repository's [issue tracker](https://github.com/maylton/turing-smart-screen-video-overlay/issues).

When reporting hardware issues, include the display model/revision, USB IDs,
Linux distribution, installation type (Flatpak/native), and relevant logs.

---

## Disclaimer

This project is **not affiliated, associated, authorized, endorsed by, or in any
way officially connected with Turing / XuanFang / Kipye brands**, or any of their
subsidiaries, affiliates, manufacturers, or sellers. Product and company names
remain the property of their respective owners.

For vendor applications, firmware or warranty support, use the manufacturer or
reseller channels.

---

## License

This fork follows the upstream project's GPL-3.0-or-later license. See
[`LICENSE`](LICENSE).
