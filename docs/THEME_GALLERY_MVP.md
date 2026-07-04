# Theme Gallery MVP

This document describes the first implementation slice from `docs/OFFICIAL_WINDOWS_PARITY_ROADMAP.md` and the architecture checkpoint in `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`.

The Theme Gallery is the new Linux/GTK theme-management surface inspired by the official Windows app's theme-selection workflow. It does not replace the GTK Theme Editor; it opens themes into it.

## Architecture role

This slice provides three pieces:

- `library/theme_gallery.py` — reusable discovery/model/UI components;
- main-app integration — the existing `configure-gtk.py` / `turing-smart-screen` `Themes` page uses the gallery surface;
- `theme-gallery-gtk.py` / `turing-smart-screen-gtk.py` — temporary developer/prototype entry points for isolated testing.

The temporary standalone scripts are not the final product architecture. The normal user-facing direction is the existing installed GTK configuration app, launched by `turing-smart-screen`.

## Installed-app guard

Older local checkouts may contain an untracked `configure-gtk-final.py`. The installer previously preferred that file over the branch's `configure-gtk.py`, which could make a fresh install still open the old `Themes` page.

This stack removes that override. Installed validation should check that the installed launcher file contains the gallery integration:

```bash
grep -n "ThemeGalleryPane" ~/.local/share/turing-smart-screen/configure-gtk.py
```

## Scope

The MVP is now a theme-management surface with guarded write actions for selecting, duplicating, renaming, deleting, and importing themes.

Included:

- reusable theme discovery from `res/themes`;
- current-theme detection from `config.yaml`;
- detected/configured display-size detection from `config.yaml` (`DISPLAY_SIZE`, `SCREEN_SIZE`, or `SIZE`), falling back to the current theme metadata;
- compatibility filtering so the gallery only shows themes whose `DISPLAY_SIZE` matches the detected/configured display size;
- visual card grid component;
- integration into the existing main app `Themes` page;
- retained `Create blank` action from the old main-app Themes page;
- preview thumbnail when `preview.png` exists;
- missing-preview placeholder;
- search/filter by name, path, YAML filename, display size, or status;
- result count for filtered searches;
- filtered empty state when no compatible theme matches;
- per-theme gallery diagnostics action;
- copyable gallery-level diagnostics report with target/theme display sizes;
- guarded `Use` action for setting a valid compatible theme as current;
- atomic update of `config.yaml` `THEME` value;
- non-destructive per-theme duplicate action;
- safe non-conflicting folder-name suggestion for duplicates;
- rename action with name sanitization and overwrite protection;
- renaming the current theme updates `config.yaml` automatically;
- guarded delete action that requires typing the exact theme name;
- delete moves the theme folder to Trash and refuses to delete the current theme;
- import from a theme folder or `.zip` archive;
- import validates `theme.yaml`/`theme.yml`, rejects unsafe archive paths, and never overwrites existing themes;
- robust theme folder opening using GTK/GIO first, `gio open`/`xdg-open` with captured errors, then direct file-manager fallbacks;
- per-theme `Edit` action;
- refresh action.

Not included yet:

- export theme;
- device sync/send-to-display.

Those actions are intentionally deferred because this stack should introduce the official-style theme-browsing surface without adding risky device-write flows.

## Entry points

Normal installed app entry point:

```bash
turing-smart-screen
```

Development checkout entry point for the same main app:

```bash
.venv/bin/python configure-gtk.py
```

Temporary developer gallery entry point:

```bash
.venv/bin/python theme-gallery-gtk.py
```

## Acceptance criteria

The MVP is accepted when:

