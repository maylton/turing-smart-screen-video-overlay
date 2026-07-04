# Theme Gallery MVP

This document describes the first implementation slice from `docs/OFFICIAL_WINDOWS_PARITY_ROADMAP.md` and the architecture checkpoint in `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`.

The Theme Gallery is the future Linux/GTK home surface inspired by the official Windows app's theme-selection workflow. It does not replace the GTK Theme Editor; it opens themes into it.

## Architecture role

This slice provides two pieces:

- `library/theme_gallery.py` — reusable discovery/model/UI components for the app shell;
- `theme-gallery-gtk.py` — temporary developer entry point for testing the gallery independently.

The temporary standalone script is not the final product architecture. The normal user-facing direction is `turing-smart-screen-gtk.py`, which embeds `ThemeGalleryPane` as the app home surface.

## Scope

The MVP is now a mostly read-oriented theme management surface, with one guarded write action for selecting the current theme.

Included:

- reusable theme discovery from `res/themes`;
- current-theme detection from `config.yaml`;
- visual card grid component;
- preview thumbnail when `preview.png` exists;
- missing-preview placeholder;
- broken-theme indicator when `theme.yaml`/`theme.yml` is missing;
- search/filter by name, path, YAML filename, or status;
- result count for filtered searches;
- filtered empty state when no theme matches;
- per-theme gallery diagnostics action;
- copyable gallery-level diagnostics report;
- guarded `Use` action for setting a valid theme as current;
- atomic update of `config.yaml` `THEME` value;
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

Those actions are intentionally deferred because this stack should introduce the official-style theme-browsing surface without adding destructive management flows.

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
- search filters themes by name/path/status/YAML filename;
- unmatched search shows a filtered empty state;
- clearing search restores the full theme list;
- diagnostics opens a read-only report for a selected theme;
- Copy Report copies the diagnostics report;
- `Use` is shown only for non-current themes;
- `Use` is disabled for broken themes;
- confirming `Use Theme` updates `config.yaml` and refreshes the current badge;
- clicking `Edit` opens the selected theme in `theme-editor-gtk.py`;
- clicking `Open Current` opens the current theme;
- clicking the folder button opens the theme folder;
- clicking refresh reloads the list;
- only the explicit `Use Theme` action modifies `config.yaml`.

## Validation

```bash
.venv/bin/python -m py_compile library/theme_gallery.py
.venv/bin/python -m py_compile theme-gallery-gtk.py
.venv/bin/python -m py_compile turing-smart-screen-gtk.py
.venv/bin/python -m py_compile theme-editor-gtk.py
.venv/bin/python -m unittest discover -s tests -t . -v
git diff --check
```

Manual validation:

1. Launch the app shell.
2. Confirm the shell opens with a sidebar.
3. Confirm the Theme Gallery cards are displayed inside the shell.
4. Confirm the current theme badge appears on the theme from `config.yaml`.
5. Confirm previews load where `preview.png` exists.
6. Confirm missing previews show a placeholder.
7. Search by theme name and confirm only matching cards remain.
8. Search by status/path/YAML filename and confirm matching cards remain.
9. Search for a non-existing term and confirm the filtered empty state appears.
10. Clear search and confirm all themes return.
11. Open diagnostics for a theme and confirm the report appears.
12. Click Copy Report and confirm the clipboard contains the report.
13. Click `Use` on a non-current valid theme and confirm the dialog appears.
14. Confirm `Use Theme` updates the badge and `config.yaml` `THEME` value.
15. Confirm broken themes cannot be set as current.
16. Click `Edit` on a normal theme and confirm the GTK Theme Editor opens.
17. Click `Open Current` and confirm the current theme opens.
18. Click the folder button and confirm the file manager opens the theme folder.
19. Click refresh and confirm the list reloads.
20. Restore test config changes before final merge if needed: `git restore config.yaml`.

## Stack position

Completed in this branch so far:

1. Reusable Theme Gallery module.
2. Main app shell that embeds the gallery.
3. Gallery search/filter.
4. Gallery diagnostics action.
5. Set active/current theme from the gallery.

Follow-up stack:

1. Integrated local validation.
2. Duplicate/import/export/rename/delete in later management slices.
3. Device Manager / display-profile integration.
