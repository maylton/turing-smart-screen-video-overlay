# Theme Gallery MVP

This document describes the first implementation slice from `docs/OFFICIAL_WINDOWS_PARITY_ROADMAP.md` and the architecture checkpoint in `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`.

The Theme Gallery is the future Linux/GTK home surface inspired by the official Windows app's theme-selection workflow. It does not replace the GTK Theme Editor; it opens themes into it.

## Architecture role

This slice provides two pieces:

- `library/theme_gallery.py` — reusable discovery/model/UI components for the app shell;
- `theme-gallery-gtk.py` — temporary developer entry point for testing the gallery independently.

The temporary standalone script is not the final product architecture. The normal user-facing direction is `turing-smart-screen-gtk.py`, which embeds `ThemeGalleryPane` as the app home surface.

## Scope

The MVP is intentionally read-only for theme management.

Included:

- reusable theme discovery from `res/themes`;
- current-theme detection from `config.yaml`;
- visual card grid component;
- preview thumbnail when `preview.png` exists;
- missing-preview placeholder;
- broken-theme indicator when `theme.yaml`/`theme.yml` is missing;
- `Open Current` action in the developer window and app shell;
- per-theme `Edit` action;
- per-theme folder-open action;
- refresh action.

Not included yet:

- duplicate theme;
- rename theme;
- delete theme;
- import/export theme;
- device sync/send-to-display.

Those actions are intentionally deferred because the first slice should only introduce the official-style theme-browsing surface without adding new destructive management flows.

## Entry points

Normal app-shell entry point:

```bash
.venv/bin/python turing-smart-screen-gtk.py
```

Temporary developer gallery entry point:

```bash
.venv/bin/python theme-gallery-gtk.py
```

## Acceptance criteria

The MVP is accepted when:

- the reusable gallery module imports successfully;
- the app shell opens and embeds the gallery;
- the developer gallery still opens independently;
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
.venv/bin/python -m py_compile turing-smart-screen-gtk.py
.venv/bin/python -m py_compile theme-editor-gtk.py
.venv/bin/python -m unittest discover -s tests -t . -v
git diff --check
```

Manual validation later in the stack:

1. Launch the app shell.
2. Confirm the shell opens with a sidebar.
3. Confirm the Theme Gallery cards are displayed inside the shell.
4. Confirm the current theme badge appears on the theme from `config.yaml`.
5. Confirm previews load where `preview.png` exists.
6. Confirm missing previews show a placeholder.
7. Click `Edit` on a normal theme and confirm the GTK Theme Editor opens.
8. Click `Open Current` and confirm the current theme opens.
9. Click the folder button and confirm the file manager opens the theme folder.
10. Click refresh and confirm the list reloads.
11. Confirm `git status --short` shows no theme changes caused by browsing.

## Stack position

Completed in this branch so far:

1. Reusable Theme Gallery module.
2. Main app shell that embeds the gallery.

Follow-up stack:

1. Gallery search/filter.
2. Gallery diagnostics action.
3. Set active/current theme from the gallery.
4. Duplicate/import/export/rename/delete in later management slices.
5. Device Manager / display-profile integration.
