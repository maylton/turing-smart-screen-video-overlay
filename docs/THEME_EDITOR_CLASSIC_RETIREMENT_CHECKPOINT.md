# Theme Editor Classic Retirement Checkpoint

This checkpoint defines the safe path from the legacy/classic editor to the modern GTK Theme Editor.

The goal is not to delete the classic editor immediately. The goal is to make the GTK editor trustworthy enough that the classic editor can be hidden, then deprecated, then eventually removed without losing recovery paths.

## Current baseline

The modern GTK editor already has the core media workflow that previously required leaving the main editor:

- theme element navigator;
- layer ordering actions;
- static image layout inspector;
- static image transform/crop workflow;
- generated media manager;
- Video Inspector V2 with live preview;
- video mirror, trim, speed, loop, crop, rotation, background, FPS, CRF, conversion, theme preview background generation, and Undo/Redo;
- tools menu and overflow menu organization;
- contextual media actions from the property panel.

This means the project is past the media-editor expansion phase and is now in the parity/retirement phase.

## Retirement policy

Classic editor retirement must happen in stages.

```text
Available fallback
↓
Soft deprecation
↓
Hidden behind advanced action
↓
Disabled by default
↓
Removal only after release validation
```

The classic editor must remain reachable until the GTK editor covers the workflows below and those workflows are validated on at least one real theme plus one clean installed environment.

## Required parity gates

### Gate 1 — Safe session lifecycle

The GTK editor must protect user work during open, save, close, and reload.

Required:

- detect unsaved changes before closing;
- offer Save / Discard / Cancel;
- detect external theme file changes when possible;
- keep Undo/Redo intact after tool dialogs;
- recover gracefully from invalid YAML instead of replacing a valid file;
- never mutate `config.yaml`, theme YAML, generated media, or preview files as a side effect of simply opening the editor.

Validation:

- edit a simple value and close;
- cancel close and confirm the editor remains open;
- save and reopen;
- discard and confirm the original YAML is preserved;
- trigger a tool dialog and confirm Undo/Redo still works.

### Gate 2 — YAML access without returning to classic editor

The GTK editor must still support advanced users who need direct YAML access.

Required:

- open the current `theme.yaml` from the overflow menu;
- optionally open the theme folder;
- show a warning that external edits should be reloaded before continuing;
- avoid pretending that the GTK editor has parsed external edits until the theme is reloaded.

Validation:

- open theme folder;
- open theme YAML;
- externally edit a harmless value;
- reload/reopen and confirm the GTK editor reflects the change.

### Gate 3 — Background image parity

The GTK editor must cover the common `BACKGROUND_IMAGE` workflow.

Required:

- contextual action for image-like `BACKGROUND_IMAGE` fields;
- choose image from disk;
- copy/prepare it into the theme when needed;
- apply layout/transform/crop through the existing image inspector pipeline;
- preserve Undo/Redo;
- avoid overwriting user-owned files.

Validation:

- select a background image element;
- replace image;
- adjust fit/fill/custom layout;
- apply transform/crop;
- Undo/Redo;
- save/reopen.

### Gate 4 — Display preview validation before hardware apply

Before the classic editor is hidden, GTK needs a safe replacement for any workflow where the user expected to preview/apply a theme.

Required:

- structured validation report;
- missing asset detection;
- invalid media detection;
- profile/dimension compatibility checks;
- safe path checks;
- clear warnings vs blocking errors;
- no hardware write until validation succeeds.

Validation:

- valid theme passes;
- missing image reports an error;
- invalid video reports an error;
- unsupported profile reports an error/warning according to severity;
- validation does not mutate files.

### Gate 5 — Temporary preview on display

The final parity gate before soft retirement is a safe temporary hardware preview flow.

Required:

- snapshot current display/theme state;
- apply a temporary preview;
- show progress;
- prevent concurrent preview operations;
- offer Keep / Restore;
- restore previous state on failure or user choice;
- distinguish temporary preview from permanent save/apply.

Validation:

- preview valid theme on hardware;
- restore previous state;
- keep previewed state;
- simulate failure and verify recovery;
- confirm no stale temporary files are left behind.

## Retirement stages

### Stage A — Documented fallback

Status target: current stage.

- Keep `Open Classic Editor` visible in the overflow menu.
- Add this checkpoint document.
- Do not remove the classic editor.
- Start implementing gates in small PRs.

### Stage B — Soft deprecation

After Gates 1–3 are validated:

- rename overflow action to `Open Classic Editor (legacy)`;
- add tooltip/copy explaining that the GTK editor is now primary;
- keep the action available.

### Stage C — Advanced fallback only

After Gates 4–5 are validated:

- move classic editor action under an advanced/troubleshooting section;
- keep it available for recovery and comparison;
- document the fallback path in the README or troubleshooting guide.

### Stage D — Disabled by default

After at least one release candidate:

- hide classic editor unless an advanced setting or environment flag is enabled;
- keep the file in the repository for one more cycle.

### Stage E — Removal candidate

Only after a stable release where the GTK editor is the validated default:

- remove classic editor launcher/action;
- archive any useful classic-only logic into pure helpers or docs before deletion;
- keep migration notes.

## Next implementation order

The next work should proceed in this order:

```text
1. Safe session lifecycle
2. Direct YAML/theme-folder access cleanup
3. BACKGROUND_IMAGE contextual workflow
4. Theme preview validation pipeline
5. Temporary preview on display
6. Soft deprecation copy for classic editor
```

## Branch plan

Recommended branch names:

```text
feature/theme-editor-safe-session-lifecycle
feature/theme-editor-yaml-access
feature/theme-background-image-workflow
feature/theme-display-preview-validation
feature/theme-preview-on-display
feature/theme-editor-classic-soft-deprecation
```

## Validation command set

For every implementation PR in this retirement track, run at minimum:

```bash
.venv/bin/python -m unittest discover -s tests -t . -v
.venv/bin/python -m py_compile theme-editor-gtk.py
git diff --check
git status --short
```

When UI is touched, also perform targeted GTK validation and restore generated preview files before committing.

## Non-goals

This checkpoint does not require:

- deleting `theme-editor.py` now;
- removing the classic editor action now;
- rewriting all theme internals at once;
- introducing the data-source wizard before preview safety;
- starting canvas direct manipulation before the classic editor safety gates.

## Decision

The GTK editor is now the primary development target. The classic editor remains a fallback until the gates above are implemented and validated.
