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
- search/filter by theme name, path, YAML filename, or status;
- result count for filtered searches;
- filtered empty state when no theme matches;
- per-theme gallery diagnostics action;
- copyable gallery-level diagnostics report;
- guarded `Use` action to set a theme as current;
- atomic `config.yaml` update for `config.THEME`;
- no theme file writes from browsing, filtering, or diagnostics.

Not included yet:

- import/export/duplicate/delete management actions;
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

Manual validation:

1. Launch the existing main app with `.venv/bin/python configure-gtk.py` or the installed `turing-smart-screen` command after reinstalling.
2. Open the sidebar `Themes` page.
3. Confirm the old split list/preview view is replaced by the gallery cards.
4. Confirm the `Create blank` button is still available at the top of the page.
5. Search by part of a theme name and confirm the card list filters.
6. Search by `missing`, `theme.yaml`, or a path fragment and confirm matching works.
7. Confirm an unmatched search shows the filtered empty state.
8. Clear search and confirm all themes return.
9. Confirm per-theme `Edit` opens the selected theme.
10. Confirm per-theme diagnostics opens a report dialog.
11. Confirm `Copy Report` copies the diagnostics report.
12. Click `Use` on a non-current valid theme and confirm the dialog appears.
13. Confirm `Use Theme` updates the current badge and `config.yaml` `THEME` value.
14. Confirm broken themes cannot be set as current.
15. Confirm per-theme folder button opens the theme folder.
16. Confirm refresh updates the card list and preserves the current search query.
17. Confirm browsing/searching/diagnostics do not modify tracked theme files.
18. Restore the test config change before final merge if needed: `git restore config.yaml`.

## Stack status

Completed in this branch so far:

- Phase 1 — reusable Theme Gallery module.
- Phase 2 — temporary app shell prototype with Theme Gallery embedded.
- Phase 3 — gallery search/filter.
- Phase 4 — gallery diagnostics action.
- Phase 5 — set active/current theme from the gallery.
- Phase 6 — integrate the gallery into the existing main app `Themes` page.

Next phase:

- Validate the integrated main-app Themes page locally before merging.
