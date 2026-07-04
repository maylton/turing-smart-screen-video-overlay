# Theme App Architecture Checkpoint

This checkpoint records the architecture decision for the Theme Gallery / Theme Manager stack after PR #46 was promoted from prototype work into the integrated main app.

The project should evolve toward one cohesive Linux/GTK application shell, not a collection of separate standalone apps for every new feature.

## Problem identified

The initial Theme Gallery MVP branch introduced a new standalone entry point:

```bash
.venv/bin/python theme-gallery-gtk.py
```

That was useful as a technical prototype, but it should not become the long-term architecture pattern.

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

## Architecture decision

The accepted direction is one main GTK/Libadwaita app shell with feature surfaces inside it:

```text
Main app shell
├─ Overview
├─ Theme Gallery / Theme Manager
├─ Embedded Theme Editor
├─ Embedded Video Manager
├─ Generated Media / Video tools
├─ Device Manager
├─ Settings
└─ Diagnostics
```

The standalone scripts remain useful as fallback/developer entry points, but normal user-facing actions should route through the integrated app shell.

## Post-merge status

PR #46 was merged with the integrated architecture instead of shipping the original standalone-gallery prototype as the final direction.

The merged stack now includes:

- Theme Gallery integrated into the existing main app `Themes` page;
- embedded Theme Editor route from Theme Gallery, Overview, and Quick Actions;
- embedded Video Manager route from Overview Quick Actions and Tools;
- Overview animated preview for video themes;
- preview renderer behavior aligned with the Theme Editor/runtime text rendering path;
- static Overview preview data aligned with the Theme Editor `HW_SENSORS=STATIC` basis.

## Current entry point policy

| Entry point | Long-term role | Decision |
| --- | --- | --- |
| `turing-smart-screen` | Normal installed app launcher | Required |
| `turing-smart-screen-main.py` | Integrated launcher wrapper | Required |
| `configure-gtk.py` | Existing app foundation / legacy runtime launcher | Required during transition |
| `library/theme_gallery.py` | Reusable Theme Gallery surface/model | Required |
| Embedded Theme Editor | Editing surface inside the app shell | Required |
| Embedded Video Manager | Video-management surface inside the app shell | Required |
| `theme-editor-gtk.py` | Standalone fallback/dev editor | Allowed |
| `video-manager-gtk.py` | Standalone fallback/dev video manager | Allowed |
| `theme-gallery-gtk.py` | Isolated gallery developer harness | Temporary/dev only |
| `turing-smart-screen-gtk.py` | Earlier standalone app-shell prototype | Temporary/dev only |

## Rules for new features

New major features should follow these rules:

1. Do not create a new user-facing app unless there is an explicit architecture decision.
2. Prefer a reusable module plus an app-shell surface.
3. Prefer dialogs/pages/tools inside the main shell or editor.
4. Keep standalone scripts only as fallback/developer/debug entry points.
5. Keep the app packageable as one coherent application.
6. Do not bypass existing safe save/reload/diagnostics behavior.

## Current structure

```text
turing-smart-screen                         # normal installed app command
└─ turing-smart-screen-main.py              # integrated launcher wrapper
   └─ configure-gtk.py runtime patches      # existing app foundation
      ├─ Overview                           # active theme preview surface
      ├─ Themes page                        # reusable ThemeGalleryPane
      ├─ Embedded Theme Editor page         # hosted editor surface
      ├─ Embedded Video Manager page        # hosted video-manager surface
      └─ Tools / Quick Actions              # routes into embedded surfaces
```

Standalone fallback/dev entry points remain available:

```bash
.venv/bin/python theme-editor-gtk.py
.venv/bin/python video-manager-gtk.py
.venv/bin/python theme-gallery-gtk.py
.venv/bin/python turing-smart-screen-gtk.py
```

## Follow-up direction

The next work should continue from the integrated shell, not from new standalone app surfaces.

Recommended follow-ups:

1. Post-merge documentation and validation cleanup.
2. Export completeness: referenced/generated media preflight and missing-asset warnings.
3. Embedded media-preparation workflow.
4. Device Manager / display-profile integration.
5. Gradual retirement or hiding of standalone prototype entry points once the integrated app is stable.
