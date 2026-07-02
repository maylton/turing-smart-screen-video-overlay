# Installation, update, and validation

This fork is currently packaged as a native Linux desktop application.
The installer supports a per-user installation, which is the recommended
mode, and an optional system-wide installation.

## Supported installation target

The automated dependency installation is currently designed for
Arch Linux and CachyOS. Other distributions can still use the installer
after providing these dependencies manually:

- Python 3 with `venv`;
- PyGObject;
- GTK4;
- Libadwaita;
- FFmpeg and FFprobe;
- rsync;
- Git;
- Tk;
- Pillow;
- desktop-file-utils.

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

## Autostart

```bash
./install.sh --autostart
```

This creates:

```text
~/.config/autostart/io.github.turing.SmartScreen.desktop
```

Application autostart and automatic monitor startup are separate choices.
The GTK settings page controls whether the monitor itself starts
automatically.

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

## System-wide installation

```bash
./install.sh --system
```

This installs the application under `/opt/turing-smart-screen` and the
launcher under `/usr/local/bin`.

## Validation

The installer creates its virtual environment with access to system site
packages so PyGObject can use the distribution-provided GTK bindings. It
then validates:

- GTK4 and Libadwaita through the system Python;
- GTK4, Pillow, and ruamel.yaml through the project virtual environment;
- syntax of all desktop, monitor, power, and video entry points;
- runtime ownership, media safety, and packaging unit tests;
- required files, commands, themes, and stale temporary files through
  `gtk-checkup.py`.

Run the checkup manually with:

```bash
/usr/bin/python3 \
  ~/.local/share/turing-smart-screen/gtk-checkup.py \
  ~/.local/share/turing-smart-screen
```

## Isolated packaging test

The repository includes a two-pass installation test that never touches
the real installation:

```bash
/usr/bin/python3 scripts/test-install.py \
  --root ../turing-smart-screen-packaging-home \
  --reset
```

The test installs under a temporary `HOME`, modifies the installed
configuration and adds custom theme/media fixtures, runs the installer a
second time, and confirms that the user's data survives the update.

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

Do not set an isolated `XDG_RUNTIME_DIR` during hardware tests. Device
ownership must remain shared between all application copies.

## Troubleshooting

### `ModuleNotFoundError: No module named 'gi'`

Re-run the updated installer. The project virtual environment must be
created with `--system-site-packages`, while PyGObject, GTK4, and
Libadwaita should come from the distribution packages.

### Display reported as busy

Another monitor, power helper, or video manager owns the display. The GTK
interface and JSON CLI responses report the owner role and PID. Stop that
process normally before retrying.

### Existing installation must remain untouched

Use the isolated packaging test or a separate Git worktree. Never point
test commands at `~/.local/share/turing-smart-screen`.
