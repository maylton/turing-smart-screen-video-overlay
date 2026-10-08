# Installation, update, and validation

Turing Smart Screen for Linux supports two installation paths:

1. **Native/source install** — clone `main` and use the repository installer.
   This is the working path today.
2. **Flatpak** — build it locally from `packaging/flatpak` (see
   [Building the Flatpak from source](#building-the-flatpak-from-source)).

The current application version is **0.9.0**.

> [!IMPORTANT]
> No prebuilt bundle is published yet: the Flatpak and AppImage CI builds on
> `main` are failing and the GitHub Releases page is empty. The bundle
> instructions below apply once a release is published.

---

## Flatpak 0.9.0 bundle

A GitHub release is expected to provide:

- `Turing-Smart-Screen-0.9.0-x86_64.flatpak`;
- `70-turing-smart-screen.rules`;
- `SHA256SUMS`.

Download them from:

<https://github.com/maylton/turing-smart-screen-video-overlay/releases>

### 1. Install the host udev rule

Flatpak can expose serial and raw USB devices to the sandbox, but it cannot
install host udev rules. Install the supplied rule before testing hardware:

```bash
sudo install -Dm0644 \
  70-turing-smart-screen.rules \
  /etc/udev/rules.d/70-turing-smart-screen.rules

sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect the display afterwards.

The rule covers the serial/raw USB identities used by currently supported and
validated Turing/TURZX workflows. It grants access through `uaccess` rather than
requiring a project-specific privileged daemon.

### 2. Make Flathub available

The bundle uses `org.gnome.Platform//50` as its runtime. Add Flathub if it is not
already configured for your user:

```bash
flatpak remote-add --user --if-not-exists \
  flathub \
  https://flathub.org/repo/flathub.flatpakrepo
```

### 3. Install the bundle

```bash
flatpak install --user ./Turing-Smart-Screen-0.9.0-x86_64.flatpak
```

### 4. Launch

```bash
flatpak run io.github.turing.SmartScreen
```

The application should also appear in the desktop launcher/menu.

### Flatpak application data

The application payload under `/app` is read-only. The launcher keeps a writable
runtime copy under the Flatpak private XDG data directory and preserves mutable
state across package updates.

Typical location:

```text
~/.var/app/io.github.turing.SmartScreen/data/turing-smart-screen/runtime
```

Preserved user data includes `config.yaml`, installed/custom themes, local video
assets and application backup directories.

### Updating the Flatpak

For a newer GitHub release, download the new `.flatpak` bundle and install it over
the existing app:

```bash
flatpak install --user ./Turing-Smart-Screen-<version>-x86_64.flatpak
```

The private runtime is refreshed when packaged application code changes while
preserving mutable user data.

### Removing the Flatpak

```bash
flatpak uninstall --user io.github.turing.SmartScreen
```

Flatpak may offer to keep or remove application data separately. Keep the data if
you plan to reinstall and want to preserve configuration/themes.

---

## Hardware access notes

Supported displays use more than one transport:

- `/dev/ttyUSB*` and `/dev/ttyACM*` serial endpoints;
- raw USB on newer TURZX/Rev. C workflows.

The Flatpak currently uses device access broad enough to cover both classes; host
permissions are still enforced by udev/ACLs.

The physically validated fork-specific profile is a **Turing Smart Screen Rev. C
2.1-inch (ROM 88)**. Other devices may work through inherited upstream support,
but native storage/video-writing operations are not guaranteed on unvalidated
hardware.

---

## AMD GPU telemetry in Flatpak

Version 0.9.0 bundles libdrm 2.4.134 and builds `pyamdgpuinfo` from source against
the app-local libdrm libraries. This is intentional: prebuilt manylinux wheels
for `pyamdgpuinfo` can include private libdrm copies that look for
`/usr/share/libdrm/amdgpu.ids` inside the sandbox.

The release build smoke-check verifies that the private `pyamdgpuinfo.libs`
directory is not present.

---

## Native/source installation

Use this path for development, debugging or distributions/environments where you
prefer a normal per-user installation.

Clone the canonical `main` branch:

```bash
git clone https://github.com/maylton/turing-smart-screen-video-overlay.git
cd turing-smart-screen-video-overlay
```

### Readiness checks

Preview the detected distribution family, package manager and system packages
without changing anything:

```bash
scripts/install-system-deps.sh --print
```

After installing, re-run the installed checkup at any time. It verifies the
GTK4/Libadwaita imports, the HTML renderer dependencies (WebKitGTK and the
PyGObject cairo integration) when the HTML renderer is enabled, required files
and AMD GPU monitoring support:

```bash
cd ~/.local/share/turing-smart-screen
venv/bin/python3 gtk-checkup.py .
```

### Per-user install

```bash
./install.sh
```

Installed locations:

- application: `~/.local/share/turing-smart-screen`;
- command: `~/.local/bin/turing-smart-screen`;
- desktop entry: `~/.local/share/applications/io.github.turing.SmartScreen.desktop`.

Launch with:

```bash
turing-smart-screen
```

### Native dependencies

The native GTK application expects system GTK/PyGObject packages plus normal
project/runtime tools such as Python, FFmpeg/FFprobe and desktop integration
utilities. The project virtual environment is created with
`--system-site-packages`, so PyGObject, pycairo and the GTK/WebKit introspection
data always come from the distribution.

`./install.sh` installs them through `scripts/install-system-deps.sh`, which
detects the distribution family from `/etc/os-release` (falling back to the
available package manager):

| Family | Examples | Package manager |
| --- | --- | --- |
| Arch | Arch Linux, CachyOS, Manjaro, EndeavourOS | `pacman` |
| Debian | Debian, Ubuntu, Linux Mint, Pop!_OS | `apt-get` |
| Fedora | Fedora, Nobara, RHEL/Rocky/AlmaLinux | `dnf` |

Preview what would be installed without changing the system:

```bash
scripts/install-system-deps.sh --print
```

The HTML renderer needs the PyGObject cairo integration (`gi._gi_cairo`):
WebKitGTK 4.1 returns frame snapshots as cairo surfaces. Some distributions ship
it separately (`python3-gi-cairo` on Debian/Ubuntu, `python-cairo` on Arch;
`python3-gobject` on Fedora). Without it the monitor starts but the display
stays dark, and the renderer reports
`Couldn't find foreign struct converter for 'cairo.Surface'`.

Media preparation encodes H.264 with `libx264`. Fedora's default
`ffmpeg-free` does not include that encoder; enable RPM Fusion and run
`sudo dnf swap ffmpeg-free ffmpeg --allowerasing`.

On other distributions the helper prints the required components so they can be
installed manually before running `./install.sh --no-deps`.

Flatpak remains the simpler end-user installation because it carries the
application runtime/dependencies in a controlled environment.

### Updating a native install

```bash
git switch main
git pull --ff-only
./install.sh --no-deps
```

Updates preserve by default:

- `config.yaml`;
- themes under `res/themes`;
- local media under `res/video` and `res/videos`;
- fonts referenced by installed themes;
- GTK/theme-editor backup directories.

Use `./install.sh --fresh` only when replacing user-managed data is intentional.

### Full font catalog

The default native installation includes the core font profile used by bundled
themes. To install the complete optional font catalog:

```bash
./install.sh --full-fonts
```

### Autostart

```bash
./install.sh --autostart
```

Application autostart and automatic monitor startup are separate settings. The
GTK settings page controls whether the monitor itself starts automatically.

### System-wide native install

```bash
./install.sh --system
```

This installs under `/opt/turing-smart-screen` with a launcher under
`/usr/local/bin`. Prefer Flatpak or the per-user native install unless a
system-wide deployment is specifically required.

---

## Building the Flatpak from source

For packaging/development work:

```bash
flatpak remote-add --user --if-not-exists \
  flathub \
  https://flathub.org/repo/flathub.flatpakrepo

flatpak install --user -y \
  flathub \
  org.gnome.Platform//50 \
  org.gnome.Sdk//50

rm -rf build-flatpak

flatpak-builder \
  build-flatpak \
  --user \
  --install-deps-from=flathub \
  --force-clean \
  --install \
  packaging/flatpak/io.github.turing.SmartScreen.yml
```

Run the local build with:

```bash
flatpak run io.github.turing.SmartScreen
```

To build a single-file bundle, see
[`../packaging/flatpak/README.md`](../packaging/flatpak/README.md).

---

## Validation

Before a release or packaging change:

```bash
./scripts/verify-release-readiness.sh
```

The GitHub Flatpak workflow additionally builds the Flatpak repository,
smoke-checks exported application files, confirms the AMD Python extension is not
using bundled manylinux libdrm copies, creates the single-file bundle and
publishes release assets from `main`.

---

## Troubleshooting

### Display exists but cannot be opened

First confirm that the release udev rule is installed and reload the rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect the device and retry.

For native installs, `scripts/configure-hardware-access.sh` re-applies the udev
rule and adds your user to the serial-device group used by the distribution.

### Monitor starts but the display stays dark (HTML themes)

The HTML renderer runs in a worker process. If it cannot capture frames, the
monitor stays alive and keeps restarting it, but nothing reaches the display.
Check `~/.local/share/turing-smart-screen/log.log` and, for desktop launches,
`journalctl --user -b | grep SmartScreen`.

`Couldn't find foreign struct converter for 'cairo.Surface'` (or a startup error
mentioning `gi._gi_cairo`) means the PyGObject cairo integration is missing.
Install it with `scripts/install-system-deps.sh` (`python3-gi-cairo` on
Debian/Ubuntu, `python-cairo` on Arch, `python3-gobject` on Fedora). The monitor
picks it up on the next worker restart; no reinstall is needed.

### Display reported as busy

Only one process should own the physical display at a time. The GTK application
reports runtime owner/PID information. Stop the existing monitor normally before
starting another instance.

For Flatpak, to terminate all processes belonging to the application sandbox:

```bash
flatpak kill io.github.turing.SmartScreen
```

### Flatpak AMD GPU warning about `amdgpu.ids`

The stable 0.9.0 build should not repeatedly print
`/usr/share/libdrm/amdgpu.ids: No such file or directory`. If it does, confirm
you are running the current release and report the output of:

```bash
flatpak run --command=sh io.github.turing.SmartScreen -c '
find /app/lib/python3.13/site-packages -maxdepth 1 -name "pyamdgpuinfo.libs" -print
'
```

The stable source-built package should not contain that directory.

### `ModuleNotFoundError: No module named gi` in native installs

The native virtual environment uses system site packages so PyGObject can reuse
distribution-provided GTK bindings. Install the system bindings and re-run the
installer:

```bash
scripts/install-system-deps.sh
./install.sh --no-deps
```

### Keep an existing native installation untouched during testing

Use the isolated packaging test or a separate Git worktree instead of pointing
test commands at your real `~/.local/share/turing-smart-screen` installation.

### Isolated packaging test

`scripts/test-install.py` runs the native installer twice (install and upgrade)
inside an empty directory used as `HOME`, with `--no-deps --no-hardware-access`,
and checks that configuration, custom themes and media survive the upgrade:

```bash
python3 scripts/test-install.py --root /tmp/turing-install-test
```

Pass `--reset` to reuse a previous test directory.
