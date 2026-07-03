# Turing Smart Screen Video Overlay — Theme Editor Detailed Roadmap

> Detailed implementation roadmap for the GTK Theme Editor and adjacent tooling.
> This document is intended to live both locally and in the repository so it can guide
> manual development and Codex-assisted development consistently.

---

## 1. Purpose

This roadmap documents, in a detailed and operational way, the planned evolution of the
modern GTK Theme Editor and related media/theme workflows in the project:

```text
maylton/turing-smart-screen-video-overlay
```

It serves four goals:

1. **Project direction** — define what comes next and in what order.
2. **Implementation guardrails** — clarify boundaries, dependencies, and non-goals.
3. **Codex handoff** — provide a stable source of truth for automated implementation prompts.
4. **Review support** — make it easier to validate whether a change matches the intended roadmap.

---

## 2. Project principles

All future work described here should preserve these principles.

### 2.1. One change at a time

- Work in **small, isolated increments**.
- Each feature should be developed in its own branch.
- Prefer one coherent implementation step per checkpoint.

### 2.2. Test before commit

Every implementation step should be validated with:

- pure/module tests when applicable;
- full unit test suite;
- `git diff --check`;
- targeted visual/manual testing in the GTK app when UI is involved.

### 2.3. No silent format drift

Avoid unnecessary changes in unrelated files such as:

- `config.yaml`;
- `res/themes/*/theme.yaml`;
- generated user assets;
- formatting-only edits outside the intended scope.

If these files are touched only because of manual testing, they should normally be restored before commit.

### 2.4. Preserve open theme architecture

The editor should continue to favor:

- open YAML themes;
- explicit, understandable structure;
- recoverable/transparent transformations;
- non-destructive editing when possible;
- atomic saves;
- Undo/Redo;
- compatibility with existing themes.

### 2.5. Prefer pure logic outside GTK

Any logic that can be tested without GTK should live in pure helper modules.

Examples:

- geometry/layout calculation;
- media transformation logic;
- manifest parsing/writing;
- data-source catalogs;
- canvas hit-testing.

This keeps the project testable and makes Codex implementations safer.

---

## 3. Current status summary

At the time this roadmap was produced, the following major pieces are already implemented or underway.

### 3.1. Completed or substantially implemented

#### Theme elements navigator
- visual navigator replacing a raw YAML-only browsing experience;
- semantic grouping and friendly labels;
- state filters;
- search integration;
- element actions;
- better visibility control for static items.

#### Layer ordering foundation + navigator integration
- explicit ordering within `static_images` and `static_text`;
- `Move backward`;
- `Move forward`;
- `Send to back`;
- `Bring to front`;
- `Layer N of M` indicator;
- Undo/Redo;
- reordering limited to same container;
- tree and preview kept in sync.

#### Static image layout inspector (Media Inspector V1)
- `Original size`;
- `Fit`;
- `Fill`;
- `Stretch`;
- `Custom size`;
- zoom;
- 3×3 alignment;
- preview before apply;
- non-destructive geometry update;
- Apply changes only to:
  - `X`;
  - `Y`;
  - `WIDTH`;
  - `HEIGHT`.

### 3.2. Current checkpoint / next checkpoint

#### Static image transform inspector (Media Inspector V2)
Implemented in the current checkpoint:
- rotation 0/90/180/270 clockwise;
- mirror horizontal;
- mirror vertical;
- transform preview;
- generated PNG assets;
- transform provenance manifest;
- restore original `PATH` on reset;
- Undo/Redo with `PATH + geometry`.

The next planned implementation checkpoint is Static image crop inspector
(Media Inspector V3), after visual validation of V2 in the GTK app.

---

## 4. High-level roadmap phases

The roadmap is organized in five major product phases, inspired by both our own design goals
and the capabilities observed in the official Windows software.

## Phase 1 — Layers and visual ordering
**Status:** Completed

Delivered:
- explicit draw order;
- move forward/backward;
- send to back/bring to front;
- layer indicator;
- Undo/Redo;
- reordering limited to same container.

Still possible later (not required to consider phase completed):
- drag-and-drop layering;
- dedicated layer panel;
- cross-category text/image stacking (would require runtime changes).

---

## Phase 2 — Integrated media inspector
**Status:** Partially completed

This is being implemented in multiple sub-stages.

### 2.1. Images — Layout
**Status:** Completed

