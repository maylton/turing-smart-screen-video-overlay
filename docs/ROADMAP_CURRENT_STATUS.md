# Current Roadmap Status

This checkpoint summarizes the current project state after the Theme Gallery app-shell stack was merged into `feature/theme-video-inspector-live-preview`.

It is meant to be the quick operational roadmap: what is done, what is current, and what should come next. Longer design context remains in:

- `docs/ROADMAP.md`
- `docs/ROADMAP_THEME_EDITOR_DETAILED.md`
- `docs/OFFICIAL_WINDOWS_PARITY_ROADMAP.md`
- `docs/THEME_APP_SHELL_MVP.md`
- `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`

## Ground rules

Continue using the established roadmap guardrails:

- one small feature branch per implementation step;
- pure/testable helper modules outside GTK when possible;
- no unrelated theme/config/generated-file drift;
- preserve Undo/Redo and atomic-save behavior;
- keep device-write flows explicit and guarded;
- do not bypass the YAML-first architecture.

## Current base

```text
base branch: feature/theme-video-inspector-live-preview
latest merged stack: Theme Gallery app shell stack + post-merge docs cleanup
normal launcher: turing-smart-screen
integrated dev launcher: .venv/bin/python turing-smart-screen-main.py
legacy/runtime launcher: .venv/bin/python configure-gtk.py
```

## Completed checkpoints

### Runtime, packaging, and media foundation

- [x] Runtime and native-video foundation.
- [x] Installation and documentation readiness.
- [x] Media preparation editor MVP.
- [x] Advanced media preparation.
- [x] Multiple display profiles.
- [x] Automatic display detection.
- [x] Release-readiness foundation.

### Theme editor and media tooling

- [x] Theme elements navigator.
- [x] Layer ordering foundation.
- [x] Theme property presets.
- [x] Theme text and effect presets.
- [x] Semantic visual preset engine foundation.
- [x] Component preset foundation.
- [x] Composition preset foundation.
- [x] Static image layout inspector.
- [x] Static image transform inspector.
- [x] Static image crop inspector.
- [x] Generated Media Manager.
- [x] Video Inspector V1 with reactive playback preview.
- [x] Theme editor text/effect hardening.
- [x] True transparent native-video overlays.
- [x] Text effects over native-video themes.
- [x] Reliable Save As/theme cloning fixes.

### Integrated app shell / official-app parity cycle

- [x] Theme Gallery reusable module.
- [x] Theme Gallery integrated into the main app `Themes` page.
- [x] Current-theme detection and compatibility filtering.
- [x] Gallery diagnostics.
- [x] Set active/current theme from gallery.
- [x] Duplicate, rename, delete with confirmation.
- [x] Import from folder/archive.
- [x] Export selected theme to `.zip` archive.
- [x] Theme card action polish with overflow menu.
- [x] Embedded Theme Editor inside the main app stack.
- [x] Embedded Video Manager inside the main app stack.
- [x] Overview and Quick Actions route into embedded editor/video manager.
- [x] Rev. C offscreen bitmap clipping guard.
- [x] Overview animated preview for video themes.
- [x] Overview preview renderer aligned with Theme Editor/runtime `DisplayText` behavior.
- [x] Overview mock values aligned with the Theme Editor `HW_SENSORS=STATIC` preview basis.
- [x] Post-merge documentation cleanup.

## Current gap

The next useful gap is not another large UI shell change. The integrated shell is now stable enough to resume smaller feature work.

The current exported theme `.zip` flow exists, but it still needs a stronger preflight layer for referenced/generated media.

## Next implementation — Phase 22B: Export completeness preflight

### Goal

Before exporting a theme, inspect `theme.yaml` plus generated-media metadata and report whether the export will be complete.

### Suggested branch

```text
feature/theme-export-preflight
```

### Target behavior

- [ ] Scan the selected theme before export.
- [ ] Collect referenced assets from theme YAML:
  - images;
  - backgrounds;
  - fonts when theme-local;
  - video preview backgrounds;
  - local video references where applicable;
  - generated-media outputs.
- [ ] Cross-check `generated-media/transform-manifest.json` when present.
- [ ] Classify referenced assets:
  - present and included;
  - missing;
  - outside theme folder;
  - generated and managed;
  - generated but missing manifest metadata;
  - referenced from manifest but not used by theme.
- [ ] Produce a structured preflight report.
- [ ] Show warnings before export when assets may be missing from the archive.
- [ ] Keep export explicit and non-destructive.
- [ ] Never delete or mutate theme files during export preflight.

### Recommended implementation shape

Add pure logic first:

```text
library/theme_export_preflight.py
tests/test_theme_export_preflight.py
```

Then integrate into the existing gallery export action only after the pure preflight is covered by tests.

### Non-goals for Phase 22B

- [ ] No automatic asset repair.
- [ ] No device sync.
- [ ] No upload/send-to-display.
- [ ] No broad Theme Gallery refactor.
- [ ] No changes to Overview preview rendering.
- [ ] No deletion or cleanup of generated media.

### Validation

```bash
.venv/bin/python -m py_compile library/theme_export_preflight.py
.venv/bin/python -m py_compile library/theme_gallery.py
.venv/bin/python -m unittest tests.test_theme_export_preflight -v
.venv/bin/python -m unittest discover -s tests -t . -v
git diff --check
git status --short
```

Manual validation after GTK integration:

1. Export a complete theme and confirm no warnings appear.
2. Export a theme with a missing referenced asset and confirm a warning appears before export.
3. Export a theme with generated-media assets and confirm managed outputs are detected.
4. Confirm export still refuses to overwrite existing archives.
5. Confirm no `theme.yaml`, manifest, or generated asset is modified by preflight.

## Later roadmap

After export preflight/completeness:

1. Embedded media-preparation workflow polish.
2. Device Manager / display-profile integration.
3. Unified sync/send-to-display plan.
4. Safe temporary preview-on-display flow.
5. Data source and visualization catalogs.
6. Data element creation wizard.
7. Canvas interaction model.
8. Canvas direct selection/drag.
9. Canvas resize/actions.

## Current decision

Resume with **Phase 22B: Export completeness preflight**.

Reason: the app shell and gallery are now integrated, import/export already exist, and export completeness is the next safest official-app-parity step before any risky device sync or display-write workflow.
