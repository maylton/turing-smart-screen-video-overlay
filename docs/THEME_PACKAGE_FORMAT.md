# Portable `.theme` package format

Format identifier: `turing-smart-screen-theme`  
Current format version: `1`  
Container: ZIP with the `.theme` extension

## Purpose

A `.theme` file is the portable, single-file representation used for sharing,
importing, exporting, and backing up a theme. The application validates and
extracts it into a normal managed theme directory before editing or rendering.
WebKit, FFmpeg, relative assets, and native-video synchronization therefore
continue to use real local paths.

The legacy `.zip` importer remains supported. New exports use `.theme` unless a
`.zip` destination is requested explicitly.

## Canonical layout

Files are stored directly at the archive root; there is no outer directory.

HTML package:

```text
material-expressive.theme
├── theme-package.json
├── manifest.json
├── index.html
├── style.css
├── theme.js
├── assets/
└── generated background/preview files
```

YAML package:

```text
classic-theme.theme
├── theme-package.json
├── theme.yaml
├── preview.png
└── local theme assets
```

Future packages may organize authored and generated files into `source/`,
`assets/`, and `dist/`. Version 1 intentionally preserves current theme-relative
paths so existing renderers and editors remain compatible.

## Root descriptor

`theme-package.json` describes the container rather than replacing the HTML
theme manifest or YAML definition.

```json
{
  "format": "turing-smart-screen-theme",
  "formatVersion": 1,
  "name": "material-expressive",
  "engine": "html",
  "definition": "manifest.json"
}
```

Fields:

- `format`: fixed format identifier;
- `formatVersion`: integer schema version;
- `name`: suggested installed folder name;
- `engine`: `html` or `yaml`;
- `definition`: root `manifest.json`, `theme.yaml`, or `theme.yml`.

Unknown format versions are rejected rather than interpreted as version 1.
Imported names are sanitized and receive a numeric suffix instead of
overwriting an existing theme.

## Import safety policy

Before extraction the importer rejects:

- absolute paths, `..` traversal, Windows-style traversal, and invalid names;
- duplicate paths and case-insensitive path collisions;
- encrypted entries, symbolic links, and other special filesystem objects;
- more than 4,096 archive members;
- individual members larger than 256 MiB;
- archives larger than 512 MiB when uncompressed;
- large members with a suspicious compression ratio.

After extraction it validates the descriptor, required definition file, engine,
HTML manifest, CSP, local-only permissions, and network policy. Existing themes
are never overwritten.

## Export behavior

Export is atomic: the archive is first written to a temporary file next to the
destination and then renamed into place. Existing destinations are rejected.

Temporary files, editor backups, repair backups, video-working snapshots,
Python caches, and symbolic links are not exported. Symbolic links cause the
export to fail explicitly so an external target can never be copied into a
theme package accidentally.

Explicit `.zip` destinations retain the legacy outer-folder layout for backward
compatibility. The `.zip` format does not include `theme-package.json`.
