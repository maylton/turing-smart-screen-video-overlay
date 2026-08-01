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

## Testable prototype

The first simulator theme is `res/themes/html-demo`. It uses only synthetic data
and cannot access the display, serial ports, shell commands, or the network.

Validate the manifest and local WebKitGTK installation:

```bash
python html-theme-preview-gtk.py --check
```

Open the isolated simulator:

```bash
python html-theme-preview-gtk.py
```

Optionally request a PNG after the page finishes loading:

```bash
python html-theme-preview-gtk.py --snapshot /tmp/html-theme-preview.png
```

Run the pure-Python regression suite:

```bash
python -m unittest -v \
  tests.test_sensor_snapshot \
  tests.test_theme_engine \
  tests.test_html_theme_engine
```

The preview requires the GTK4 and WebKitGTK 6.0 GI namespaces. The core modules
and their tests do not import GI, so machines without WebKitGTK can still run all
non-visual validation.

## Later work, intentionally not in the first testable prototype

- real sensor adapter wired into the normal monitor loop;
- full-frame and dirty-region conversion for hardware;
- watchdog and frame-rate budgets;
- gallery/editor integration;
- import/export permission review;
- compiled HTML-to-video mode.