- the reusable gallery module imports successfully;
- the existing main app opens and embeds the gallery on the `Themes` page;
- the installed `configure-gtk.py` contains the `ThemeGalleryPane` integration;
- the old split list/preview `Themes` page is replaced by gallery cards;
- the developer gallery still opens independently;
- only themes compatible with the detected/configured display size are listed;
- the result counter shows the compatible-theme count and target display size when available;
- incompatible themes are hidden from the card grid;
- the theme configured in `config.yaml` is marked as current when it is compatible;
- cards show `preview.png` when available;
- cards show a clear placeholder when no preview exists;
- search filters compatible themes by name/path/status/YAML filename/display size;
- unmatched search shows a filtered empty state;
- clearing search restores the compatible theme list;
- diagnostics opens a read-only report for a selected theme;
- Copy Report copies the diagnostics report;
- `Use` is shown only for non-current compatible themes;
- confirming `Use Theme` updates `config.yaml` and refreshes the current badge;
- duplicate creates a non-destructive copy with a safe non-conflicting folder name;
- duplicate does not change `config.yaml` automatically;
- rename changes the theme folder name and refuses overwrites;
- renaming the current theme updates `config.yaml` automatically;
- delete is not available for the current theme;
- deleting a non-current theme requires typing the exact theme name;
- confirmed delete moves the theme folder to Trash and refreshes the gallery;
- import accepts a folder containing `theme.yaml`/`theme.yml` or a safe `.zip` archive;
- import never overwrites an existing theme;
- clicking `Edit` opens the selected theme in `theme-editor-gtk.py`;
- clicking the folder button opens the theme folder or shows a useful error dialog;
- clicking refresh reloads the list;
- only explicit `Use Theme`, `Duplicate`, `Rename`, confirmed `Delete`, or `Import` actions write files.

## Validation

```bash
.venv/bin/python -m py_compile library/theme_gallery.py
.venv/bin/python -m py_compile theme-gallery-gtk.py
.venv/bin/python -m py_compile turing-smart-screen-gtk.py
.venv/bin/python -m py_compile configure-gtk.py
.venv/bin/python -m py_compile configure_gtk_app.py
.venv/bin/python -m py_compile theme-editor-gtk.py
.venv/bin/python -m unittest discover -s tests -t . -v
git diff --check
```

Manual validation:

1. Launch the existing main app with `.venv/bin/python configure-gtk.py`.
2. Open the sidebar `Themes` page.
3. Confirm the Theme Gallery cards are displayed in the main app.
4. Confirm the counter shows only compatible themes, such as `compatible themes · 2.1"`.
5. Confirm themes with a different `DISPLAY_SIZE` are not shown.
6. Confirm the current theme badge appears on the theme from `config.yaml` when compatible.
7. Confirm previews load where `preview.png` exists.
8. Confirm missing previews show a placeholder.
9. Search by theme name and confirm only matching compatible cards remain.
10. Search by status/path/YAML filename/display size and confirm matching compatible cards remain.
11. Search for a non-existing term and confirm the filtered empty state appears.
12. Clear search and confirm the compatible theme list returns.
13. Open diagnostics for a theme and confirm the report includes target/theme display sizes.
14. Click Copy Report and confirm the clipboard contains the report.
15. Click `Use` on a non-current compatible theme and confirm the dialog appears.
16. Confirm `Use Theme` updates the badge and `config.yaml` `THEME` value.
17. Click duplicate on a valid theme and confirm the dialog suggests a safe copy name.
18. Confirm duplicating creates a new compatible card after refresh without changing `config.yaml`.
19. Click rename on a duplicated theme and confirm the folder/card name changes.
20. Rename the current theme and confirm `config.yaml` updates to the new name.
21. Click delete on the duplicated theme, type the exact name, and confirm it moves to Trash.
22. Confirm the current theme does not show a delete button.
23. Click Import, paste a valid theme folder or `.zip` path, and confirm it appears without overwriting existing themes.
24. Click `Edit` on a normal theme and confirm the GTK Theme Editor opens.
25. Click the folder button and confirm the file manager opens the theme folder.
26. Click refresh and confirm the list reloads.
27. Restore test config/theme changes before final merge if needed.

## Stack position

Completed in this branch so far:

1. Reusable Theme Gallery module.
2. Temporary app shell prototype.
3. Gallery search/filter.
4. Gallery diagnostics action.
5. Set active/current theme from the gallery.
6. Duplicate theme.
7. Rename theme.
8. Delete theme with confirmation.
9. Import theme from folder/archive.
10. Integrate gallery into the existing main app `Themes` page.
11. Fix installer validation path so stale local `configure-gtk-final.py` cannot mask this branch.
12. Fix gallery layout expansion in the main app.
13. Filter gallery themes to the detected/configured display size.
14. Fix open theme folder in niri with direct file-manager fallback and debug logs.

Follow-up stack:

1. Export theme.
2. Device Manager / display-profile integration.