Delivered:
- layout modes;
- zoom;
- alignment;
- preview;
- Apply/Cancel;
- Undo/Redo.

### 2.2. Images — Transform
**Status:** Implemented; pending visual validation

Delivered:
- 0/90/180/270 clockwise rotation;
- horizontal and vertical mirror;
- combined transform and layout preview;
- deterministic derived PNG assets;
- transform provenance manifest;
- original source preservation;
- identity transform restoring the original `PATH`;
- Undo/Redo for `PATH`, `X`, `Y`, `WIDTH`, and `HEIGHT`.

### 2.3. Images — Crop
**Status:** Planned

Target:
- visual crop region;
- crop handles;
- presets;
- crop-aware preview;
- derived assets;
- manifest support;
- Undo/Redo.

### 2.4. Generated media management
**Status:** Planned

Target:
- inspect generated assets;
- show provenance;
- show usage;
- remove safe unused assets.

### 2.5. Video inspector
**Status:** Planned

Target:
- integrate existing media preparation workflow into the theme editor;
- then expand toward near-parity with the Windows flow:
  - Fit/Fill/Stretch;
  - crop;
  - zoom;
  - rotation;
  - mirror;
  - alignment;
  - trim;
  - speed;
  - loop;
  - preview;
  - conversion.

---

## Phase 3 — Separate data source from visualization
**Status:** Not started

Goal:
separate **what data is shown** from **how it is visualized**.

Conceptual flow:

```text
Add data element
   ↓
Choose source
   CPU usage
   GPU temperature
   RAM
   Network
   Date
   Time
   ...
   ↓
Choose visualization
   Text
   Bar
   Radial
   Chart
   Arc
   Icon + text
```

This is a large architectural phase and will be split into:
1. pure catalogs;
2. compatibility matrix;
3. GTK creation wizard.

---

## Phase 4 — Direct canvas manipulation
**Status:** Mostly not started

Goal:
edit elements directly from the preview canvas instead of only from forms.

Expected capabilities:
- selection by click;
- bounding box;
- movement by drag;
- resize handles;
- snapping;
- guides;
- alignment actions;
- layer operations from canvas.

This phase requires a pure geometry/hit-testing model first.

---

## Phase 5 — Preview on display
**Status:** Not started as a full workflow

Goal:
implement a safe, modern equivalent to the Windows software’s “Run/Preview” flow.

Conceptual flow:

```text
Validate
   ↓
Prepare assets
   ↓
Snapshot current display state
   ↓
Apply temporary theme
   ↓
Show progress
   ↓
Keep or Restore
```

Required:
- validation;
- progress reporting;
- recovery on failure;
- restore previous state;
- temporary preview logic.

---

## 5. Detailed implementation sequence

The sequence below is the recommended order for actual implementation work.

---

# Step 0 — Validation gate for Media Inspector V2
**Status:** Code/test validation complete; visual validation pending

## Goal
Before moving ahead, confirm the transform inspector works end-to-end.

## Branch
```text
feature/theme-media-transform-inspector
```

## Validate
- rotate 90/180/270;
- mirror horizontal/vertical;
- combined transforms;
- preview generation;
- generated asset naming;
- transform manifest;
- no original overwrite;
- identity transform restoring original `PATH`;
- Undo/Redo restoring:
  - `PATH`;
  - `X`;
  - `Y`;
  - `WIDTH`;
  - `HEIGHT`;
- Cancel leaving no YAML/manifest/asset changes.

## Suggested checkpoint commit
```text
Add static image transform inspector
```

---

# Step 1 — Media Inspector V3: visual image crop

## Goal
Add visual crop to the same image inspector.

## Suggested branch
```text
feature/theme-media-crop-inspector
```

## Pipeline order
```text
EXIF transpose
→ rotation
→ horizontal mirror
→ vertical mirror
→ crop
→ layout mode
→ zoom
→ alignment
```

## Key design rule
Crop should be defined in the space of the **already transformed image**, because that is what the user sees.

However, the whole recipe must still be reconstructed from the **original source**, never by repeatedly cropping a previously derived asset.

## Planned capabilities
- interactive crop rectangle;
- drag crop region;
- resize from handles;
- optional locked aspect ratio;
- crop presets:
  - Free;
  - Square;
  - Canvas ratio;
  - Source ratio;
