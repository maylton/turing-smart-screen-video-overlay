# Theme App Shell MVP

This document describes stack phase 2 from `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`.

The app shell establishes one user-facing GTK/Libadwaita launcher for future surfaces instead of letting each roadmap feature become a separate standalone app.

## Entry point

```bash
.venv/bin/python turing-smart-screen-gtk.py
```

## Scope

Included in this slice:

- new primary app-shell entry point: `turing-smart-screen-gtk.py`;
- embedded Theme Gallery surface using `library.theme_gallery.ThemeGalleryPane`;
- sidebar navigation with the current `Themes` surface and disabled placeholders for future surfaces;
- `Open Current` action in the shell header;
- refresh action routed to the current surface;
- app-level toasts and error dialogs;
- no theme file writes from browsing the shell.

Not included yet:

- search/filter;
- diagnostics action from the gallery;
- setting the active/current theme from gallery;
- import/export/duplicate/delete management actions;
- real Device Manager implementation.

## Architecture decision

The normal user-facing direction is now:

```text
turing-smart-screen-gtk.py       # main app shell
└─ ThemeGalleryPane              # home surface
   └─ theme-editor-gtk.py        # editor launched for a selected theme
```

Temporary direct scripts may still exist for development/testing, but new roadmap features should be integrated into the shell as surfaces, dialogs, or reusable modules.

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

1. Launch `turing-smart-screen-gtk.py`.
2. Confirm the shell opens with a sidebar.
3. Confirm `Themes` is selected.
4. Confirm theme cards render inside the shell.
5. Confirm `Open Current` opens the GTK Theme Editor.
6. Confirm per-theme `Edit` opens the selected theme.
7. Confirm per-theme folder button opens the theme folder.
8. Confirm refresh updates the card list.
9. Confirm disabled sidebar rows do not open separate apps.
10. Confirm browsing does not modify tracked theme files.

## Stack status

Completed in this branch so far:

- Phase 1 — reusable Theme Gallery module.
- Phase 2 — main GTK app shell with Theme Gallery embedded.

Next phase:

- Phase 3 — gallery search/filter inside the shell.
