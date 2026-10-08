# Installation, update, and validation

Turing Smart Screen for Linux is installed natively from the `main` branch with
the repository installer. The current application version is **0.9.0**.

---

## Install

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

The application should also appear in the desktop launcher/menu.

### System dependencies

The GTK application expects system GTK/PyGObject packages plus normal
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

### Hardware access

Unless `--no-hardware-access` is given, the installer runs
`scripts/configure-hardware-access.sh`, which installs
`/etc/udev/rules.d/70-turing-smart-screen.rules` and adds your user to the
serial-device group used by the distribution (`uucp` on Arch, `dialout`
elsewhere). The rule grants access through `uaccess` rather than requiring a
project-specific privileged daemon.

Supported displays use more than one transport:

- `/dev/ttyUSB*` and `/dev/ttyACM*` serial endpoints;
- raw USB on newer TURZX/Rev. C workflows, also used to reset a wedged Rev. C
  display.

The physically validated fork-specific profile is a **Turing Smart Screen Rev. C
2.1-inch (ROM 88)**. Other devices may work through inherited upstream support,
but native storage/video-writing operations are not guaranteed on unvalidated
hardware.

### AMD GPU telemetry

The installed checkup detects AMD GPUs and installs
`requirements-gpu-amd.txt` (`pyamdgpuinfo`) into the project virtual
environment only when one is present.

---

## Updating

```bash
git switch main
git pull --ff-only
./install.sh --no-deps
```

Stop the monitor first: the installer recreates the virtual environment.

Updates preserve by default:

- `config.yaml`;
- themes under `res/themes`;
- local media under `res/video` and `res/videos`;
- fonts referenced by installed themes;
- GTK/theme-editor backup directories.

Use `./install.sh --fresh` only when replacing user-managed data is intentional.

### Full font catalog

The default installation includes the core font profile used by bundled themes.
To install the complete optional font catalog:

```bash
./install.sh --full-fonts
```

### Autostart

```bash
./install.sh --autostart
```

Application autostart and automatic monitor startup are separate settings. The
GTK settings page controls whether the monitor itself starts automatically.

### System-wide install

```bash
./install.sh --system
```

This installs under `/opt/turing-smart-screen` with a launcher under
`/usr/local/bin`. Prefer the per-user install unless a system-wide deployment is
specifically required.

### Uninstall

```bash
./uninstall.sh            # per-user install
./uninstall.sh --system   # system-wide install
```

This deletes the whole application directory, including `config.yaml`, custom
themes and local media. Back them up first if you want to keep them. The udev
rule and serial-group membership are left in place.

---

## Validation

Before publishing changes:

```bash
./scripts/verify-release-readiness.sh
```

### Isolated packaging test

`scripts/test-install.py` runs the installer twice (install and upgrade) inside
an empty directory used as `HOME`, with `--no-deps --no-hardware-access`, and
checks that configuration, custom themes and media survive the upgrade:

```bash
python3 scripts/test-install.py --root /tmp/turing-install-test
```

Pass `--reset` to reuse a previous test directory. Use it, or a separate Git
worktree, instead of pointing test commands at your real
`~/.local/share/turing-smart-screen` installation.

---

## Troubleshooting

### Display exists but cannot be opened

Re-apply the udev rule and serial-group access, then reconnect the device:

```bash
scripts/configure-hardware-access.sh
```

A newly added serial group only takes effect after logging out and back in.

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

### `ModuleNotFoundError: No module named gi`

The virtual environment uses system site packages so PyGObject can reuse
distribution-provided GTK bindings. Install the system bindings and re-run the
installer:

```bash
scripts/install-system-deps.sh
./install.sh --no-deps
```
