# Official Windows App Parity Roadmap

This roadmap records the implementation plan that came from comparing the official Windows Turing Smart Screen application with this Linux-focused GTK fork.

It is intentionally separate from the classic-editor retirement roadmap. The classic-editor work made the GTK Theme Editor the primary Linux editing surface. This roadmap tracks the next feature cycle: what we want to bring over from the official Windows app, what we already implemented, and what we intentionally want to do better than the official app.

## Context

The official Windows app was used as a workflow reference, not as something to copy blindly.

The goal is parity where the Windows app has useful user-facing workflows, while preserving the strengths of this fork:

- open `theme.yaml` model;
- Linux-first GTK/Libadwaita UX;
- non-destructive editing;
- Undo/Redo-friendly operations;
- guarded saves;
- external-change detection;
- atomic writes;
- local preview;
- semantic element tree;
- layer-order controls;
- generated-media tracking;
- diagnostic/reporting tools;
- safe device ownership and shutdown behavior.

## Decision summary

| Decision | Status |
| --- | --- |
| Use the official Windows app as a workflow reference | Accepted |
| Copy the Windows binary/architecture directly | Rejected |
| Preserve YAML-first, scriptable Linux workflow | Accepted |
| Prefer non-destructive media editing | Accepted |
| Keep original source assets whenever possible | Accepted |
| Keep local preview and generated-media diagnostics | Accepted |
| Implement official-style visual media workflows gradually | Accepted |
| Delay risky device-write parity until connection/discovery is explicit | Accepted |
| Avoid removing Linux safety guards for Windows-like convenience | Accepted |

## What the official app influenced

The Windows app strongly influenced these workflow targets:

1. Select media.
2. Adjust layout/fit/fill/alignment.
3. Transform image or video.
4. Preview the result.
5. Apply safely.
6. Send or use the prepared asset on the display.

In this fork, those ideas were translated into safer GTK-native slices instead of a direct clone.

## What we already implemented from that comparison

### Runtime / native video foundation

| Capability | Current status | Notes |
| --- | --- | --- |
| Native video command path | Implemented | The fork has a structured native-video flow instead of relying only on static image rendering. |
| Device-safe media operations | Implemented | The fork has safe device ownership and shutdown work from earlier runtime checkpoints. |
| SD/internal media listing | Implemented | Media listing and management were part of the native-video manager work. |
| Upload/playback/stop/delete style operations | Implemented | Covered through the native-video CLI/GTK manager direction. |
| ffprobe-based compatibility checks | Implemented | Better than guessing whether a file will work. |

### Media preparation editor

| Capability | Current status | Notes |
| --- | --- | --- |
| Select an image/media source | Implemented | Done through GTK media/layout/transform flows. |
| Fit/fill/original/stretch style layout | Implemented | Non-destructive static image layout inspector. |
| Alignment shortcuts | Implemented/partially implemented | Present through layout controls and alignment handling. |
| Preview before applying | Implemented | Local preview is a core design choice. |
| Apply without destroying the original | Implemented | Generated assets preserve source references. |
| Generated asset tracking | Implemented | Generated Media Manager and Theme Diagnostics now cover this. |

### Image transform workflow

| Capability | Current status | Notes |
| --- | --- | --- |
| Rotate image | Implemented | Added after the initial non-destructive layout MVP. |
| Mirror/flip image | Implemented | Implemented as part of the transform inspector direction. |
| Crop image | Implemented | Implemented with preview/apply semantics. |
| Preserve original image | Implemented | Source assets are not overwritten. |
| Track transformed output | Implemented | Managed generated media records output/source/settings. |

### Video Inspector V2

| Capability | Current status | Notes |
| --- | --- | --- |
| Select/resolve local video | Implemented | Video source resolution exists. |
| Mirror video | Implemented | Horizontal/vertical mirror controls. |
| Trim video | Implemented | Start/end trim controls. |
| Playback speed | Implemented | Inspector includes speed control. |
| Loop count | Implemented | Inspector includes loop control. |
| Background mode | Implemented | Inspector includes background mode controls. |
| Reactive/live preview hooks | Implemented | Preview reacts to inspector changes. |

### GTK editor and recovery features that are better than the official app

| Capability | Current status | Why it is better |
| --- | --- | --- |
| Open YAML directly | Implemented | Keeps power-user workflow available. |
| Guard before external YAML edits | Implemented | Prevents accidental GTK/YAML conflicts. |
| Detect external `theme.yaml` changes before saving | Implemented | Prevents overwriting outside edits. |
| Reload Theme From Disk | Implemented | Recovers from external edits without closing the editor. |
| Theme Diagnostics | Implemented | Produces a copyable support report. |
| Generated Media Manager | Implemented | Exposes in-use/unused/orphaned/unmanaged status. |
| Copy paths/open folder/open terminal | Implemented | Linux-native debugging workflow. |
| Classic editor fallback gate | Implemented | Keeps fallback available without promoting it as the main path. |

## What we decided not to copy directly

| Official-style behavior | Decision | Reason |
| --- | --- | --- |
| Binary/opaque project structure | Do not copy | This fork should remain open, YAML-based, and scriptable. |
| Destructive edits to original media | Do not copy | We prefer generated assets with source preservation. |
| Silent overwrite when file changed externally | Do not copy | GTK must keep external-change protection. |
| Device writes without explicit safe connection model | Defer | Risky until display detection/sync are explicitly modeled. |
| Windows-only UX conventions | Do not copy directly | Use GTK/Libadwaita patterns on Linux. |
| Hiding raw theme access | Do not copy | YAML access is a strength of this project. |
| Removing fallback before observation | Do not do yet | Classic editor remains advanced fallback for one more cycle. |

