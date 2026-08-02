# Repository size, HTML package, and YAML migration audit

Status: implementation roadmap  
Baseline: `main` at `d304f19c7826`  
Audit date: 2026-08-02

## Implementation progress

- Completed: explicit Linux runtime payload with development and legacy-example
  exclusions.
- Completed: core font profile covering all 18 fonts referenced by bundled YAML
  themes and editor templates.
- Completed: `--full-fonts` opt-in installation and automatic preservation of
  non-core fonts referenced by installed custom themes.
- Measured default payload after these changes: approximately 86.3 MiB and 627
  files, before the Python environment and system libraries.
- Completed: versioned `.theme` container with canonical root layout, atomic
  export, safe extraction limits, and legacy `.zip` compatibility.
- Completed: canonical `overlays.json` representation for editor-managed HTML
  elements, including automatic migration from legacy hidden metadata.
- Next: explicit custom sensor bindings and the YAML conversion analyzer.

## Executive summary

The application code is not the main source of repository or installation
size. Most tracked bytes are legacy theme examples, fonts, bundled theme
assets, and test fixtures. The Linux installer also copies almost the complete
source checkout, so development-only and locally ignored files can leak into
an installation.

The recommended direction is:

1. install from an explicit runtime payload instead of a short exclusion list;
2. distribute legacy examples and the complete font catalog as optional packs;
3. use a `.theme` ZIP container as the user-facing unit of distribution;
4. make a declarative `overlays.json` the canonical representation of managed
   HTML overlays;
5. migrate YAML themes in stages, beginning with static layers, text, bars,
   and native-video backgrounds.

## Measured repository footprint

The audit found 2,786 tracked files and approximately 869.6 MiB of tracked
content. The local checkout occupied approximately 1.1 GiB because generated
or ignored content also existed under the theme directories.

| Category | Tracked size |
| --- | ---: |
| Legacy theme examples | 556.7 MiB |
| Fonts | 188.0 MiB |
| Other bundled themes | 75.4 MiB |
| LCD golden test fixtures | 20.4 MiB |
| External binaries and tools | 9.4 MiB |
| Documentation | 8.2 MiB |
| Development tools | 5.0 MiB |
| Runtime Python code | 2.1 MiB |
| Total | 869.6 MiB |

The Git object pack is approximately 846 MiB. Removing large files from a new
revision reduces release and installation size, but not existing clone history.
Shrinking clone size requires moving optional packs to release assets or LFS,
or a separately approved history rewrite.

### Highest-impact payload changes

- Do not install `res/themes/--Theme examples` with the core application.
- Do not install tests, CI files, developer documentation, release tooling,
  Windows-only external binaries, golden fixtures, logs, or editor backups.
- Keep only the fonts referenced by core themes in the base package. The 76
  tracked YAML themes reference 18 font files totaling approximately 8.4 MiB,
  compared with the current 188 MiB font tree.
- Offer the remaining themes and fonts as optional downloadable packs.
- Compress or generate the large LCD golden fixtures. Four fixtures totaling
  about 12.3 MiB compress to about 1.3 MiB with gzip.
- Avoid cross-theme asset links inside portable packages. Content-addressed
  storage or hard links may be used only in the managed installation cache.

The expected application-owned runtime payload is below 100 MiB after examples
and unused fonts are separated. This estimate excludes the Python environment
and system GTK/WebKit libraries.

## Code simplification candidates

Code refactoring primarily improves maintainability and startup behavior; it
does not save as much disk space as payload work.

### GTK editor and application shell

- `theme-editor-gtk.py` is an 8,000-line monolith. Split YAML persistence,
  widget models, property panels, preview rendering, media, and window wiring.
- `configure-gtk.py`, `sitecustomize.py`, and `usercustomize.py` apply a large
  patch stack at import time. Move patched implementations into normal classes
  and services, then remove the import hooks incrementally.
- Keep standalone tools only where they provide a documented diagnostic or
  fallback path. The integrated app shell remains the normal user entrypoint.
- Retire the classic editor only after the existing parity and release gates
  pass.

### Shared services

Repeated helpers should move into small reusable services:

- `AppPaths` for repository, configuration, resource, and theme paths;
- `ThemeRepository` for discovery, import, export, selection, and file lookup;
- `ConfigService` for atomic configuration reads and writes;
- one YAML persistence layer for safe load, round-trip edit, and atomic save.

### Dependencies and packaging

- Use separate dependency profiles for core runtime, GTK UI, classic Tk UI,
  GPU integrations, and build tooling.
- Move PyInstaller out of the normal runtime requirements.
- Make `sv-ttk`, `tkinter-tooltip`, and legacy tray dependencies optional when
  the classic UI is not installed.
- Replace the two nearly identical PyInstaller specs with one parameterized
  spec for release and debug builds.

## Proposed `.theme` package

`.theme` should be a ZIP-compatible distribution container, not a filesystem
mounted directly by the renderer.

```text
example.theme
├── theme-package.json
├── manifest.json
├── overlays.json
├── source/
│   ├── index.html
│   ├── style.css
│   └── theme.js
├── assets/
│   ├── fonts/
│   └── images/
├── dist/
│   ├── background.mp4
│   └── preview.png
└── build.json
```

