# YAML theme migration

The migration tool first analyzes a legacy `theme.yaml`, then can generate a
new editable HTML directory or portable `.theme` draft without changing the
source. It resolves display geometry and assets and maps visible dynamic nodes
to the HTML sensor snapshot.

## Analyze a theme

```bash
python3 theme-migrate.py analyze res/themes/24
python3 theme-migrate.py analyze res/themes/ColoredFlat --json
```

The source may be a theme directory or its `theme.yaml`/`theme.yml` file. The
analyze command never edits the YAML, images, fonts, video, or application
configuration.

## Convert one theme

```bash
python3 theme-migrate.py convert res/themes/24 ~/Downloads/24-html.theme
python3 theme-migrate.py convert res/themes/24 ~/Downloads/24-html-directory
```

The converter copies the original YAML into `source/theme.yaml`, brings local
static images and referenced fonts into the draft, emits canonical
`overlays.json`, and generates text/bar markup, CSS, local runtime, manifest,
and `migration-report.json`. A compatible local MP4 is included when available.
The destination must not exist.

Assisted/manual themes are rejected by default. `--allow-partial` creates a
review draft containing only supported overlays and records every skipped node.
Themes with no supported visible overlays remain listed as skipped.

## Convert a collection

```bash
python3 theme-migrate.py batch res/themes ~/Downloads/turing-html-converted
python3 theme-migrate.py batch res/themes ~/Downloads/turing-html-partial --allow-partial
```

Without `--allow-partial`, batch mode packages every automatic theme and lists
assisted/manual themes in `batch-report.json`. Output is assembled in a
temporary directory and published atomically; an existing destination is never
overwritten.

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

## Implementation checklist

- [x] Read-only compatibility analysis with text and JSON reports.
- [x] Explicit sensor binding and formatter mapping.
- [x] Non-destructive HTML directory and `.theme` generation.
- [x] Batch generation with an atomic destination and machine-readable report.
- [x] Static image, static text, local font, preview, and compatible MP4 copy.
- [x] Canonical editable `overlays.json` plus generated text/bar runtime.
- [ ] Visual approval of each converted theme against its YAML source.
- [ ] Bake static YAML layers into copied/generated native video backgrounds.
- [ ] Radial and line/history components.
- [ ] Ping, CPU fan, separate Ethernet/Wi-Fi, and custom-data adapters.
- [ ] Automatic screenshot comparison with documented tolerance.
