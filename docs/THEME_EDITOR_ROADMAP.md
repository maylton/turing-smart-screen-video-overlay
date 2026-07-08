# Theme Editor roadmap

This note tracks the first isolated polish pass for the GTK Theme Editor. The
scope is intentionally limited to the theme editor surface and editor-specific
documentation so that concurrent work on diagnostics, the main app, runtime,
installer, dashboard, video sync, and monitor flows can continue on separate
branches without conflicts.

## Current state

- The GTK Theme Editor opens a selected theme from `res/themes/<theme>/` and
  supports either `theme.yaml` or `theme.yml`.
- Theme data is loaded with `ruamel.yaml` so existing YAML structure, comments,
  and quoted scalars are preserved as much as possible.
- The editor keeps a file signature for the loaded YAML and refuses to save when
  the file changed externally after the editor opened it.
- The main layout is a three-pane workspace: element tree, preview panel, and
  property editor.
- The header already exposes Undo, Redo, Save, Tools, overflow actions, and a
  preview refresh action.
- The preview is rendered by the existing preview helper and can be refreshed
  without closing the editor.
- Editable YAML fields are currently driven by the known `EDITABLE_KEYS` list,
  including display geometry, text/font fields, colors, bars, axes, booleans,
  layout-ish flags, paths, and media/video-related fields.

## Current graph styles

The current theme schema already supports three primary graph families under
sensor sections:

1. **`GRAPH` / horizontal bar meter**
   - Uses `X`, `Y`, `WIDTH`, `HEIGHT`, `MIN_VALUE`, `MAX_VALUE`, `BAR_COLOR`,
     optional `BAR_OUTLINE`, optional background, and `REVERSE_DIRECTION`.
   - Best suited for compact CPU/GPU/RAM usage bars.

2. **`RADIAL` / circular or arc gauge**
   - Uses `X`, `Y`, `RADIUS`, `WIDTH`, value range, angle controls, step and
     separator controls, direction, bar color, and optional inline text/unit.
   - Best suited for hero metrics or dashboard-style gauges.

3. **`LINE_GRAPH` / history sparkline**
   - Uses position/size, value range, `HISTORY_SIZE`, `AUTOSCALE`, `LINE_COLOR`,
     `LINE_WIDTH`, optional axis, axis color, axis font, and background.
   - Best suited for recent trend/history displays.

The Theme Editor can currently expose many of these raw properties, but it does
not yet present graph-specific presets, style groups, or visual controls for
bars, radial gauges, and line graphs.

## Implementation 1: editor polish and safer saves

This pass keeps the existing editor architecture and behavior. It does not
rewrite the editor, move shared app code, or change the monitor/runtime/video
flows.

Changes included in this step:

- Added a hidden `.theme-editor-backups/` directory inside the theme folder.
- Added timestamped YAML backups before replacing `theme.yaml` or `theme.yml`.
- Kept save operations atomic: the editor writes a temporary YAML file, validates
  that the exact output is parseable, creates the backup, and only then replaces
  the original file.
- If dumping, YAML validation, backup creation, or replacement fails, the
  original theme YAML is left intact.
- Added a friendlier YAML validation error dialog for invalid save output.
- Added a toast with the backup path when a backup is created.
- Routed the Text Effects save flow through the same safer save helper so it
  receives the external-change check, backup behavior, YAML validation, and file
  signature update.
- Lightly clarified window subtitle and primary action tooltips.
- Added basic tooltips for popover action rows so the main actions are easier to
  discover.

## Files intentionally not touched

This pass must not edit the following areas:

- main GTK app entrypoints such as `configure-gtk.py` and `configure_gtk_app.py`;
- diagnostics files;
- runtime, monitor, video sync, and video manager files;
- installer files;
- dashboard/main-app modules.

## Suggested next steps

1. **Layer list**
   - Add a dedicated layer list that separates structural groups from renderable
     screen objects.
   - Show visibility, state, and order at a glance.

2. **Visual property editor**
   - Replace generic text fields for common properties with safer controls such
     as spin buttons, color pickers, file selectors, switches, and presets.

3. **Graph visual polish**
   - Add graph-aware property groups in the editor: bar meter, radial gauge, and
     line graph.
   - Add presets such as thin pill bar, segmented bar, hero radial ring, compact
     radial arc, mini sparkline, and axis-free trend line.
   - Add safe color/threshold helpers for normal/warning/critical states without
     changing renderer behavior in the first step.
   - Later, evaluate renderer-level improvements in a separate branch: rounded
     bar caps, smoother antialiasing, gradient fills, threshold bands, cleaner
     tick marks, softer grid/axis rendering, and optional glow/shadow effects.

4. **Drag/reposition**
   - Allow selected renderable elements to be moved on the preview canvas.
   - Keep keyboard nudging and undo/redo support.

5. **Advanced validation**
   - Validate required keys, numeric ranges, color formats, paths, asset
     existence, and display bounds before saving.

6. **Repair helpers**
   - Offer explicit repair actions for common theme issues such as missing
     preview backgrounds, invalid asset paths, malformed color arrays, or
     unsupported dimensions.

7. **Live preview**
   - Add an opt-in live preview mode once save safety and validation are mature.
   - Keep manual refresh as the safe default until rendering performance and
     partial-update behavior are predictable.
