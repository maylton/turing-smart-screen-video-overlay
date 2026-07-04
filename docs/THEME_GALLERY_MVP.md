# Theme Gallery MVP

This document describes the first implementation slice from `docs/OFFICIAL_WINDOWS_PARITY_ROADMAP.md` and the architecture checkpoint in `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`.

The Theme Gallery is the future Linux/GTK home surface inspired by the official Windows app's theme-selection workflow. It does not replace the GTK Theme Editor; it opens themes into it.

## Architecture role

This slice now provides two pieces:

- `library/theme_gallery.py` — reusable discovery/model/UI components for the future app shell;
- `theme-gallery-gtk.py` — temporary developer entry point for testing the gallery independently.

The temporary standalone script is not the final product architecture. Future slices should embed `ThemeGalleryPane` into one main app shell instead of creating a new app for every feature.

## Scope

The MVP is intentionally read-only for theme management.

Included:

- reusable theme discovery from `res/themes`;
- current-theme detection from `config.yaml`;
- visual card grid component;
- preview thumbnail when `preview.png` exists;
- missing-preview placeholder;
- broken-theme indicator when `theme.yaml`/`theme.yml` is missing;
- `Open Current` action in the developer window;
- per-theme `Edit` action;
- per-theme folder-open action;
- refresh action.

Not included yet:

- main app shell;
- duplicate theme;
- rename theme;
- delete theme;
- import/export theme;
- set active/current theme from gallery;
- diagnostics action from gallery;
- device sync/send-to-display.

Those actions are intentionally deferred because the first slice should only introduce the official-style theme-browsing surface without adding new destructive or write-capable management flows.

## Developer entry point

```bash
.venv/bin/python theme-gallery-gtk.py
```

## Acceptance criteria

The MVP is accepted when:

- the reusable gallery module imports successfully;
- the developer gallery opens independently;
- themes from `res/themes` are listed;
- the theme configured in `config.yaml` is marked as current;
- cards show `preview.png` when available;
- cards show a clear placeholder when no preview exists;
- broken theme folders are visible but cannot be opened in the editor;
- clicking `Edit` opens the selected theme in `theme-editor-gtk.py`;
- clicking `Open Current` opens the current theme;
- clicking the folder button opens the theme folder;
- clicking refresh reloads the list;
- no theme files are modified by simply opening or browsing the gallery.

## Validation

```bash
.venv/bin/python -m py_compile library/theme_gallery.py
.venv/bin/python -m py_compile theme-gallery-gtk.py
.venv/bin/python -m py_compile theme-editor-gtk.py
.venv/bin/python -m unittest discover -s tests -t . -v
git diff --check
```

Manual validation:

1. Launch the gallery.
2. Confirm cards are displayed.
3. Confirm the current theme badge appears on the theme from `config.yaml`.
4. Confirm previews load where `preview.png` exists.
5. Confirm missing previews show a placeholder.
6. Click `Edit` on a normal theme and confirm the GTK Theme Editor opens.
7. Click `Open Current` and confirm the current theme opens.
8. Click the folder button and confirm the file manager opens the theme folder.
9. Click refresh and confirm the list reloads.
10. Confirm `git status --short` shows no theme changes caused by browsing.

## Stack position

This is stack phase 1.

Recommended follow-up order:

1. App shell that embeds the gallery.
2. Gallery search/filter.
3. Gallery diagnostics action.
4. Set active/current theme from the gallery.
5. Duplicate/import/export/rename/delete in later management slices.
6. Device Manager / display-profile integration.
