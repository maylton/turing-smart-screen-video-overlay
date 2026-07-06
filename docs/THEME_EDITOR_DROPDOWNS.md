# Theme Editor dropdown controls

This document tracks the staged cleanup of property editing controls in the GTK
Theme Editor.

## Goal

Reduce free-text editing for fields that have a known set of valid values,
especially in component nodes. Free-text remains available for dimensions,
positions, numeric tuning, asset paths, and values that are intentionally
customizable.

## Stage 1: closed-choice dropdowns

The first stage converts closed-choice properties to direct dropdown rows:

- `DISPLAY_SIZE`;
- `DISPLAY_ORIENTATION`;
- `ALIGN`;
- `ANCHOR`;
- `FORMAT`;
- `BAR_DECORATION`;
- `ORIENTATION`.

These fields were already backed by known presets or by the new graph bar
orientation list. They now render as direct dropdown controls instead of a text
field plus a preset dropdown.

## Why these fields

These properties are effectively enums:

- `DISPLAY_SIZE` should match one of the supported display sizes.
- `DISPLAY_ORIENTATION` should be `portrait` or `landscape`.
- `ALIGN` should be `left`, `center`, or `right`.
- `ANCHOR` should be one of the Pillow text anchor codes used by the theme
  engine.
- `FORMAT` should be one of the known date/time format styles.
- `BAR_DECORATION` is currently empty/none or `Ellipse`.
- `ORIENTATION` is `auto`, `horizontal`, or `vertical` for `GRAPH` bars.

## Compatibility

When a theme contains a value that is not present in the preset list, the editor
keeps it visible as a `Current — ...` option. This avoids silently changing older
or hand-edited themes.

For `ORIENTATION`, the save path still validates the selected value and blocks
unsupported values.

## Not changed in this stage

The following remain text fields with preset helpers because custom values are
useful:

- `X`, `Y`;
- `WIDTH`, `HEIGHT`;
- `FONT_SIZE`, `AXIS_FONT_SIZE`;
- `LINE_WIDTH`;
- `MIN_VALUE`, `MAX_VALUE`;
- `HISTORY_SIZE`;
- `ANGLE_START`, `ANGLE_END`, `ANGLE_STEPS`, `ANGLE_SEP`;
- `INTERVAL`, `REFRESH_INTERVAL`.

## Stage 2: searchable asset dropdowns

The second stage converts theme asset fields to searchable dropdown rows:

- `PATH`;
- `BACKGROUND_IMAGE`;
- `PREVIEW_BACKGROUND`;
- `FONT`;
- `AXIS_FONT`.

Image fields search files inside the selected theme directory. Font fields search
the shared `res/fonts` directory.

The editor still preserves hand-written values: when the current value is not
part of the discovered asset list, it is shown as a `Current — ...` option.
This keeps older themes safe while making normal asset selection much cleaner.

`PATH` now uses the same image discovery helper as `BACKGROUND_IMAGE` and
`PREVIEW_BACKGROUND`, so static image components no longer require typing image
file names manually when the asset already exists in the theme folder.

Search is enabled on these dropdowns because theme folders and font folders can
contain many files.

## Next stage

Stage 3 should add component presets and component creation helpers for common
theme component types.

## Stage 3: component starter presets

The third stage adds component-level starter presets to the property panel.
When a supported component is selected, the editor shows a compact preset row
above the raw fields.

Supported component kinds:

- text components;
- static image components;
- `GRAPH` bar components;
- `RADIAL` gauge components;
- `LINE_GRAPH` trend components.

These presets intentionally update layout/style fields only. They do not rename
the component, delete assets, or replace the selected image path. For text
components, they avoid overwriting the current `TEXT` value.

The first preset groups are:

- text:
  - centered label;
  - top-left caption;
  - large metric value;
- static image:
  - full-screen background;
  - centered card;
  - small icon;
- graph:
  - horizontal bar with track;
  - vertical bar with track;
  - compact thin bar;
- radial:
  - hero ring;
  - arc gauge;
  - compact ring;
- line graph:
  - minimal sparkline;
  - axis trend graph;
  - thin compact trend.