- Reset crop;
- crop-aware preview;
- derived asset generation;
- manifest support;
- recovery of crop settings when reopening;
- Undo/Redo.

## Manifest considerations
The transform manifest created in V2 must be audited first.

Preferred approach:
- preserve backward compatibility if possible;
- add crop metadata safely;
- if schema migration is needed, do it explicitly and safely;
- never destroy older manifest data.

## Out of scope
- video crop;
- free-angle rotation;
- perspective transform;
- masking;
- auto-cleanup of assets.

## Suggested checkpoint commit
```text
Add visual crop to image inspector
```

---

# Step 2 — Generated media manager

## Goal
Make generated PNG assets visible and manageable.

## Suggested branch
```text
feature/theme-generated-media-manager
```

## Why it comes here
Once transform + crop exist, derived assets become more numerous.
A management layer should be added before we expand into video.

## Planned capabilities
- list generated assets for the current theme;
- preview generated assets;
- show original source;
- show transform/crop recipe;
- indicate:
  - referenced/in use;
  - unreferenced;
  - orphaned;
- reveal in file manager;
- validate manifest integrity;
- remove unused generated assets safely;
- never remove:
  - referenced assets;
  - unregistered arbitrary files;
  - user-owned non-managed assets.

## Out of scope
- automatic deletion;
- cross-theme global asset cleanup;
- cloud/media library.

## Suggested checkpoint commit
```text
Add generated media manager
```

---

# Step 3 — Video Inspector V1: editor integration

## Goal
Integrate the existing media preparation app into the Theme Editor.

## Suggested branch
```text
feature/theme-video-inspector-integration
```

## Strategy
Do not re-implement the media preparation stack from scratch in `theme-editor-gtk.py`.

Instead:
- reuse/refactor the existing GTK media preparation flow;
- open it as a child/transient editor workflow;
- pass in theme/profile/video context;
- return prepared media path back to the theme editor.

## First delivery
- action `Adjust video…`;
- open video preparation in theme context;
- preselect display profile;
- preload the current local video if available;
- return the prepared output path;
- Apply updates `video.PATH`;
- one Undo state;
- refresh preview/background;
- Cancel leaves theme unchanged.

## Out of scope
- full inline embed in properties;
- upload to display;
- remote-only video editing;
- Preview on display.

## Suggested checkpoint commit
```text
Integrate video preparation with theme editor
```

---

# Step 4 — Video Inspector V2: near-parity transform workflow

## Goal
Extend video editing toward parity with the Windows editor’s most useful workflow.

## Suggested branch
```text
feature/theme-video-transform-inspector
```

## Planned capabilities
- Original/Fit/Fill/Stretch/Custom;
- crop;
- zoom;
- rotate;
- mirror horizontal/vertical;
- 3×3 alignment;
- trim;
- speed;
- loop;
- FPS;
- background modes;
- preview;
- conversion;
- Apply result to theme.

## Backend requirement
Extend the video conversion settings/backend to support mirror flags.

Likely additions:
- `flip_horizontal`;
- `flip_vertical`;

and FFmpeg filter integration:
- `hflip`;
- `vflip`.

## Out of scope
- upload to display;
- hardware preview;
- direct editing of remote-only videos without local access.

## Suggested checkpoint commit
```text
Add full video transform inspector
```

---

# Step 5 — Preview validation pipeline

## Goal
Create safe validation infrastructure before touching the device for preview.

## Suggested branch
```text
feature/theme-display-preview-validation
```

## Planned validations
- YAML parse/structure validity;
- display dimensions/profile compatibility;
- image file presence;
- font presence;
- manifest integrity;
- generated asset validity;
- video presence;
- video compatibility;
- safe paths;
- incomplete components;
- invalid intervals;
- invalid numeric ranges;
- empty or inconsistent layer groups.

## Outputs
Structured validation report with:
- errors;
- warnings;
- informational messages.

## UI ideas
- `Validate theme` action;
- result panel/list;
- direct navigation to problematic items.

## Out of scope
- actually applying the theme to the hardware.

## Suggested checkpoint commit
```text
Add theme preview validation pipeline
```

---

# Step 6 — Preview on display

## Goal
Create a temporary apply/preview flow similar in spirit to the official Windows “Run” behavior.

## Suggested branch
```text
feature/theme-preview-on-display
```

## Flow
```text
Validate
→ Prepare assets
→ Snapshot current display state
→ Apply temporary theme
→ Show progress
→ Preview running
→ Keep or Restore
```

