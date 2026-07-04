# Installation, update, and validation

This fork is packaged as a **native Linux desktop application**. The recommended
installation mode is per-user, under `~/.local/share/turing-smart-screen`, with a
launcher in `~/.local/bin/turing-smart-screen`.

> [!WARNING]
> This is an experimental, AI-assisted / vibe-coded fork. The installer has
> safety checks and preserves user data by default, but users should review the
> commands and run the readiness check before installing.

## Supported installation target

The fork is Linux-focused. The GTK4/Libadwaita app shell and installer are tested
primarily on Arch/CachyOS-style systems, while diagnostics and dependency hints
also cover other common Linux families.

Automated dependency installation currently uses `pacman` when available. Other
distributions can still use the app after installing the required packages with
their own package manager.

Required system-level pieces include:

- Python 3 with `venv` support;
- pip;
- PyGObject;
- GTK4;
- Libadwaita;
- FFmpeg and FFprobe;
- rsync;
- Git;
- Tk;
- Pillow or system image libraries required by Pillow;
- desktop-file-utils.

Run the readiness check to see a distro-specific dependency hint.

## Readiness check before installing

```bash
./install.sh --check-only
```

This mode is non-destructive. It does not install, remove, or modify files.

It reports:

- source directory and target install paths;
- detected OS and package manager;
- dependency hints for `pacman`, `apt`, `dnf`, `zypper`, or unknown systems;
- required project files;
- command availability for tools such as Python, rsync, Git, FFmpeg, and desktop
  integration utilities;
- Python `venv` support;
- GTK4/Libadwaita imports through the system Python;
- Pillow and PyYAML availability;
- installed virtual-environment health, when an installation already exists;
- whether the launcher directory is in `PATH`;
- connected serial/USB devices under `/dev/ttyACM*`, `/dev/ttyUSB*`, and
  `/dev/serial/by-id/*`;
- the real owner, group, and mode of detected devices;
- whether the current user belongs to the required access group.

Different distributions use different serial-device groups. The check does not
assume that all systems use the same group. It suggests likely groups by distro
family and then reports the actual group exposed by the connected device.

Common examples:

| Distro family | Common serial groups |
| --- | --- |
| Arch / CachyOS / Manjaro | `uucp`, sometimes `lock` |
| Debian / Ubuntu / Linux Mint / Pop!_OS | `dialout`, sometimes `plugdev` |
| Fedora / RHEL-like | `dialout`, sometimes `lock` |
| openSUSE / SUSE | `dialout`, `uucp`, sometimes `lock` |

When a group change is required, the command usually looks like:

```bash
sudo usermod -aG <group> "$USER"
```

Log out and log in again after changing groups. Existing sessions do not always
pick up new group membership.

## Per-user installation

```bash
./install.sh
```

Installed locations:

- application: `~/.local/share/turing-smart-screen`;
- command: `~/.local/bin/turing-smart-screen`;
- desktop entry:
  `~/.local/share/applications/io.github.turing.SmartScreen.desktop`.

Add `~/.local/bin` to `PATH` when your shell does not already include it.

Launch the app with:

```bash
turing-smart-screen
```

## Updating safely

```bash
git pull --ff-only
./install.sh --no-deps
```

By default, updates preserve:

- `config.yaml`;
- all theme folders under `res/themes`;
- local media under `res/video` and `res/videos`.

Use `./install.sh --fresh` only when replacing those user-managed files is
intentional.

## Autostart

```bash
./install.sh --autostart
```

This creates:

```text
~/.config/autostart/io.github.turing.SmartScreen.desktop
```

Application autostart and automatic monitor startup are separate choices. The
GTK settings page controls whether the monitor itself starts automatically.

## System-wide installation

```bash
./install.sh --system
```

This installs the application under `/opt/turing-smart-screen` and the launcher
under `/usr/local/bin`.

System-wide installation requires `sudo` and is less convenient for iterative
fork testing. Prefer per-user installation unless there is a specific reason to
install into `/opt`.

## Validation during install

The installer creates its virtual environment with access to system site packages
so PyGObject can use the distribution-provided GTK bindings. It then validates:

- GTK4 and Libadwaita through the system Python;
- GTK4, Pillow, PyYAML, and ruamel.yaml through the project virtual environment;
- syntax of desktop, monitor, editor, gallery, media, video, and runtime entry
  points;
- runtime ownership, media safety, packaging, and media-preparation unit tests;
- required files, commands, themes, and stale temporary files through
  `gtk-checkup.py`.

Run the checkup manually with:

```bash
/usr/bin/python3 \
  ~/.local/share/turing-smart-screen/gtk-checkup.py \
  ~/.local/share/turing-smart-screen
```

## Isolated packaging test

The repository includes a two-pass installation test that never touches the real
installation:

```bash
/usr/bin/python3 scripts/test-install.py \
  --root ../turing-smart-screen-packaging-home \
  --reset
```

The test installs under a temporary `HOME`, modifies the installed configuration
and adds custom theme/media fixtures, runs the installer a second time, and
confirms that the user's data survives the update.

To launch that isolated installation manually:

```bash
TEST_HOME="$(realpath ../turing-smart-screen-packaging-home)"

env \
  HOME="$TEST_HOME" \
  XDG_CONFIG_HOME="$TEST_HOME/.config" \
  XDG_CACHE_HOME="$TEST_HOME/.cache" \
  XDG_DATA_HOME="$TEST_HOME/.local/share" \
  "$TEST_HOME/.local/bin/turing-smart-screen"
```

Do not set an isolated `XDG_RUNTIME_DIR` during hardware tests. Device ownership
must remain shared between all application copies.

## Troubleshooting

### `ModuleNotFoundError: No module named 'gi'`

Re-run the updated installer. The project virtual environment must be created
with `--system-site-packages`, while PyGObject, GTK4, and Libadwaita should come
from the distribution packages.

### Launcher command not found

Check whether the per-user launcher directory is in `PATH`:

```bash
./install.sh --check-only
```

If needed, add this to your shell profile:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Display device exists but the app cannot access it

Run:

```bash
./install.sh --check-only
```

Look at the **Hardware permission readiness** section. It reports the real group
for the connected device and whether your current user belongs to it.

After adding yourself to a device group, log out and log in again.

### Display reported as busy

Another monitor, power helper, or video manager owns the display. The GTK
interface and JSON CLI responses report the owner role and PID. Stop that
process normally before retrying.

### Existing installation must remain untouched

Use the isolated packaging test or a separate Git worktree. Never point test
commands at `~/.local/share/turing-smart-screen` unless you intentionally want to
validate the real installation.
