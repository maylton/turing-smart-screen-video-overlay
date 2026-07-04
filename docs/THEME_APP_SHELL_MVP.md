# Theme App Shell MVP

This document describes the Theme Gallery / Theme Manager stack from `docs/THEME_APP_ARCHITECTURE_CHECKPOINT.md`.

The implementation now targets the **existing installed GTK configuration app** launched by `turing-smart-screen`, not only a separate prototype shell.

## Entry points

Normal installed app entry point:

```bash
turing-smart-screen
```

Development checkout entry point for the integrated installed-app launcher:

```bash
.venv/bin/python turing-smart-screen-main.py
```

Legacy/runtime launcher entry point:

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
- rename action with sanitization, overwrite protection, and current-theme config update;
- guarded delete action that requires typing the exact theme name;
- delete moves themes to Trash and refuses to delete the current theme;
- import action for theme folders or safe `.zip` archives;
- export action for selected themes as `.zip` archives;
- export skips temporary/editor-backup/cache files and refuses to overwrite existing archives;
- compact gallery card action layout with secondary actions in an overflow menu;
- embedded Theme Editor page inside the main app stack for the normal gallery `Edit` flow;
- standalone `theme-editor-gtk.py` kept as the fallback/dev entry point;
- Rev. C runtime guard that clips partially offscreen bitmap updates instead of crashing on negative packet addresses;
- robust theme folder opening using GTK/GIO first, `gio open`/`xdg-open` with captured errors, then file-manager fallbacks;
- debug logging for the theme-folder open action with `TURING_THEME_GALLERY_DEBUG=1`;
- installer guard so local `configure-gtk-final.py` leftovers cannot override the branch's `configure-gtk.py` during installed-app tests;
- installed syntax validation for the integrated launcher, embedded editor helpers, and gallery/runtime modules;
- no theme file writes from browsing, filtering, diagnostics, or opening folders.

Not included yet:

- full export preflight for referenced/generated media;
- real Device Manager implementation.

## Architecture decision

The normal user-facing direction is now:

```text
turing-smart-screen                         # installed app command
└─ turing-smart-screen-main.py              # integrated launcher wrapper
   └─ configure-gtk.py runtime patches      # existing app foundation
      ├─ Themes page                        # reusable ThemeGalleryPane
      └─ Embedded Theme Editor page         # existing editor content hosted in app stack
```

`theme-editor-gtk.py` remains available as a standalone fallback/dev entry point, but the normal gallery `Edit` path should open the editor inside the main app.

## Debugging folder opening

Run the installed app from a terminal with debug logging enabled:

```bash
TURING_THEME_GALLERY_DEBUG=1 turing-smart-screen 2>&1 | tee /tmp/turing-theme-gallery-debug.log
```

Then click the folder button in `Themes`. The terminal should print `[theme-gallery]` lines showing whether the callback fired, the target path, desktop/session environment, and the result of each opener attempt.

If there are no `[theme-gallery]` lines after clicking, the button callback is not firing. If there are lines but no file manager opens, use the logged `gio`, `xdg-open`, or file-manager result to decide the next fix.

## Validation

```bash
.venv/bin/python -m py_compile sitecustomize.py
.venv/bin/python -m py_compile theme_gallery_card_polish.py
.venv/bin/python -m py_compile turing-smart-screen-main.py
.venv/bin/python -m py_compile library/theme_gallery.py
.venv/bin/python -m py_compile library/embedded_theme_editor.py
.venv/bin/python -m py_compile library/embedded_theme_editor_runtime.py
.venv/bin/python -m py_compile library/runtime_rev_c_image_guard.py
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
grep -n "turing-smart-screen-main.py" ~/.local/bin/turing-smart-screen
grep -n "EmbeddedThemeEditorPage" ~/.local/share/turing-smart-screen/library/embedded_theme_editor.py
grep -n "runtime_rev_c_image_guard" ~/.local/share/turing-smart-screen/sitecustomize.py
turing-smart-screen
```

Manual validation:

1. Launch the existing main app with the installed `turing-smart-screen` command after reinstalling.
2. Open the sidebar `Themes` page.
3. Confirm the old split list/preview view is replaced by the gallery cards.
4. Confirm only compatible themes are shown for the detected/configured display size.
5. Confirm the `Create blank` button is still available at the top of the page.
6. Confirm each card shows only `Use`, `Edit`, and `⋮` directly.
7. Open `⋮` and test duplicate, rename, export, open folder, diagnostics, and delete.
8. Click `Edit` on a theme and confirm the Theme Editor opens inside the main app window.
9. Confirm the embedded editor can render the preview and expose the existing editor panels/actions.
10. Use the embedded editor's `Themes` back button and confirm it returns to the gallery.
11. Use `Open separate window` and confirm the standalone GTK Theme Editor still opens as fallback.
12. Start the monitor with a theme containing partially offscreen images and confirm it logs clipping warnings instead of crashing with `OverflowError`.
13. Restore test config/theme changes before final merge if needed.

## Stack status

Completed in this branch so far:

- Phase 1 — reusable Theme Gallery module.
- Phase 2 — temporary app shell prototype with Theme Gallery embedded.
- Phase 3 — gallery search/filter.
- Phase 4 — gallery diagnostics action.
- Phase 5 — set active/current theme from the gallery.
- Phase 6 — duplicate theme.
- Phase 7 — rename theme.
- Phase 8 — delete theme with confirmation.
- Phase 9 — import theme from folder/archive.
- Phase 10 — integrate the gallery into the existing main app `Themes` page.
- Phase 11 — fix installer path so stale local `configure-gtk-final.py` cannot mask this branch.
- Phase 12 — fix gallery layout expansion in the main app.
- Phase 13 — filter gallery themes to the detected/configured display size.
- Phase 14 — fix open theme folder in niri with direct file-manager fallback and debug logs.
- Phase 15 — export theme to `.zip` archive.
- Phase 16 — polish Theme Gallery card actions into an overflow menu.
- Phase 17 — embed Theme Editor into the main app stack.
- Phase 18 — guard Rev. C bitmap updates against offscreen image coordinates.

Next phase:

- Export completeness: referenced/generated media preflight and missing-asset warnings.
