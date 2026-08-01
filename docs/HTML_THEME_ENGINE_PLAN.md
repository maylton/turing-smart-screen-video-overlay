# HTML Theme Engine — staged implementation

Branch: `feature/html-theme-engine`

This branch introduces a second theme engine without replacing or mutating the
existing YAML runtime. Hardware writes stay outside the experimental path until
the simulator, security boundary, and frame pipeline have separate tests.

## Safety rules

1. Existing YAML themes remain the default and must render exactly as before.
2. HTML themes initially run only in a developer simulator.
3. The HTML engine receives JSON snapshots, never Python objects or shell access.
4. Network requests are denied by default.
5. Theme paths are confined to the selected theme directory.
6. No display upload or serial operation is introduced before a later milestone.
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

## Later work, intentionally not in this milestone

- a simulated display sink that consumes RGB565 region payloads;
- full-frame and dirty-region conversion for tested hardware profiles;
- watchdog and frame-rate budgets;
- gallery/editor integration;
- import/export permission review;
- compiled HTML-to-video mode.
