# Changelog

All notable changes to this Linux-focused fork are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and fork releases follow semantic versioning where practical.

## [Unreleased]

### Planned

- Broader hardware validation across additional Turing/TURZX/XuanFang/Kipye/WeAct profiles.
- Flathub submission work and further Flatpak permission tightening where possible.
- Additional packaging/offline-build cleanup.

## [0.9.0] - 2026-08-24

First stable GitHub-distributed Flatpak release of the Linux GTK application.

### Added

- GTK4/Libadwaita desktop application shell with Overview, settings and system tray integration.
- Theme Gallery / Theme Manager with visual previews, activation, import/export, duplicate/rename/delete and compatibility information.
- Embedded Theme Editor with guarded saves, external-change detection, semantic navigation, image layout controls, text/effect presets and generated-media tracking.
- HTML theme renderer and HTML/native-video overlay workflows.
- Media Preparation Editor for GIF/video conversion with FFprobe analysis, framing, crop/rotation/alignment, timing and preview controls.
- Native Rev. C media management workflows for validated hardware, including listing, upload, playback, stop, size inspection and guarded deletion.
- Safe automatic display detection based on serial descriptors and USB IDs.
- Runtime display ownership lock with PID/role reporting.
- GTK/runtime diagnostics and `install.sh --check-only` readiness reporting.
- Flatpak packaging for `io.github.turing.SmartScreen` using GNOME Platform 50.
- GitHub Actions Flatpak build, smoke checks, single-file bundle generation and release publishing.
- Host udev rules for serial and raw USB identities used by supported display workflows.
- Release assets for the Flatpak bundle, udev rules and SHA256 checksums.

### Changed

- `main` is now the canonical application branch; users no longer need to clone a separate feature branch.
- Flatpak is the recommended normal-user installation path; native/source installation remains available for development and advanced users.
- Monitor startup imports were reorganized so renderer selection happens before legacy display/scheduler construction, avoiding duplicate serial ownership for HTML themes.
- The GTK Overview Start Monitor action now uses the same runtime start path as the working system tray action.
- Runtime status follows the actual display lock/PID so the UI transitions reliably from Starting to Running.
- Flatpak-launched monitor processes remain in the application process group instead of becoming detached/orphaned sessions.
- Flatpak runtime payload refresh now tracks packaged Python changes while preserving mutable configuration, themes, videos and backups.
- StatusNotifier registration uses a targeted watcher permission rather than broad session-bus access.
- GPU selection on Linux prefers the AMD adapter with the largest dedicated VRAM, avoiding accidental iGPU selection on mixed Ryzen/Radeon systems.

### Fixed

- Rev. C HTML/native-video startup on a physical 2.1-inch display under Flatpak.
- Raw USB reset/recovery permission failures by adding the required host `uaccess` rules.
- Repeated Flatpak AMD GPU `/usr/share/libdrm/amdgpu.ids` warnings.
- AMD telemetry packaging by bundling libdrm 2.4.134 and compiling `pyamdgpuinfo` from source against the app-local libraries instead of using manylinux wheels with private libdrm copies.
- Rev. C sub-revision initialization and ROM defaults.
- Rev. C orientation handling and duplicated bitmap-size payload behavior.
- Safe cleanup and display ownership during shutdown and competing processes.

### Validation

Physically validated during the 0.9.0 release work on:

- KDE Linux;
- Turing Smart Screen Rev. C 2.1-inch, ROM 88;
- GTK Start Monitor and system tray Start Screen;
- HTML/Gengar theme rendering;
- native video overlay path;
- serial and raw USB access through Flatpak + host udev rules;
- AMD GPU telemetry with a discrete Radeon and integrated AMD GPU present.

### Safety

- Native media upload/storage-writing remains intended for hardware-validated profiles.
- Unverified display profiles should be treated as conversion/preview-first until physically validated.
- Ambiguous display detection does not silently rewrite configuration.
- The project remains an independent, AI-assisted fork and is not official vendor software.

[0.9.0]: https://github.com/maylton/turing-smart-screen-video-overlay/releases/tag/v0.9.0