## Required capabilities
- clear primary action: `Preview on display`;
- progress reporting;
- cancelation;
- timeout handling;
- prevent concurrent preview operations;
- snapshot and restore previous state;
- recovery after failure;
- keep editor open;
- support fast re-preview;
- distinguish:
  - temporary preview;
  - permanent application.

## Out of scope
- final release packaging workflow;
- cloud sync;
- multi-user device orchestration.

## Suggested checkpoint commit
```text
Add temporary preview on display
```

---

# Step 7 — Data source catalogs

## Goal
Create pure data-source and visualization catalogs.

## Suggested branch
```text
feature/theme-data-source-catalog
```

## New modules (suggested)
```text
library/theme_data_sources.py
library/theme_visualizations.py
library/theme_data_visualization_compat.py
```

## Data sources (initial examples)
- CPU usage;
- CPU temperature;
- GPU usage;
- GPU temperature;
- GPU memory;
- RAM usage;
- disk usage;
- network download/upload;
- ping;
- weather;
- uptime;
- date;
- time.

## Visualizations (initial examples)
- Text;
- Progress bar;
- Radial;
- Arc;
- Line graph;
- Icon + text.

## Additional metadata
- unit;
- default format;
- recommended min/max;
- supported visualizations;
- generated YAML shape;
- platform availability.

## Out of scope
- GTK wizard UI;
- migration of all existing themes in the same step.

## Suggested checkpoint commit
```text
Add data source and visualization catalogs
```

---

# Step 8 — Data element creation wizard

## Goal
Expose the source/visualization split through a guided GTK creation workflow.

## Suggested branch
```text
feature/theme-data-element-wizard
```

## Target flow
```text
Add data element
→ Choose source
→ Choose visualization
→ Configure format
→ Choose preset
→ Preview
→ Add
```

## Planned capabilities
- search;
- categories;
- compatibility visibility;
- guided steps;
- preview;
- presets;
- generated YAML creation;
- automatic selection of the new item;
- Undo/Redo.

## Constraints
- should not break existing components;
- should support gradual coexistence with legacy/static definitions.

## Suggested checkpoint commit
```text
Add data element creation wizard
```

---

# Step 9 — Canvas interaction model

## Goal
Build a pure geometry model for future direct canvas editing.

## Suggested branch
```text
feature/theme-canvas-interaction-model
```

## Planned model fields
For each visual element:
- path;
- type;
- x;
- y;
- width;
- height;
- visibility;
- z-order;
- container/group;
- possibly lock state.

## Planned helpers
- bounding box extraction;
- hit-testing;
- overlap/intersection;
- topmost element selection;
- coordinate transforms;
- snapping candidates.

## Out of scope
- visible handles;
- live GTK drag interactions.

## Suggested checkpoint commit
```text
Add canvas interaction model
```

---

# Step 10 — Canvas direct selection and movement

## Goal
Enable direct element selection and drag movement in the preview.

## Suggested branch
```text
feature/theme-canvas-selection-drag
```

## Planned capabilities
- click-to-select;
- selection highlight/bounding box;
- drag to move;
- live coordinates;
- keyboard arrows;
- Shift for larger increments;
- Escape to cancel gesture;
- one Undo step per drag gesture;
- snap to center and edges;
- visual guides.

## Out of scope
- resize handles;
- complex alignment operations.

## Suggested checkpoint commit
```text
Add direct canvas selection and movement
```

---

# Step 11 — Canvas resize and quick actions

## Goal
Complete the first practical direct-manipulation canvas editor.

## Suggested branch
```text
feature/theme-canvas-resize-actions
```

## Planned capabilities
- resize handles;
- proportional resize;
- free resize;
- quick alignment actions;
- distribute actions;
- duplicate;
- hide/show;
- delete;
- layer operations;
- optional grid.

## Out of scope
- full design-tool complexity;
- arbitrary transforms;
- multi-select advanced tooling (can come later).

## Suggested checkpoint commit
```text
Add direct canvas resize and actions
```

---

## 6. Consolidated recommended order

The recommended implementation order is:

```text
Media Inspector V2 — Transform
↓
Media Inspector V3 — Crop
↓
Generated Media Manager
↓
Video Inspector V1 — Editor integration
↓
Video Inspector V2 — Full transform workflow
↓
Preview Validation
↓
Preview on display
↓
Data Source Catalogs
↓
Data Element Wizard
↓
Canvas Interaction Model
↓
Canvas Selection/Drag
↓
Canvas Resize/Actions
```

