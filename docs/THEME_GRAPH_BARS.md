# Theme graph bars

This document describes the first compatible extension for theme progress bars.
It keeps the existing `GRAPH` section and adds optional fields instead of
introducing a new graph type.

## Why this shape

Older themes already use `GRAPH` for compact horizontal progress bars. The
rendering engine also had an implicit vertical mode whenever `HEIGHT` was
greater than or equal to `WIDTH`, but that behavior was not explicit in the YAML
schema or the Theme Editor.

The safest approach is to keep `GRAPH` and add a small set of optional keys:

```yaml
GRAPH:
  SHOW: True
  X: 20
  Y: 40
  WIDTH: 12
  HEIGHT: 120
  MIN_VALUE: 0
  MAX_VALUE: 100
  BAR_COLOR: 255, 80, 80
  ORIENTATION: vertical
  DRAW_BAR_BACKGROUND: True
  BAR_BACKGROUND_COLOR: 45, 45, 45
  BAR_OUTLINE: True
  REVERSE_DIRECTION: False
```

## Fields

### `ORIENTATION`

Controls the fill direction for `GRAPH`.

- `auto`: preserves the legacy behavior.
  - `WIDTH > HEIGHT` renders as horizontal.
  - `HEIGHT >= WIDTH` renders as vertical.
- `horizontal`: forces left/right fill behavior, even when the rectangle is
  tall.
- `vertical`: forces bottom/top fill behavior, even when the rectangle is wide.

Default: `auto`.

### `DRAW_BAR_BACKGROUND`

Draws a full-size track behind the filled value before drawing the active bar.
This makes partial values easier to read.

Default: `False`.

### `BAR_BACKGROUND_COLOR`

Color for the empty track when `DRAW_BAR_BACKGROUND` is enabled.

Default: `0, 0, 0`.

### `BAR_OUTLINE`

Existing field. When true, draws a border around the full graph rectangle.

## Compatibility

Existing themes keep their current appearance because:

- `ORIENTATION` defaults to `auto`;
- `DRAW_BAR_BACKGROUND` defaults to `False`;
- `BAR_BACKGROUND_COLOR` is ignored unless `DRAW_BAR_BACKGROUND` is true;
- `BAR_OUTLINE` keeps its previous behavior.

## Theme Editor integration

When a `GRAPH` node is selected, the GTK Theme Editor can add the optional graph
bar controls that older themes do not have yet:

- `ORIENTATION: auto`;
- `DRAW_BAR_BACKGROUND: False`;
- `BAR_BACKGROUND_COLOR: 60, 60, 60`;
- `BAR_OUTLINE: False`.

The helper deliberately uses defaults that preserve the current rendering. After
the fields are added, the user can change them in the normal property editor.

`ORIENTATION` is edited through a dropdown with the supported values `auto`,
`horizontal`, and `vertical`, so invalid values are blocked before saving from
the editor.

## Relation to other graph types

`RADIAL` already has equivalent track support through:

- `DRAW_BAR_BACKGROUND`;
- `BAR_BACKGROUND_COLOR`;
- `BAR_DECORATION`.

`LINE_GRAPH` already has a graph area background through:

- `BACKGROUND_COLOR`;
- `BACKGROUND_IMAGE`;
- `AXIS`;
- `AXIS_COLOR`.

A future patch can add explicit line-graph frame controls if we want a true
border/outline independent from the axis.
