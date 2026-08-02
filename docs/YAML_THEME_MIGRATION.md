# YAML theme migration

The first migration tool is deliberately read-only. It parses a legacy
`theme.yaml`, resolves display geometry and assets, maps visible dynamic nodes
to the HTML sensor snapshot, and reports what can be converted safely before
any output theme is created.

## Analyze a theme

```bash
python3 theme-migrate.py analyze res/themes/24
python3 theme-migrate.py analyze res/themes/ColoredFlat --json
```

The source may be a theme directory or its `theme.yaml`/`theme.yml` file. The
command never edits the YAML, images, fonts, video, or application
configuration.

The JSON form includes:

- display dimensions and whether they came from `DISPLAY_SIZE` or inferred
  element geometry;
- native-video and static-layer inventory;
- every visible and hidden dynamic overlay;
- proposed `binding` and `formatter` values;
- referenced fonts/assets and unresolved paths;
- an overall readiness classification.

## Readiness levels

- `automatic`: every visible dynamic node is currently representable as text
  or a 0-100 bar with an available HTML snapshot binding;
- `assisted`: layout can be migrated, but at least one overlay needs a radial,
  history, non-standard range, ping, or other runtime addition;
- `manual`: the display cannot be determined or custom Python sensor data needs
  an explicit adapter.

Ethernet and Wi-Fi paths are reported with a warning because the current HTML
snapshot exposes only the selected interface. Device-only paths such as
`/mnt/SDCARD/video/...` are inventoried but cannot be copied into a portable
package without a matching local source.

## Explicit overlay bindings

`overlays.json` schema 5 adds validated `binding`, `formatter`, `sample`, and
`generatedWidget` fields. This removes the requirement that every converted
YAML metric first be added to the editor's fixed component menu. Bindings are
restricted to renderer snapshot paths, and formatters come from a local
allowlist; neither field can execute JavaScript or access the network.

The next migration slice will consume the analysis report to create a new
`<theme-name>-html` draft. It will not overwrite the YAML source. Radial and
history components remain separate follow-up work.
