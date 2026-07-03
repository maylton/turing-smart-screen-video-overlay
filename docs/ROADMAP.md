# Roadmap

## Checkpoint 1 — Runtime and native-video foundation

Status: **completed and hardware validated**

- exclusive process-wide ownership of the USB/serial display;
- real owner role/PID reporting;
- duplicate monitor prevention;
- asynchronous GTK stop and power actions;
- complete process reaping and serial-port release;
- explicit native-video stop during shutdown;
- structured JSON video-manager protocol;
- safe remote-path normalization;
- mandatory compatibility probing for GTK uploads;
- SD/internal list, size, upload, play, stop, and delete;
- automated runtime and media-safety tests.

## Checkpoint 2 — Installation and documentation readiness

Status: **implemented by the packaging/documentation checkpoint**

- GTK-aware project virtual environment using system site packages;
- installation-time dependency, syntax, and application checkup;
- isolated two-pass update test;
- explicit verification that configuration, custom themes, and media are
  preserved;
- fork-specific installation, update, validation, and troubleshooting
  documentation;
- corrected README support scope for native Rev. C video/storage features.

## Current implementation — Media preparation editor MVP

Status: **implemented for isolated and hardware validation**

Tracking issue:
[#7 — Media preparation editor for GIF and arbitrary video inputs](https://github.com/maylton/turing-smart-screen-video-overlay/issues/7)

The MVP branch provides a GTK workflow that:

- imports GIF, MP4, MKV, WebM, MOV, and AVI;
- displays source metadata from FFprobe;
- offers Fit, Fill/Cover, and Stretch modes;
- supports drag positioning, zoom, and centering;
- trims start and end;
- offers 24 and 30 FPS presets;
- converts to H.264 MP4, 480×480, and `yuv420p`;
- removes audio by default;
- previews the converted output;
- uploads the result through the hardened video-manager backend;
- stores temporary output in the user cache directory;
- performs conversion and upload outside the GTK main thread.

## Later phases

### Advanced framing

- original-size and fully custom modes;
- numeric X/Y/width/height controls;
- crop handles, rotation, and alignment shortcuts;
- solid, blurred, or custom-image backgrounds;
- GIF loop and playback-speed controls.

### Multiple display profiles

- target dimensions selected from the active display/theme;
- reusable conversion profiles;
- firmware-specific codec constraints;
- storage estimation before upload.

### Release readiness

- screenshots and fork-specific release notes;
- versioned changelog;
- repeatable release packaging;
- broader hardware/profile validation.

## Current implementation — Advanced media preparation

Status: **implemented for isolated and hardware validation**

The advanced editor adds:

- original-size and fully custom foreground modes;
- numeric crop margins;
- 0°/90°/180°/270° rotation;
- nine-point canvas alignment;
- solid, blurred-source, and custom-image backgrounds;
- playback-speed control;
- explicit finite input looping;
- automated unit and real-FFmpeg integration coverage.


## Current implementation — Multiple display profiles

Status: **implemented for isolated validation**

The profile-aware editor adds:

- automatic target resolution from the active theme;
- orientation-aware portrait and landscape dimensions;
- reusable square, portrait, landscape, and ultrawide presets;
- profile-specific H.264 and pixel-format constraints;
- hardware-validation and upload-safety metadata;
- native upload restricted to the validated Rev. C 2.1-inch profile;
- profile-aware preview aspect ratio;
- advisory output-size estimation before conversion;
- exact output size after conversion;
- rectangular-output unit and real-FFmpeg integration coverage.

## Current implementation — Automatic display detection

Status: **implemented for isolated and hardware validation**

- passive USB and serial descriptor scanning;
- safe exact-model mapping and ambiguity handling;
- automatic revision, AUTO port, and compatible-theme loading;
- Rev. C size-preservation fallback;
- startup detection before driver import;
- GTK detection status and manual rescan;
- atomic configuration backup and unit coverage.

## Next implementation — Release readiness

- screenshots and fork-specific release notes;
- versioned changelog;
- repeatable release packaging;
- broader hardware/profile validation;
- promotion of additional profiles from preview-only to native-upload support.


## Current implementation — Release readiness

Status: **implemented for isolated validation**

The release-readiness layer adds:

- a versioned changelog and first release-candidate notes;
- a machine-readable release manifest;
- explicit hardware-validation and preview-only boundaries;
- repeatable shell, Python, metadata, unit, whitespace, and FFmpeg checks;
- contract tests for required release files and fields;
- documented limitations without publishing a tag or GitHub Release.

## Release-candidate polish — Theme editor media integration

- fix repeated GTK property rows after Apply, Reset, Undo, or Redo;
- choose a local video or a video already stored on the display;
- browse SD-card and internal-memory videos through the existing backend;
- play or stop a selected remote video for physical preview;
- write the selected display path into the theme video section;
- extract an exact-size PNG background from a local video frame;
- update `video.PREVIEW_BACKGROUND` and refresh the GTK preview safely;
- retain the classic editor as a fallback while the migration is completed.

## Theme cloning and prepared-media reuse

- automatically reuse converted videos retained in the media-preparation cache;
- allow a display-side video to generate a background without reselecting the
  source when its local converted copy is still available;
- keep manual local selection as a fallback;
- add Save As to clone the complete current theme into a new editable theme;
- reject unsafe or conflicting theme names and open the new theme after cloning.

## True transparent native-video overlays

- render text, linear bars, line graphs, and radial widgets on RGBA canvases;
- ignore captured-frame `BACKGROUND_IMAGE` values while native video is active;
- transmit only visible widget pixels through the Rev. C D0 visibility map;
- preserve solid/image backgrounds for non-video themes;
- prevent moving video from appearing frozen inside widget rectangles.

## Text effects and reliable theme cloning

- add shadow, glow, and outline to text rendering;
- preserve RGBA transparency over native video;
- expose effects in the GTK editor;
- ensure Save As imports shutil reliably.

## Theme editor text-style integration hardening

- forward text effects explicitly for every dynamic sensor text;
- support effects on text embedded in radial widgets;
- remove coordinate-based effect guessing;
- support RGB/RGBA strings, lists, hex values, and named colors;
- show color selectors for legacy comma-separated theme colors;
- use color selectors and numeric controls in the text-effects dialog;
- fix property type conversion and missing editor keys;
- restore the missing `shutil` import used by Save As.

## Theme property presets

- keep the existing visual editor workflow;
- add reusable preset dropdowns beside editable property fields;
- preserve free-form custom values;
- provide common choices for layout, typography, timing, graph, and radial parameters;
- discover fonts and theme background images dynamically;
- expose display size and orientation in the GTK property panel.

The preset menus are helpers for common values only. They fill the existing
manual property field and the user can still type any valid custom value before
clicking `Apply property changes`.

Initial preset coverage:

- display metadata: `DISPLAY_SIZE`, `DISPLAY_ORIENTATION`;
- layout: `X`, `Y`, `WIDTH`, `HEIGHT`, `RADIUS`, `ALIGN`, `ANCHOR`;
- text: `FORMAT`, `FONT_SIZE`, `AXIS_FONT_SIZE`, `FONT`, `AXIS_FONT`;
- timing: `INTERVAL`, `REFRESH_INTERVAL`;
- graphs and gauges: `MIN_VALUE`, `MAX_VALUE`, `MIN_SIZE`, `LINE_WIDTH`,
  `HISTORY_SIZE`, `ANGLE_START`, `ANGLE_END`, `ANGLE_STEPS`, `ANGLE_SEP`;
- media and decoration: `BAR_DECORATION`, `BACKGROUND_IMAGE`,
  `PREVIEW_BACKGROUND`.

Fonts are discovered recursively below `res/fonts` with `.ttf`, `.otf`, and
`.ttc` files stored as paths relative to that directory. Theme images are
discovered inside the selected theme directory with `.png`, `.jpg`, `.jpeg`,
`.webp`, `.bmp`, and `.gif` files stored as paths relative to the theme.

Still pending for later roadmap stages: context-aware preset filtering, compound
quick presets, property validation, live preview/debounce behavior, and broader
theme editor module extraction.

## Theme elements navigator

The GTK editor's left column now acts as a visual navigator for theme
components instead of a raw YAML list. YAML keys are preserved, but the tree
uses friendly labels such as `Video and background`, `Text`, `Images`,
`System metrics`, `Percentage text`, `Memory usage`, `Date`, and `Time`.

The navigator shows symbolic icons by element type, a theme-level summary, and
per-row states:

- `Visible` for active static elements, enabled video, or shown sensor parts;
- `Hidden` for `SHOW: false`, disabled video, or disabled sensor parts;
- `Mixed` for groups containing both visible and hidden descendants;
- `Configuration` or `Group` for structural nodes without display state.

The search field works together with the state filter:

- `All elements`;
- `Visible`;
- `Hidden`;
- `Mixed`;
- `Structure`.

The Add element control is embedded directly in the panel and is backed by the
central pure catalog in `library/theme_element_catalog.py`. It reports whether
an item is available, already visible, currently hidden, mixed, or repeatable,
and changes its action between `Add`, `Enable`, `Select`, and `Add another`.

The Actions menu replaces the fixed button grid. It exposes `Show / Enable`,
`Hide / Disable`, `Duplicate`, and `Delete`, with sensitivity based on the
current selection. Static text and static images now support `SHOW`, so they can
be hidden and shown without deleting their YAML entries. Themes without `SHOW`
on static elements remain compatible: absence still means visible.

Layer ordering is integrated for individual `static_images` and `static_text`
entries. Reorderable rows show labels such as `Layer 2 of 4 · Images` or
`Layer 3 of 5 · Text`. The Actions menu adds:

- `Move backward`, which moves the item one position toward the start of its
  mapping and draws it below its previous neighbor;
- `Move forward`, which moves the item one position toward the end of its
  mapping and draws it above its next neighbor;
- `Send to back`, which moves the item to the first position of its container;
- `Bring to front`, which moves the item to the last position of its container.

Images and text keep independent stacks. Static images are still drawn first,
then static text, so text remains above images and this stage does not reorder
across categories. There is no drag-and-drop yet; ordering is currently handled
through the Actions menu and preserves Undo/Redo, search, filters, selection,
and preview refresh.

Media Inspector V1 is implemented for individual `static_images` entries. It is
available from `Adjust image layout…` in Actions and from the contextual
`Image layout` row in Properties. The inspector is non-destructive: it renders a
local Pillow preview on a checkerboard background and only writes `X`, `Y`,
`WIDTH`, and `HEIGHT` when the user clicks Apply. It supports:

- Original size;
- Fit;
- Fill;
- Stretch;
- Custom size;
- 0.25× to 4.0× zoom;
- 3×3 alignment;
- Cancel without YAML changes;
- Apply with one Undo state and normal Redo support.

It does not add mode, zoom, alignment, source-size, or inspector metadata to the
theme YAML, and it does not modify or duplicate the original image asset.

Current limitations intentionally remain for future phases:

- renaming;
- drag-and-drop;
- cross-category reordering if the runtime drawing model changes;
- multiple selection;
- batch actions;
- a virtual `Available to add` group inside the tree;
- validation of incomplete element structures;
- a dedicated layers panel;
- crop;
- rotation;
- mirror;
- derivative asset generation;
- video inspector;
- conversion;
- upload;
- canvas resizing;
- preview on the display.

## Theme text and effect presets

Text style presets are compound helpers for the selected text-like element.
Unlike simple property presets, one text style preset can fill several existing
property controls at once. They are filtered by text category so clock presets
do not appear for metric percentages, and metric presets do not appear for
labels. They still do not save automatically: values remain editable and are
persisted only when `Apply property changes` is clicked.

Initial text style presets:

- `Large clock`;
- `Centered title`;
- `Metric value`;
- `Compact value`;
- `Small label`;
- `Caption`.

Text style presets only fill controls for properties already present on the
selected node. They do not add missing YAML keys, do not change `X` or `Y`, and
do not change text content, format, font, colors, visibility, intervals,
backgrounds, or effects.

Text effect presets fill the controls in the existing Text effects dialog and
are applied to the selected element only after the dialog's `Apply` response.
Initial effect presets:

- `None`;
- `Soft shadow`;
- `Strong shadow`;
- `Subtle glow`;
- `Neon glow`;
- `Thin outline`;
- `High-contrast outline`;
- `Glow + outline`;
- `Video overlay readable`.

Still pending for later roadmap stages: graph presets, radial indicator presets,
coordinate and size validation, palette/global style presets, live preview,
debounce behavior, multi-element application, and wizard-style theme creation.

## Theme Engine Semantic Presets

Semantic presets define global visual identities through named color roles such
as `BACKGROUND`, `SURFACE`, `PRIMARY`, `ON_SURFACE`, `OUTLINE`, `SUCCESS`,
`WARNING`, and `DANGER`. They are different from property presets: a property
preset fills one field in the editor, while a semantic visual preset resolves a
coherent token set and can apply those roles to existing color properties across
a theme copy.

Initial global presets:

- `tonal_expressive_dark`;
- `tonal_expressive_light`;
- `soft_neutral_dark`;
- `soft_neutral_light`;
- `technical_data_dark`;
- `technical_data_light`;
- `video_overlay_readable`;
- `monochrome_high_contrast`.

Initial YAML color mapping:

- `FONT_COLOR` -> `ON_SURFACE`;
- `BACKGROUND_COLOR` -> `SURFACE`;
- `BAR_COLOR` -> `PRIMARY`;
- `BAR_BACKGROUND_COLOR` -> `SURFACE_ALT`;
- `LINE_COLOR` -> `PRIMARY`;
- `AXIS_COLOR` -> `OUTLINE`;
- `DISPLAY_RGB_LED` -> `PRIMARY`.

The engine applies presets as a pure operation over a deep copy. It does not
save YAML, update previews, access files, or call the GTK editor. Geometry,
text content, font/media paths, video sections, static images, hierarchy, and
missing properties are preserved. `video_overlay_readable` preserves existing
`BACKGROUND_COLOR` by default so video or captured backgrounds remain readable,
while explicit `preserve_background=False` can override that policy.

Future phases remain intentionally separate: GTK integration, typography
presets, effect presets, bars, radial indicators, line graphs, complete layouts,
automated accessibility presets, and contrast validation.

## Theme Component Presets

Component presets sit one layer above semantic tokens. They describe reusable
settings for one selected node, such as typography, text effects, bars, radial
gauges, line graphs, and data palettes. They may reference semantic color roles
from the theme engine, but they remain pure data operations and do not save YAML,
open GTK, render previews, or modify sibling elements.

Initial component preset types:

- `typography`;
- `effects`;
- `bar`;
- `radial`;
- `line_graph`;
- `data_palette`.

The Phase B foundation applies presets only to properties already present on the
selected node. Missing properties are not added, geometry and text content are
preserved unless those exact editable fields already exist in the node, and
token references are resolved only when a semantic token mapping is supplied.

Still pending for later phases: GTK controls for component presets, richer
component detection, complete layout presets, automatic contrast checks, and
preview-assisted application.

## Theme Composition Presets

Composition presets combine one semantic visual preset with a set of component
rules. They provide a pure foundation for broader visual systems such as a video
HUD, compact metrics grid, or high-contrast readout. A composition first applies
the semantic token mapping to a theme copy, then applies matching component
presets to existing nodes only.

Initial composition presets:

- `video_hud_readable`;
- `compact_metrics_grid`;
- `monochrome_accessible_readout`.

Composition rules match existing nodes by path tokens and existing property
keys. They do not create missing elements, do not add missing properties, do not
save YAML, do not render previews, and do not call the GTK editor. Geometry,
text content, media paths, and unrelated sibling elements remain preserved by
default.

Still pending for later phases: editor integration, richer rule authoring,
complete generated layouts, preview comparison, contrast scoring, and
accessibility-specific validation.