---

## 7. Progress estimation

### After Media Inspector V2
```text
Phase 1 — Layers                         100%
Phase 2 — Media inspector               ~60%
Phase 3 — Source × visualization          0%
Phase 4 — Direct canvas                  ~10%
Phase 5 — Preview on display              0%
```

### After Media Inspector V3 + Video Inspector V2
```text
Phase 1 — Layers                         100%
Phase 2 — Media inspector               100%
Phase 3 — Source × visualization          0%
Phase 4 — Direct canvas                  ~10%
Phase 5 — Preview on display              0%
```

---

## 8. Branching and checkpoint conventions

Recommended conventions:

### Branch naming
- `feature/theme-media-transform-inspector`
- `feature/theme-media-crop-inspector`
- `feature/theme-generated-media-manager`
- `feature/theme-video-inspector-integration`
- `feature/theme-video-transform-inspector`
- `feature/theme-display-preview-validation`
- `feature/theme-preview-on-display`
- `feature/theme-data-source-catalog`
- `feature/theme-data-element-wizard`
- `feature/theme-canvas-interaction-model`
- `feature/theme-canvas-selection-drag`
- `feature/theme-canvas-resize-actions`

### Commit naming examples
- `Add static image transform inspector`
- `Add visual crop to image inspector`
- `Add generated media manager`
- `Integrate video preparation with theme editor`
- `Add full video transform inspector`
- `Add theme preview validation pipeline`
- `Add temporary preview on display`
- `Add data source and visualization catalogs`
- `Add data element creation wizard`
- `Add canvas interaction model`
- `Add direct canvas selection and movement`
- `Add direct canvas resize and actions`

---

## 9. Standard validation protocol for every step

For every roadmap step:

### Before implementation
- start from a clean worktree;
- confirm current branch and last checkpoint;
- create a dedicated feature branch.

### During implementation
- keep scope constrained to the planned files;
- avoid touching unrelated project areas;
- keep pure logic outside GTK when possible.

### Required validation
- `py_compile` for affected modules;
- focused unit tests for new module(s);
- full unit suite;
- `git diff --check`;
- `git diff --stat`;
- `git status --short`.

### Manual validation when UI is involved
- launch GTK editor with a theme;
- test success path;
- test Cancel/no-op path;
- test Undo/Redo;
- test selection preservation;
- test preview refresh;
- test that unrelated theme fields are not mutated accidentally.

### Before commit
- restore incidental changes in:
  - `config.yaml`;
  - `res/themes/*/theme.yaml`;
  - temporary/generated files not meant for commit.

---

## 10. Codex usage guidance

This roadmap is also meant to guide Codex work.

For Codex-driven implementation:

1. Start from the exact checkpoint branch/commit documented here.
2. Use a narrow scope and explicitly list allowed files.
3. Explicitly list prohibited files for that step.
4. Require:
   - pure tests;
   - full suite;
   - `git diff --check`;
   - no commit;
   - no push.
5. Review visually before creating checkpoint commits manually.

This document should be referenced directly by future prompts whenever helpful.

---

## 11. Suggested repository placement

Recommended location in the repository:

```text
docs/ROADMAP_THEME_EDITOR_DETAILED.md
```

Optionally, the shorter `docs/ROADMAP.md` can continue to track high-level status, while this file remains the long-form implementation guide.

---

## 12. Immediate next action

Assuming Media Inspector V2 has just been prepared, validated and committed, the **next planned implementation** is:

```text
Media Inspector V3 — Visual Crop
```

Base branch:
```text
feature/theme-media-transform-inspector
```

New branch:
```text
feature/theme-media-crop-inspector
```

This will be the next major step toward completing **Phase 2 — Integrated media inspector**.

---

## 13. Final note

This roadmap is intentionally detailed. It is not just a list of ideas — it is a development contract.

When a roadmap item is implemented, the result should be reviewable against:
- its declared goal;
- its explicit scope;
- its non-goals;
- its validation requirements;
- its suggested checkpoint.

That discipline is what will let the GTK editor grow toward — and in many areas surpass — the usability of the official Windows tooling, while keeping our architecture cleaner, more testable, and more open.
