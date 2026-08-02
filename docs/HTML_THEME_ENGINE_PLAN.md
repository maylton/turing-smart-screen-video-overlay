# HTML Theme Engine — staged implementation

Branch: `feature/html-theme-engine`

This branch introduces a second theme engine without replacing or mutating the
existing YAML runtime. Physical support remains opt-in and is gated by manifest,
media, protocol, and lifecycle validation.

## Safety rules

1. Existing YAML themes remain the default and must render exactly as before.
2. HTML themes run only when explicitly selected in `renderer.engine`.
3. The HTML engine receives JSON snapshots, never Python objects or shell access.
4. Network requests are denied by default.
5. Theme paths are confined to the selected theme directory.
6. Automated tests never open the display serial port.
7. Each milestone is one coherent commit and can be reverted independently.

## Milestones

### 1. Sensor snapshot

Create a renderer-neutral, versioned JSON payload. Collection failures are
isolated per section so one unsupported metric cannot stop the theme.

### 2. Theme engine interface

Add manifest validation, engine discovery, and lifecycle contracts while keeping
the YAML engine as the default route.

### 3. HTML simulator

Load a local HTML theme in WebKitGTK, inject synthetic snapshots, block external
navigation, and optionally export a preview snapshot. This milestone remains
fully disconnected from physical display transports.

### 4. Real sensors and simulated frame pipeline

Add an opt-in adapter for the existing sensor backend and an in-memory frame
pipeline that:

- captures `Gdk.Texture` snapshots as PNG bytes;
- normalizes frames to RGBA;
- ignores tiny per-channel changes;
- groups changed pixels into conservative tile regions;
- falls back to a full refresh when too much of the frame changes;
- writes simulator-only inspection artifacts.

This milestone still has no USB, serial, or physical display sink.

### 5. Integrated bitmap renderer

The monitor owns one renderer lifecycle and runs GTK/WebKit in a child process.
The bitmap path keeps its validated limits of eight regions and 300,000 bytes
per cycle and remains available as a diagnostic/fallback implementation.

### 6. Compiled native video with HTML overlays

An HTML theme may opt in with `nativeVideoOverlay`. Elements explicitly marked
with `data-turing-overlay` remain live; every other element and CSS animation is
compiled into a local H.264 480x480 video. Runtime WebKit renders only a
transparent text/bar canvas and submits it through the existing native Rev. C
video-overlay transaction. No network assets or implicit display upload are
allowed.

### 7. Gallery selection, build state, and visual overlay authoring

The main GTK theme gallery discovers both engines and writes the explicit
`renderer.engine`/`renderer.theme` selection while preserving the legacy YAML
theme. HTML cards show whether the generated MP4 is missing, stale, or ready by
comparing a source fingerprint with the compiled artifact.

The gallery can build/rebuild the MP4 in an isolated helper process and then
sync only a validated, current artifact. Selecting an HTML theme automatically
builds a missing/stale artifact before the existing safe video-sync lifecycle.
The HTML editor exposes native-video timing/storage fields and the explicit
`data-turing-overlay` element markers. Saves are atomic and keep one local
editor backup.

HTML import/use remains local-only: packages require a CSP meta tag,
`network=false`, and only the `sensors` permission. YAML import/export behavior
is unchanged.

## Testable prototype

The simulator theme is `res/themes/html-demo`. It cannot access the display,
serial ports, shell commands, or the network.

Validate the manifest and local WebKitGTK installation:

```bash
python html-theme-preview-gtk.py --check
```

Open the isolated simulator with synthetic data:

```bash
python html-theme-preview-gtk.py
```

Use the existing Python hardware sensor backend:

```bash
python html-theme-preview-gtk.py --real-sensors
```

Choose a specific network interface when needed:

```bash
python html-theme-preview-gtk.py \
  --real-sensors \
  --network-interface enp1s0
```

Inspect the complete frame and calculated dirty regions:

```bash
python html-theme-preview-gtk.py \
  --real-sensors \
  --inspect-frames /tmp/turing-html-frames
```

The inspection directory contains:

```text
latest.png
latest-diff.png
metrics.json
```

This path is intentionally diagnostic. Frames are captured in memory and only
the latest artifacts are written atomically.

Optionally request a one-time PNG after the page finishes loading:

```bash
python html-theme-preview-gtk.py \
  --snapshot /tmp/html-theme-preview.png
```

Build the Material Expressive native background without accessing hardware:

```bash
python html-theme-build-video.py \
  --theme res/themes/html-aio-material-expressive
```

Inspect only its transparent runtime layer and exit automatically:

```bash
python html-theme-preview-gtk.py \
  --theme res/themes/html-aio-material-expressive \
  --native-overlay \
  --snapshot /tmp/html-aio-overlay.png \
  --exit-after-snapshot
```

The generated MP4 must be synchronized explicitly to the exact `devicePath`
from `manifest.json` before starting the physical renderer. The monitor never
uploads or overwrites display media implicitly.

Run the pure-Python regression suite:

```bash
python -m unittest -v \
  tests.test_sensor_snapshot \
  tests.test_theme_engine \
  tests.test_html_theme_engine \
  tests.test_html_frame_capture \
  tests.test_real_sensor_source \
  tests.test_frame_pipeline
```

The preview requires the GTK4 and WebKitGTK 6.0 GI namespaces. The core modules
and their tests do not import GI, so machines without WebKitGTK can still run all
non-visual validation.

## Later work

- a simulated display sink that consumes RGB565 region payloads;
- full-frame and dirty-region conversion for tested hardware profiles;
- watchdog and frame-rate budgets;
- richer visual layout authoring beyond overlay-marker selection.
