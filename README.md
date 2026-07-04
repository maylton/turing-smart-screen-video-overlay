# Turing Smart Screen Linux GTK Fork

<!-- MAYLTON_FORK_OVERVIEW -->

> [!IMPORTANT]
> This repository is an **experimental Linux-focused fork** of
> [`mathoudebine/turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python).
> It explores a GTK4/Libadwaita desktop application, safer theme editing,
> Theme Gallery workflows, media preparation, and native Rev. C video/storage
> support on Linux.
>
> This is **not** the official vendor software and it is **not** the upstream
> project. It is a personal/experimental fork shared for people who want to
> inspect, test, or discuss the direction.

> [!WARNING]
> This fork was developed through a heavily **AI-assisted / vibe-coded**
> workflow. The code has been tested throughout development, but it has not gone
> through a traditional maintainer-led review process. Use it at your own risk,
> especially when running device-write, media upload, delete, playback, or
> hardware-control features.

## What this fork is

This fork turns the original Python system monitor into a more complete
Linux desktop experience:

- a native GTK4/Libadwaita app shell;
- a Theme Gallery / Theme Manager;
- an embedded GTK Theme Editor;
- an embedded Video Manager;
- media preparation for GIF/video inputs;
- generated-media tracking;
- theme import/export with completeness preflight;
- safer Linux installer diagnostics;
- native video/storage workflow for tested Rev. C hardware.

The original project remains the upstream foundation. This fork keeps the
YAML-based theme model and Python runtime, but it focuses on a Linux-first UI
and workflow rather than preserving the same multi-OS experience as upstream.

## Current status

| Area | Status |
| --- | --- |
| Linux GTK app shell | Implemented and used as the main launcher |
| Theme Gallery / Theme Manager | Implemented |
| Embedded Theme Editor | Implemented |
| Embedded Video Manager | Implemented |
| Theme import/export | Implemented |
| Export preflight for referenced/generated media | Implemented |
| Media preparation workflow | Implemented |
| Native video/storage operations | Implemented for tested Rev. C workflow |
| Installer readiness diagnostics | Implemented with `./install.sh --check-only` |
| Broad multi-distro packaging | Partial; diagnostics exist, automated dependency install is strongest on Arch/CachyOS |
| Broad hardware validation | Limited; native media features are validated only on the hardware described below |

## Hardware validation scope

The inherited system-monitor functionality still comes from the upstream
project and may work with the same families of supported devices.

The **new media/video/storage features in this fork** are more limited:

| Feature area | Validation status |
| --- | --- |
| Turing Smart Screen Rev. C 2.1-inch, ROM 88 | Physically validated by the fork author |
| Native video playback/storage management | Validated on the Rev. C 2.1-inch profile above |
| Other Turing/TURZX revisions and sizes | Not guaranteed for fork-specific media operations |
| XuanFang / Kipye / WeAct / other devices | Inherited monitor support may work, but fork-specific media flows are not guaranteed |

> [!CAUTION]
> Device operations can interact with real hardware storage/playback state.
> Read the diagnostics, understand the selected device/profile, and keep backups
> of custom themes/media before testing.

## Quick start on Linux

```bash
git clone https://github.com/maylton/turing-smart-screen-video-overlay.git
cd turing-smart-screen-video-overlay

./install.sh --check-only
./install.sh
turing-smart-screen
```

Recommended update flow:

```bash
git pull --ff-only
./install.sh --no-deps
turing-smart-screen
```

Useful installer modes:

```bash
./install.sh --check-only   # diagnostics only; does not install or modify files
./install.sh                # per-user install under ~/.local/share/turing-smart-screen
./install.sh --no-deps      # update/reinstall without installing system packages
./install.sh --autostart    # create a desktop autostart entry
./install.sh --system       # optional system-wide install under /opt
./install.sh --fresh        # replace installed config/themes/media instead of preserving them
```

See [Installation, update, and validation](docs/INSTALLATION.md) for details.

## Installer readiness diagnostics

Before installing, run:

```bash
./install.sh --check-only
```

The check reports:

- detected Linux distribution and package manager;
- distro-specific dependency hints;
- Python/venv readiness;
- GTK4 and Libadwaita imports;
- Pillow, PyYAML, and ruamel.yaml availability;
- whether the installed virtual environment is healthy;
- whether `~/.local/bin` is in `PATH`;
- connected serial/USB devices such as `/dev/ttyACM*`, `/dev/ttyUSB*`, and
  `/dev/serial/by-id/*`;
- the real owner/group/mode of detected devices;
- whether the current user belongs to the required access group.

Different distributions use different device-access groups. The installer does
not assume a single group for everyone. For example, Arch/CachyOS often uses
`uucp`, while Debian/Ubuntu commonly uses `dialout`. The diagnostic reports the
real group exposed by the device on your system.

## Main features

### Linux GTK app shell

The primary launcher is:

```bash
turing-smart-screen
```

The app shell integrates the main configuration workflow, theme management,
video management, overview preview, and quick actions into a Linux desktop UI.

### Theme Gallery / Theme Manager

The Theme Gallery provides:

- visual theme cards;
- current/active theme markers;
- compatibility and diagnostics indicators;
- open/edit actions;
- duplicate, rename, and delete with confirmation;
- import from folder/archive;
- export to zip archive;
- export preflight warnings for incomplete themes.

### Embedded Theme Editor

The GTK Theme Editor remains YAML-first and keeps the safety principles that
made the fork useful:

- guarded saves;
- Undo/Redo-friendly operations;
- external file change detection;
- atomic writes;
- semantic element tree;
- layer ordering;
- image layout/transform/crop inspectors;
- text/effect presets;
- generated-media tracking.

### Media preparation

The media preparation workflow can analyze and prepare GIF/video files without
requiring manual FFmpeg commands. It supports profile-aware framing, trimming,
conversion, preview, and guarded upload flows.

See [Media preparation](docs/MEDIA_PREPARATION.md).

### Native video and storage workflow

For the validated Rev. C 2.1-inch workflow, the fork includes tools for:

- listing display-side media;
- checking size/storage information;
- uploading prepared media;
- playing and stopping video;
- deleting media with guarded flows;
- using native video as a background while transparent overlays render on top.

This area is the riskiest and most hardware-specific part of the fork. Treat it
as experimental unless you have the same tested hardware/profile.

### Theme export preflight

Before exporting a theme, the app can inspect `theme.yaml` and generated-media
metadata to report:

- included assets;
- missing assets;
- paths outside the theme folder;
- generated assets with manifest metadata;
- generated assets without manifest metadata;
- generated-media records that are no longer used.

The preflight is explicit and non-destructive: it does not repair, delete, or
mutate theme files during export.

## Documentation

| Document | Purpose |
| --- | --- |
| [Installation, update, and validation](docs/INSTALLATION.md) | Install/update commands, check-only diagnostics, validation, troubleshooting |
| [Current roadmap status](docs/ROADMAP_CURRENT_STATUS.md) | Current project checkpoint and next steps |
| [Full roadmap](docs/ROADMAP.md) | Longer development history and feature roadmap |
| [Official Windows parity roadmap](docs/OFFICIAL_WINDOWS_PARITY_ROADMAP.md) | Why the fork implemented gallery/media/device workflows |
| [Theme app architecture checkpoint](docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md) | Architecture notes for the integrated app shell |
| [Media preparation](docs/MEDIA_PREPARATION.md) | Media preparation workflow details |
| [Release candidate notes](docs/releases/0.1.0-rc1.md) | Earlier release-candidate scope and limitations |
| [Changelog](CHANGELOG.md) | Versioned change history |

## Relationship with upstream

This repository is meant to be transparent about what was built on top of the
original project. It is **not** a request to merge the whole fork as-is.

Some ideas may be useful upstream, but many parts are intentionally Linux-first
or fork-specific. If the upstream maintainer or community is interested, the
work can be discussed and split into smaller upstream-friendly PRs later.

Likely upstream-friendly areas:

- small bug fixes;
- pure helper functions;
- diagnostics improvements;
- packaging/test improvements;
- isolated hardware/media discoveries, if the maintainer wants them.

Likely fork-specific areas:

- GTK4/Libadwaita app shell;
- Linux-only installer workflow;
- Theme Gallery UX as implemented here;
- generated-media management tied to this editor;
- Rev. C video/storage flows until upstream agrees on scope.

See [Upstream sharing notes](docs/UPSTREAM_SHARING.md).

## AI-assisted / vibe-coded development notice

This fork was built through iterative, AI-assisted development. That means:

- many changes were designed, generated, tested, reviewed, and refined in small
  implementation loops;
- the code has many targeted tests and manual validation checkpoints;
- the project still needs independent review before it should be treated as
  production-grade software;
- users should read the code and test in their own environment before trusting
  device-write flows.

The vibe-coded process helped move quickly, but it does not remove the need for
careful human review.

## Safety and responsibility

By using this fork, you accept that:

- it may contain bugs;
- device/media operations may behave differently on untested hardware;
- your distribution may require additional permissions or packages;
- you are responsible for reviewing commands before running them;
- you should keep backups of custom themes, configuration, and media.

The installer preserves `config.yaml`, custom themes, and local media folders by
default during updates, but backups are still recommended before testing.

## Credits

This fork is based on
[`mathoudebine/turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python).
The original project provides the cross-platform Python system monitor foundation,
hardware abstraction, themes, and configuration model that made this work
possible.

## Disclaimer

This project is **not affiliated, associated, authorized, endorsed by, or in any
way officially connected with Turing / XuanFang / Kipye brands**, or any of their
subsidiaries, affiliates, manufacturers, or sellers. All product and company
names are trademarks or registered trademarks of their respective owners.

This project is an open-source alternative software experiment, not the original
software provided for the smart screens. Do not open issues here for the vendor
applications `USBMonitor.exe`, `ExtendScreen.exe`, or for hardware warranty
support.

For the original upstream project, see:

- <https://github.com/mathoudebine/turing-smart-screen-python>

For vendor/hardware support, use the vendor/reseller channels.

## License

This fork follows the license of the upstream project. See [LICENSE](LICENSE).
