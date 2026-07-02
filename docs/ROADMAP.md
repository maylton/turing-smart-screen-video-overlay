# Roadmap

## Checkpoint 1 — Runtime and native-video foundation

Status: **completed and hardware validated**

- exclusive process-wide ownership of the USB/serial display;
- real owner role/PID reporting;
- duplicate monitor prevention;
- asynchronous GTK stop and power actions;
- complete process reaping and serial-port release;
- explicit native-video stop during shutdown;
- structured JSON video-manager protocol;
- safe remote-path normalization;
- mandatory compatibility probing for GTK uploads;
- SD/internal list, size, upload, play, stop, and delete;
- automated runtime and media-safety tests.

## Checkpoint 2 — Installation and documentation readiness

Status: **implemented by the packaging/documentation checkpoint**

- GTK-aware project virtual environment using system site packages;
- installation-time dependency, syntax, and application checkup;
- isolated two-pass update test;
- explicit verification that configuration, custom themes, and media are
  preserved;
- fork-specific installation, update, validation, and troubleshooting
  documentation;
- corrected README support scope for native Rev. C video/storage features.

## Current implementation — Media preparation editor MVP

Status: **implemented for isolated and hardware validation**

Tracking issue:
[#7 — Media preparation editor for GIF and arbitrary video inputs](https://github.com/maylton/turing-smart-screen-video-overlay/issues/7)

The MVP branch provides a GTK workflow that:

- imports GIF, MP4, MKV, WebM, MOV, and AVI;
- displays source metadata from FFprobe;
- offers Fit, Fill/Cover, and Stretch modes;
- supports drag positioning, zoom, and centering;
- trims start and end;
- offers 24 and 30 FPS presets;
- converts to H.264 MP4, 480×480, and `yuv420p`;
- removes audio by default;
- previews the converted output;
- uploads the result through the hardened video-manager backend;
- stores temporary output in the user cache directory;
- performs conversion and upload outside the GTK main thread.

## Later phases

### Advanced framing

- original-size and fully custom modes;
- numeric X/Y/width/height controls;
- crop handles, rotation, and alignment shortcuts;
- solid, blurred, or custom-image backgrounds;
- GIF loop and playback-speed controls.

### Multiple display profiles

- target dimensions selected from the active display/theme;
- reusable conversion profiles;
- firmware-specific codec constraints;
- storage estimation before upload.

### Release readiness

- screenshots and fork-specific release notes;
- versioned changelog;
- repeatable release packaging;
- broader hardware/profile validation.
