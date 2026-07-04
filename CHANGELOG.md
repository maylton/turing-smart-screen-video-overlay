# Changelog

All notable changes to this Linux-focused fork are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to use semantic versioning for fork releases.

## [Unreleased]

### Added

- Public-facing README refresh that presents this repository as an experimental
  Linux-focused GTK fork.
- AI-assisted / vibe-coded development notice and user responsibility warning.
- Hardware validation scope for fork-specific native media workflows.
- Upstream sharing note explaining how to present the fork without asking the
  upstream maintainer to merge the whole project as-is.
- Native Rev. C video overlay and storage management, including upload,
  playback, stop, listing, size inspection, and deletion commands.
- Structured command-line and GTK tools for native media management.
- Exclusive process-wide display ownership through a runtime lock.
- Media Preparation Editor for GIF and video conversion.
- Advanced framing controls, including crop, rotation, alignment, timing,
  playback speed, looping, solid/blurred/image backgrounds, and preview.
- Reusable display profiles derived from the active theme.
- Portrait, landscape, square, and ultrawide conversion-only presets.
- Advisory output-size estimates before media conversion.
- Safe automatic display detection using serial descriptors and USB IDs.
- Automatic revision/theme selection only when detection is unambiguous.
- Linux packaging, desktop integration, installer, update, autostart, and
  readiness-check documentation.
- Theme Gallery / Theme Manager app shell integration.
- Theme import/export with export completeness preflight for referenced and
  generated media.
- Installer `--check-only` diagnostics for distro/package manager, runtime
  dependencies, PATH, venv health, and serial/USB permissions.

### Changed

- README now emphasizes Linux-first scope, experimental status, hardware limits,
  upstream credit, and user responsibility.
- Installation documentation now describes the non-destructive readiness check
  and distro-specific serial-device group differences.
- Current roadmap status now reflects completed export preflight, installer
  readiness diagnostics, and public-facing fork documentation.
- Media preparation now uses profile-selected dimensions instead of assuming a
  fixed 480 × 480 target.
- Startup detection runs before the display driver is imported.
- Installation preserves user configuration, custom themes, and local media by
  default.
- Shutdown synchronously stops native video before closing the display.

### Fixed

- Rev. C sub-revision initialization and ROM defaults.
- Rev. C orientation handling and duplicated bitmap-size payload behavior.
- Safe cleanup and display ownership during shutdown and competing processes.

### Safety

- Native media upload remains enabled only for the hardware-validated Turing
  Rev. C 2.1-inch profile using ROM 88.
- Unverified display profiles remain limited to conversion and local preview.
- Ambiguous display detections never alter configuration automatically.
- The public README explicitly warns that the fork was developed through an
  AI-assisted / vibe-coded process and should be reviewed before reuse.