## Current parity matrix

| Official Windows app area | Linux/GTK status | Gap | Priority |
| --- | --- | --- | --- |
| Theme editing | Stronger in GTK now | Need final observation cycle only | Low |
| Image layout/editing | Mostly covered | Polish only if real themes expose issues | Low-medium |
| Image rotate/mirror/crop | Covered | Validate in normal use | Low |
| Video preparation/preview | Covered through Video Inspector V2 | More real-device testing later | Medium |
| Generated media management | Better in GTK | Optional UX polish | Low |
| Theme library/gallery | Not yet first-class | Need visual Theme Manager/Gallery | High |
| Import/export themes | Partial/manual | Need explicit import/export UX | High |
| Device detection/selection | Earlier roadmap exists, not finalized here | Need safe display profile/device manager | High |
| Send/sync to display | Partially covered by native-video/media flows | Need unified sync UX | High |
| Sensor/data source configuration | Not yet official-style | Need data source model and UI | Medium-high |
| WYSIWYG canvas editing | Partial through inspectors/tree | Need direct manipulation canvas later | Medium |
| Packaging/release | Linux-focused work exists | Need release polish after feature parity | Medium |

## Next implementation cycle

### Phase 1 — Theme Gallery / Theme Manager

This should be the next major implementation area because it mirrors the official app's user-facing starting point while staying low-risk compared with device sync.

Target features:

- visual list/grid of themes;
- preview thumbnail for each theme;
- theme name and folder display;
- active/current theme marker;
- open in GTK Theme Editor;
- duplicate theme;
- rename theme;
- delete theme with confirmation;
- import theme folder/archive;
- export selected theme;
- open theme folder;
- run Theme Diagnostics from the gallery;
- show broken/missing-preview themes clearly.

Recommended first slice:

```text
Theme Gallery MVP
```

Acceptance criteria:

- opens independently from the editor;
- lists themes from `res/themes`;
- shows preview when available;
- opens a selected theme in `theme-editor-gtk.py`;
- does not modify themes yet except through explicit open/edit actions.

### Phase 2 — Theme import/export

After the gallery exists, implement controlled movement of themes.

Target features:

- import from folder;
- import from archive if safe;
- validate expected theme files;
- avoid overwriting existing themes without confirmation;
- export selected theme as folder/archive;
- include generated media when exporting;
- warn about missing assets before export.

Acceptance criteria:

- import never overwrites silently;
- export preserves `theme.yaml` and referenced assets;
- diagnostics can be run before/after import/export.

### Phase 3 — Device Manager / Display profiles

This phase should build on earlier display-profile and detection work, but only after the gallery/import/export flow is stable.

Target features:

- detect connected display;
- show display model/revision/profile;
- show resolution/orientation/capabilities;
- select target display/profile;
- test connection;
- show connection diagnostics;
- avoid conflicting ownership of the device;
- safe disconnect/shutdown behavior.

Acceptance criteria:

- no unsafe writes during detection;
- user can see exactly what display/profile is active;
- errors explain what failed and how to retry.

### Phase 4 — Unified sync/send-to-display flow

This is where the Linux app becomes closer to the official Windows app's end-to-end flow.

Target features:

- prepare theme assets;
- validate media compatibility;
- sync theme/media to device;
- show progress;
- handle cancellation safely;
- report skipped/failed files;
- optionally reload/restart display content.

Acceptance criteria:

- sync is explicit, not automatic;
- failures are recoverable;
- no partial operation is presented as success;
- native video/media operations remain safe.

### Phase 5 — Sensor/data source configuration

The official app is centered around hardware/system metrics. The Linux fork needs an explicit data-source model instead of ad hoc UI fields.

Target features:

- CPU data source settings;
- GPU data source settings;
- memory/storage/network settings;
- temperature/fan sources where available;
- source availability diagnostics;
- preview sample values;
- fallback behavior when a sensor is unavailable.

Acceptance criteria:

- missing sensors are clearly reported;
- theme editor knows whether a widget's source is valid;
- diagnostics include source availability.

### Phase 6 — Visual canvas editing

This should come after the safer manager/device/sync foundation.

Target features:

- direct element selection on preview canvas;
- drag to move;
- resize handles;
- snap/alignment guides;
- layer selection from canvas;
- keyboard nudging;
- safe undo/redo for canvas operations.

Acceptance criteria:

- canvas operations use the same guarded save/history model;
- no direct manipulation bypasses `theme.yaml` safety;
- tree selection and canvas selection stay synchronized.

## Features where our app should remain better than official

These are not just parity items; they are advantages to preserve:

- YAML-first editing and version control friendliness.
- Guarded external editor workflow.
- Reload from disk.
- Atomic save behavior.
- Generated-media inventory and safe deletion policy.
- Theme Diagnostics with copyable support report.
- Linux terminal/file-manager integration.
- Explicit fallback gate for legacy/classic editor.
- Clear separation between editing, diagnostics, and device sync.

## Recommended next PRs

1. `docs/THEME_GALLERY_MVP_PLAN.md`
2. Theme Gallery MVP implementation.
3. Theme import/export plan.
4. Theme import/export implementation.
5. Device Manager/display-profile integration checkpoint.
6. Unified sync/send-to-display plan.

## Current decision

The next major implementation should be **Theme Gallery / Theme Manager MVP**.

Reason: it is the most useful official-app-inspired feature that does not require risky device-write work yet. It gives the Linux app a more complete official-style entry point while reusing the now-stable GTK Theme Editor.
