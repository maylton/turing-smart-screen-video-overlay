# Theme App Architecture Checkpoint

This checkpoint corrects the direction before the Theme Gallery MVP is merged.

The project should evolve toward one cohesive Linux/GTK application shell, not a collection of separate standalone apps for every new feature.

## Problem identified

The initial Theme Gallery MVP branch introduced a new standalone entry point:

```bash
.venv/bin/python theme-gallery-gtk.py
```

That is useful as a technical prototype, but it should not become the long-term architecture pattern.

If every major feature becomes a separate script/window/app, the project will drift into this shape:

```text
theme-editor-gtk.py
theme-gallery-gtk.py
video-manager.py
device-manager.py
settings-app.py
...
```

That would make the user experience fragmented and would make future packaging harder.

## Target architecture

The desired architecture is one main GTK/Libadwaita app shell with feature surfaces inside it:

```text
Main app shell
├─ Theme Gallery / Theme Manager
├─ Theme Editor
├─ Generated Media Manager
├─ Video Inspector
├─ Device Manager
├─ Settings
└─ Diagnostics
```

## Product decision

The Theme Gallery should become the future home/start surface of the application.

The GTK Theme Editor should remain the main editing surface, but it should be opened from the Theme Gallery or app shell instead of being the only normal entry point.

The current standalone editor script may remain as a developer/debug entry point during the transition, but the user-facing architecture should converge toward a single app.

## Entry point policy

| Entry point | Long-term role | Decision |
| --- | --- | --- |
| Main app shell | User-facing launcher | Required |
| Theme Gallery | Home / Theme Manager surface | Required |
| GTK Theme Editor | Editing surface inside/opened by shell | Required |
| Generated Media Manager | Tool/dialog inside editor or shell | Required |
| Video Inspector | Tool/dialog inside editor | Required |
| Device Manager | Shell surface/dialog | Future required |
| Classic editor | Advanced fallback only | Temporary |
| Standalone scripts | Developer/debug compatibility | Allowed during transition |

## Rules for new features

New major features should follow these rules:

1. Do not create a new user-facing app unless there is an explicit architecture decision.
2. Prefer a reusable module plus an app-shell surface.
3. Prefer dialogs/pages/tools inside the main shell or editor.
4. Keep standalone scripts only as temporary developer/debug entry points.
5. Keep the app packageable as one coherent application.
6. Do not bypass existing safe save/reload/diagnostics behavior.

## How to handle PR #46

PR #46 should remain draft-only until it is refactored.

Treat the current gallery code as a prototype for:

- theme discovery;
- current-theme detection;
- theme cards;
- preview thumbnails;
- broken-theme state;
- opening a theme in the GTK editor;
- opening a theme folder.

Before merging it, choose one of these paths:

### Option A — Promote the gallery into the main app shell

Create a new primary launcher, for example:

```bash
.venv/bin/python turing-smart-screen-gtk.py
```

The launcher opens the Theme Gallery as the home surface and opens the Theme Editor from there.

This is the preferred long-term direction.

### Option B — Integrate the gallery into an existing launcher

If the repository already has a better app entry point, integrate the gallery into that instead of creating a new shell.

### Option C — Extract reusable gallery logic first

Move discovery/card logic into a reusable module, then add the UI surface inside the chosen shell later.

This is acceptable if the app-shell decision needs more code inspection.

## Recommended next implementation plan

1. Keep PR #46 as draft.
2. Create an app-shell plan before merging gallery code.
3. Refactor gallery code into the selected architecture.
4. Keep `theme-editor-gtk.py` as a direct developer entry point for now.
5. Make the app shell the normal user-facing launcher later.

## Proposed final structure

Short term:

```text
theme-editor-gtk.py              # direct editor/dev entry point
theme-gallery-gtk.py             # draft prototype only, not final pattern
library/theme_gallery.py         # future reusable theme discovery/model code
```

Medium term:

```text
turing-smart-screen-gtk.py       # main app shell
library/theme_gallery.py         # theme discovery/model helpers
library/theme_app_shell.py       # shell navigation helpers, if needed
theme-editor-gtk.py              # still runnable directly for debugging
```

Long term:

```text
turing-smart-screen-gtk.py       # normal app launcher
Theme Gallery                    # home surface
Theme Editor                     # editing surface
Tools / Dialogs                  # media, video, diagnostics, device manager
Classic Editor                   # removed or hidden fallback only
```

## Decision

Do not merge standalone Theme Gallery as the final architecture.

Use it as a prototype, then refactor toward a single cohesive app shell.
