# Main App Roadmap

This roadmap tracks the Linux GTK application after the dashboard/theme-gallery polish and the stabilized theme video sync flow.

## Current baseline

The app now has a polished Overview, a cleaner Theme Gallery, single-video storage behavior for the display SD card, and safer theme video sync/restart handling.

## Milestone 1 — Diagnostics and supportability

Goal: make display/USB/runtime issues understandable without needing to run the app from a terminal.

- [x] Add a safe diagnostics collector that does not open the display serial port.
- [ ] Add a GTK Diagnostics page with:
  - detected serial ports;
  - UsbMonitor vs real display candidates;
  - active theme/config status;
  - monitor process status;
  - configured video status;
  - copy/export diagnostics.
- [ ] Add a one-click “Copy diagnostics” action for bug reports.
- [ ] Add recent error/log surfacing inside the app.

## Milestone 2 — Display lifecycle model

Goal: formalize the states we debugged manually.

- [ ] Show display state in the UI: disconnected, UsbMonitor/waking, real ttyACM ready, busy, running.
- [ ] Add clearer user-facing messages during Apply + Start.
- [ ] Keep bounded Rev. C hello/retry behavior covered by regression tests.
- [ ] Document the single-video display storage behavior.

## Milestone 3 — Video Manager polish

Goal: make the Video Manager match the new single-video behavior.

- [ ] Show “current display video” as the primary concept.
- [ ] Add safe replace/delete/self-test actions.
- [ ] Show SD/internal storage location and file size.
- [ ] Make stale-video cleanup visible in the UI.

## Milestone 4 — First-run setup wizard

Goal: make first installation feel like the original app, but clearer.

- [ ] Welcome screen.
- [ ] Detect display.
- [ ] Confirm model/resolution.
- [ ] Pick a compatible theme.
- [ ] Sync theme video.
- [ ] Start monitor.

## Milestone 5 — Better Linux sensors

Goal: improve CPU/GPU sensor coverage, especially on AMD systems.

- [ ] Add better AMD GPU discovery.
- [ ] Support `sensors`, `/sys/class/drm`, `amdgpu_top`, and `rocm-smi` when available.
- [ ] Show sensor diagnostics and fallback reason in the app.
- [ ] Make “No supported GPU found” actionable.

## Milestone 6 — Theme health and repair

Goal: catch broken themes before they fail at runtime.

- [ ] Validate YAML.
- [ ] Check preview availability.
- [ ] Check video block and local file availability.
- [ ] Check image bounds and display size compatibility.
- [ ] Add repair helpers: regenerate preview, normalize video path, convert/import assets.

## Milestone 7 — Import/export and backups

Goal: make theme management easier and safer.

- [ ] Import `.turzx`, `.zip`, and theme folders through the UI.
- [ ] Preview before importing.
- [ ] Normalize media paths and generated previews.
- [ ] Export current theme as a portable package.
- [ ] Backup/restore all themes.

## Milestone 8 — Visual Theme Editor

Goal: make theme editing less YAML-driven.

- [ ] Layer list.
- [ ] Preview canvas.
- [ ] Widget properties.
- [ ] Drag/reposition workflow.
- [ ] Live preview integration.
- [ ] Validate before save.