Version 1 keeps current theme-relative paths and uses `theme-package.json` as a
container descriptor. The `source/`, `assets/`, `dist/`, and canonical
`overlays.json` separation remains the forward-compatible target for a later
format/compiler milestone.

The application flow should be:

```text
.theme -> validate -> extract to managed workspace/cache -> edit or run
       -> atomically repack when exporting or saving the portable package
```

WebKit, FFmpeg, relative HTML resources, native-video upload, and the editor all
work more reliably with real extracted paths. A content hash can identify the
cache, and unused extracted versions can be removed safely.

### Manifest additions

The root manifest should declare:

- package format version;
- stable theme ID, display name, author, license, and semantic version;
- minimum compatible application version;
- renderer engine and overlay ABI version;
- display dimensions and permissions;
- entrypoint and native-video artifacts;
- optional source availability;
- content hashes for integrity checks.

The importer should reject path traversal, excessive member count, excessive
uncompressed size, suspicious compression ratios, links and special files,
duplicate paths, and case-insensitive path collisions. Cryptographic signatures
can be introduced later without changing the basic container.

The existing gallery already imports and exports ZIP archives atomically, so
the first `.theme` milestone is an evolution of existing behavior rather than
a new subsystem. ZIP compression itself is not expected to reduce theme size
significantly because PNG, MP4, and font files are already compressed.

## Canonical managed overlay model

The current HTML editor synchronizes metadata, generated CSS, manifest atomic
regions, generated HTML nodes, and a copied JavaScript widget runtime. This
creates multiple representations of the same element.

`overlays.json` should become the canonical source for editor-managed elements:

- stable element ID and component type;
- sensor binding and formatter;
- bounds, visibility, and update cadence;
- text and font properties;
- bar direction, range, and fill behavior;
- gradient, outline, shadow, and glow;
- atomic-region priority and runtime renderer requirements.

Generated CSS, HTML compatibility nodes, and atomic regions should be derived
from this file. The generic widget runtime should be supplied by the
application through a versioned ABI instead of copied into every theme.

For editor-managed themes, a future lightweight runtime can play the compiled
MP4 and render declarative text/bar overlays without WebKit. Arbitrary custom
HTML themes can retain the current WebKit fallback.

## YAML migration feasibility

All 76 directly tracked YAML themes parsed successfully during the audit.

| Predominant theme shape | Themes | Initial feasibility |
| --- | ---: | --- |
| Text and bars | 49 (64%) | High |
| Radial widgets | 15 (20%) | Medium; needs radial component |
| Line/history graphs | 6 (8%) | Medium/high complexity |
| Native-video themes | 4 (5%) | High with current architecture |
| Custom runtime data | 2 (3%) | Assisted or manual conversion |

The themes contain 473 dynamic text nodes, 175 bar graphs, 36 radial widgets,
and 31 line/history graphs.

### Mapping

| YAML feature | New representation |
| --- | --- |
| Static image or text | Static background or compiled video layer |
| `TEXT` | Declarative text overlay with binding and formatter |
| `GRAPH` | Declarative bar overlay |
| `RADIAL` | New radial SVG/canvas/native component |
| `LINE_GRAPH` | Stateful history component |
| Widget `BACKGROUND_IMAGE` | Removed; normal compositing replaces erase/restore |
| Local font | Copied into `assets/fonts` with licensing metadata |
| Native video | `dist/background.mp4` plus declarative overlays |

### Current gaps

- Thirty-two themes reference network data, often distinguishing Ethernet and
  Wi-Fi, while the HTML snapshot currently exposes one selected interface.
- Four themes use CPU fan data.
- Three themes use ping.
- Two themes use custom data providers.
- The HTML component catalog needs generic formatting, radial widgets, history
  graphs, and more complete min/max/orientation behavior.

The migration tool should never overwrite the source. It should first emit a
compatibility report, then generate `<name>-html.theme`, copy assets and fonts,
build the background, and compare YAML and new-renderer screenshots. Exact
pixel parity cannot be assumed because Pillow and WebKit rasterize fonts and
anchors differently.

The text-and-bar cohort is the recommended first milestone. After bindings,
radials, and history graphs are added, approximately 70-80% of themes should be
convertible into useful automatic drafts. The remaining themes need manual
layout validation or custom data adapters.

## Implementation sequence

1. Add an explicit Linux runtime payload contract and packaging regression
   tests.
2. Remove legacy examples and development artifacts from new installations.
3. Split the complete font catalog and example themes into optional packs.
4. Extend ZIP import/export into a versioned `.theme` package.
5. Introduce canonical `overlays.json` data and derive generated files from it.
6. Build a YAML conversion analyzer and text/bar converter.
7. Add radial and history widgets plus missing sensor bindings.
8. Add the lightweight native overlay runtime for compiled themes.
9. Consolidate GTK entrypoints and retire patch layers after validation gates.

Each milestone must preserve existing user configuration, custom themes,
generated videos, the YAML renderer, physical transport limits, and the current
local-only HTML security policy.
