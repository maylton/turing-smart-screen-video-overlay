# Installation, update, and validation

Turing Smart Screen for Linux supports two installation paths:

1. **Flatpak (recommended for normal users)** — install the stable bundle from
   GitHub Releases.
2. **Native/source install (recommended for development)** — clone `main` and
   use the repository installer.

The current stable application version is **0.9.0**.

---

## Recommended: Flatpak 0.9.0

The GitHub release provides:

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

### Readiness check

```bash
./install.sh --check-only
```

This mode is non-destructive. It reports:

- source directory and target install paths;
- detected Linux distribution and package manager;
- dependency hints for common distro families;
- required project files;
- Python/venv readiness;
- GTK4/Libadwaita imports;
- Pillow, PyYAML and ruamel.yaml availability;
- installed virtual-environment health;
- whether the launcher directory is in `PATH`;
- connected serial/USB devices;
- real device owner/group/mode and current-user access.

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
utilities. The exact package names vary by distribution; use
`./install.sh --check-only` for distro-specific hints.

The installer can automate dependencies on supported package-manager paths, but
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

For native installs, `./install.sh --check-only` reports serial-device group and
permission readiness.

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
distribution-provided GTK bindings. Re-run the current installer and verify GTK
readiness with:

```bash
./install.sh --check-only
```

### Keep an existing native installation untouched during testing

Use the isolated packaging test or a separate Git worktree instead of pointing
test commands at your real `~/.local/share/turing-smart-screen` installation.
