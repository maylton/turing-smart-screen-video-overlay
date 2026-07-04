# Theme App Shell MVP

This document describes the Theme Gallery / Theme Manager stack from `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`.

The implementation now targets the **existing installed GTK configuration app** launched by `turing-smart-screen`, not only a separate prototype shell.

## Entry points

Normal installed app entry point:

```bash
turing-smart-screen
```

Development checkout entry point for the same main app:

```bash
.venv/bin/python configure-gtk.py
```

Temporary standalone prototype entry point:

```bash
.venv/bin/python turing-smart-screen-gtk.py
```

## Scope

Included so far:

- reusable Theme Gallery model/UI in `library/theme_gallery.py`;
- temporary standalone shell in `turing-smart-screen-gtk.py` for development experiments;
- integration into the existing main GTK configuration app via `configure-gtk.py` runtime patches;
- replacement of the old main-app `Themes` page with the reusable `ThemeGalleryPane`;
- `Create blank` action retained from the old Themes page;
- compatible-theme filtering by detected/configured display size;
- search/filter by theme name, path, YAML filename, display size, or status;
- result count for filtered searches;
- filtered empty state when no compatible theme matches;
- per-theme gallery diagnostics action;
- copyable gallery-level diagnostics report;
- guarded `Use` action to set a theme as current;
- atomic `config.yaml` update for `config.THEME`;
- non-destructive per-theme duplicate action;
- guarded delete action that requires typing the exact theme name;
- delete moves themes to Trash and refuses to delete the current theme;
- robust theme folder opening using GTK/GIO first, `gio open`/`xdg-open` with captured errors, then file-manager fallbacks;
- installer guard so local `configure-gtk-final.py` leftovers cannot override the branch's `configure-gtk.py` during installed-app tests;
- installed syntax validation for `library/theme_gallery.py`, `theme-gallery-gtk.py`, and `turing-smart-screen-gtk.py`;
- no theme file writes from browsing, filtering, diagnostics, or opening folders.

Not included yet:

- rename theme;
- import/export theme;
- real Device Manager implementation.

## Architecture decision

The normal user-facing direction is now:

```text
configure-gtk.py / turing-smart-screen     # existing installed app
└─ Themes page                             # reusable ThemeGalleryPane
   └─ theme-editor-gtk.py                  # editor launched for a selected theme
```

`turing-smart-screen-gtk.py` remains a temporary prototype/dev entry point and should not be treated as the real installed app.

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

Installed-app validation:

```bash
./install.sh --no-deps
grep -n "ThemeGalleryPane" ~/.local/share/turing-smart-screen/configure-gtk.py
turing-smart-screen
```

Manual validation:

1. Launch the existing main app with `.venv/bin/python configure-gtk.py` or the installed `turing-smart-screen` command after reinstalling.
2. Open the sidebar `Themes` page.
3. Confirm the old split list/preview view is replaced by the gallery cards.
4. Confirm only compatible themes are shown for the detected/configured display size.
5. Confirm the `Create blank` button is still available at the top of the page.
6. Search by part of a theme name and confirm the card list filters.
7. Search by `missing`, `theme.yaml`, display size, or a path fragment and confirm matching works.
8. Confirm an unmatched search shows the filtered empty state.
9. Clear search and confirm all compatible themes return.
10. Confirm per-theme `Edit` opens the selected theme.
11. Confirm per-theme diagnostics opens a report dialog.
12. Confirm `Copy Report` copies the diagnostics report.
13. Click `Use` on a non-current valid theme and confirm the dialog appears.
14. Confirm `Use Theme` updates the current badge and `config.yaml` `THEME` value.
15. Confirm broken themes cannot be set as current.
16. Click duplicate on a valid theme and confirm a copy is created with a safe non-conflicting folder name.
17. Confirm duplicate does not change `config.yaml` automatically.
18. Click delete on the duplicated theme, type the exact name, and confirm it moves to Trash.
19. Confirm the current theme does not show a delete button.
20. Confirm per-theme folder button opens the theme folder in the file manager or shows a useful error dialog.
21. Confirm refresh updates the card list and preserves the current search query.
22. Confirm browsing/searching/diagnostics/folder-open do not modify tracked theme files.
23. Restore test config/theme changes before final merge if needed.

## Stack status

Completed in this branch so far:

- Phase 1 — reusable Theme Gallery module.
- Phase 2 — temporary app shell prototype with Theme Gallery embedded.
- Phase 3 — gallery search/filter.
- Phase 4 — gallery diagnostics action.
- Phase 5 — set active/current theme from the gallery.
- Phase 6 — integrate the gallery into the existing main app `Themes` page.
- Phase 7 — fix installer path so stale `configure-gtk-final.py` cannot mask this branch.
- Phase 8 — fix gallery layout expansion in the main app.
- Phase 9 — filter gallery themes to the detected/configured display size.
- Phase 10 — duplicate theme and fix open theme folder.
- Phase 11 — delete theme with confirmation and safer folder-opening diagnostics.

Next phase:

- Rename theme.
