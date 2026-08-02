# HTML overlay document

Current format: `turing-html-overlays` version `1`

Canonical filename: `overlays.json`

## Purpose

`overlays.json` is the canonical editor-managed representation of dynamic HTML
overlay layout and appearance. The editor derives these compatibility/runtime
artifacts from it when saving:

- `theme-editor-overrides.css`;
- generated sensor elements in the HTML entrypoint;
- the local widget runtime script;
- `atomicRegions` in `manifest.json`.

The HTML and generated files remain present for the current WebKit renderer.
Future native overlay rendering can consume the same declarative document
without changing the theme editor format.

## Manifest declaration

An HTML theme that uses the canonical document declares it explicitly:

```json
{
  "engine": "html",
  "entrypoint": "index.html",
  "overlayDocument": "overlays.json"
}
```

Only the root `overlays.json` filename is accepted in version 1. Its display
dimensions must match the HTML theme manifest.

## Document shape

```json
{
  "format": "turing-html-overlays",
  "formatVersion": 1,
  "schemaVersion": 5,
  "display": {
    "width": 480,
    "height": 480
  },
  "elements": [
    {
      "id": "cpu-value",
      "x": 40,
      "y": 300,
      "width": 120,
      "height": 40,
      "fontSize": 24,
      "color": "#ffffff",
      "fontWeight": 700,
      "textAlign": "center",
      "opacity": 100,
      "zIndex": 1000,
      "visible": true,
      "componentType": "cpu-temperature",
      "generatedWidget": true,
      "binding": "cpu.temperature",
      "formatter": "temperature",
      "sample": "49°C",
      "elementKind": "text",
      "effectsManaged": true,
      "gradientEnabled": false,
      "gradientStartColor": "#ffffff",
      "gradientEndColor": "#66e0ff",
      "gradientDirection": "horizontal",
      "outlineWidth": 0,
      "outlineColor": "#000000",
      "glowRadius": 0,
      "glowColor": "#ffffff"
    }
  ]
}
```

`formatVersion` versions the public document envelope. `schemaVersion` versions
the element/style fields understood by the editor. Schema 5 stores `binding`,
`formatter`, and `sample` explicitly. Catalog components still provide safe
defaults, while converted themes may use validated snapshot paths without
adding a new hard-coded component for every legacy YAML metric.

`generatedWidget` controls ownership of the HTML node. When true, the editor
derives the local widget markup from this document. Existing authored HTML
elements may keep it false while still declaring their binding for future
native-overlay compilation.

Bindings use a safe dotted snapshot path such as `cpu.frequency`,
`network.download`, or `memory.available`; `$timestamp` is the only special
root. Formatters are selected from the local runtime allowlist, including text,
integer/decimal, percent, temperature, memory/data sizes, network rate, clock,
date, duration, FPS, load, and 0-100 bar output.

## Compatibility migration

Themes using `.html-theme-editor.json` remain readable. The canonical document
takes precedence if both files exist. On the next successful save:

1. `overlays.json` is written atomically;
2. generated artifacts and manifest regions are synchronized;
3. the legacy file receives a one-time `.visual.editor-backup` copy;
4. the legacy file is removed.

The multi-file save retains the previous content and restores every affected
file if any write or final manifest validation fails.

Portable `.theme` imports validate a declared overlay document before installing
the theme. Invalid schema versions, duplicate element IDs, unsafe dimensions,
or display mismatches reject the package.
