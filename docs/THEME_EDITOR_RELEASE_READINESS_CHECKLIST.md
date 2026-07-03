# GTK Theme Editor Release Readiness Checklist

This checklist defines the final validation pass before treating the GTK Theme Editor as the release-ready/default theme editing surface.

It follows:

- `docs/THEME_EDITOR_ROADMAP_STATUS.md`
- `docs/THEME_EDITOR_CLASSIC_PARITY_AUDIT.md`

Current policy: the classic editor remains available behind `Advanced / Legacy Editor…` until this checklist and at least one normal editing-session observation pass.

## Release readiness goal

The GTK editor is release-ready when a tester can complete a normal real-theme editing session without opening the classic editor and without corrupting `theme.yaml`, generated media, or preview output.

## Required environment

Use a clean worktree based on the current integration branch:

```bash
cd ~/Downloads/turing-smart-screen-theme-editor-media-test

git fetch origin

git switch feature/theme-video-inspector-live-preview
git pull --ff-only origin feature/theme-video-inspector-live-preview

git status --short
```

Expected starting state:

```text
(no output from git status --short)
```

If generated theme files are dirty from a previous manual GTK test, restore them first:

```bash
git restore res/themes/24/theme.yaml res/themes/24/preview.png
```

## Technical validation

Run these before manual GTK testing:

```bash
.venv/bin/python -m py_compile theme-editor-gtk.py
.venv/bin/python -m unittest discover -s tests -t . -v
git diff --check
git status --short
```

Pass criteria:

- `py_compile` exits successfully.
- Unit tests pass.
- `git diff --check` reports no whitespace errors.
- `git status --short` only shows files intentionally changed during the current validation.

## Manual GTK launch

Launch with a real theme:

```bash
.venv/bin/python theme-editor-gtk.py 24
```

Pass criteria:

- The GTK editor opens.
- The theme tree loads.
- The preview area loads or reports a clear recoverable issue.
- The app does not require the classic editor at startup.

## Core editor smoke test

### 1. Selection and properties

- Select at least one normal element.
- Confirm the path label updates.
- Confirm property rows are shown.
- Edit one harmless scalar value.
- Apply/save the change.
- Confirm preview refreshes.
- Revert the change.

Pass criteria:

- The value saves correctly.
- Preview refreshes.
- No exception is printed.
- Reverting restores the original value.

### 2. Pending property close guard

- Type a property change without applying it.
- Close the window.
- Confirm the Save / Discard / Cancel dialog appears.
- Click Cancel.
- Confirm the editor remains open.
- Repeat and click Discard.

Pass criteria:

- Typed-but-unapplied changes are not silently discarded.
- Cancel keeps the editor open.
- Discard closes or resets only after explicit confirmation.

### 3. Undo/redo

- Make a harmless saved edit.
- Use Undo.
- Use Redo.

Pass criteria:

- Undo and redo update the theme data and preview consistently.
- Buttons/toasts reflect unavailable history when stacks are empty.

## Theme lifecycle actions

### 4. Save

- Make a harmless change.
- Use Save.

Pass criteria:

- Save succeeds.
- `theme.yaml` stays valid.
- External-change guard does not trigger unless the file really changed externally.

### 5. Save As

- Use `Save As…` with a temporary test name.
- Confirm a copy is created.
- Remove the temporary test theme after validation.

Pass criteria:

- The copy exists.
- The original theme remains unchanged except for intended edits.
- No paths point unexpectedly to the old theme after switching/copying.

### 6. Rename Theme

- Test only on a disposable copied theme.
- Rename it.
- Confirm the renamed folder loads.

Pass criteria:

- Rename works on the copied theme.
- Original theme remains available.

## Element structure workflows

### 7. Add element

- Add a simple/catalog element appropriate for the test theme.
- Save.
- Confirm it appears in the tree.
- Remove it before final cleanup.

Pass criteria:

- Add flow does not require the classic editor.
- Tree and preview rebuild correctly.
- Save guard remains active.

### 8. Duplicate element

- Duplicate a safe custom/static element.
- Confirm the duplicate appears.
- Save.
- Delete the duplicate before final cleanup.

Pass criteria:

- Duplicate names/paths do not collide destructively.
- Preview and tree stay consistent.

### 9. Delete element

- Delete only a disposable element created during this test.
- Confirm any destructive prompt appears.
- Save.

Pass criteria:

- Deletion is explicit and guarded.
- Preview and tree rebuild correctly.
- Undo/reload path remains safe.

### 10. Reorder layer

- Select a reorderable element.
- Move forward/backward.
- Save.
- Restore original order.

Pass criteria:

- Reorder controls are sensitive only when appropriate.
- Layer order changes are saved through the guarded save path.

## Static image workflows

### 11. Static image layout inspector

- Select a static image element.
- Open the image layout inspector.
- Change a non-destructive layout setting.
- Apply.
- Restore the original setting.

Pass criteria:

- Inspector opens.
- Preview updates.
- `theme.yaml` remains valid.
- Generated/managed media references remain consistent.

### 12. Image transform/generated asset flow

- If the theme has a suitable image, test a small transform preview/apply flow.
- Open Generated Media afterward.

Pass criteria:

- Transform preview works.
- Generated asset is tracked.
- Generated Media Manager classifies the asset correctly.

## Video workflows

### 13. Video Inspector V2

Select the `video` node and test:

- Inspector opens.
- Mirror horizontal/vertical controls display.
- Trim start/end controls display.
- Playback speed control displays.
- Loop count control displays.
- Background mode controls display.
- Live preview responds to harmless changes.

Pass criteria:

- Controls are visible and responsive.
- Preview generation does not crash.
- Reverting returns to the original settings.

### 14. Video background tools

- Open the video background/tools flow.
- Confirm prepared local video detection works when applicable.

Pass criteria:

- Tool opens.
- Missing video/backend issues are reported clearly.
- No classic editor fallback is required.

## Generated media workflows

### 15. Generated Media Manager

- Open `Tools -> Generated Media`.
- Confirm records are listed.
- Confirm statuses are understandable: in-use, unused, orphaned, unmanaged.

Pass criteria:

- Manager opens.
- It does not delete anything automatically.
- Removal is only available for safe unused managed assets.

### 16. Safe removal of unused managed asset

Only run if a disposable unused managed asset exists.

- Remove one safe unused managed asset.
- Confirm manifest/data behavior.

Pass criteria:

- Only the selected unused managed asset is removed.
- Referenced/orphaned/unmanaged assets are not removed accidentally.
- Diagnostics reflect the updated state.

## YAML/file access and recovery

### 17. Copy/open file actions

From the overflow menu, test:

- Copy Theme Folder Path
- Copy Theme YAML Path
- Open Theme Folder
- Open Theme Folder in Terminal
- Open Theme YAML

Pass criteria:

- Copy actions place the expected paths on the clipboard.
- Folder opens/reveals correctly.
- Terminal opens in the theme folder when a supported terminal exists.
- Open Theme YAML shows the warning dialog first.

### 18. External-change guard

- Open the GTK editor.
- Change `theme.yaml` externally.
- Return to GTK.
- Attempt to save a harmless GTK change.

Pass criteria:

- Save is blocked.
- The error explains that `theme.yaml` changed outside the editor.
- The editor does not overwrite the external change.

### 19. Reload Theme From Disk

After the external-change guard test:

- Use `Reload Theme From Disk`.
- Confirm tree/properties/preview rebuild.
- Make a harmless edit and save.

Pass criteria:

- Reload succeeds.
- File signature is refreshed.
- Saving works again after reload.

## Theme Diagnostics

### 20. Diagnostics report

- Open `Theme Diagnostics`.
- Confirm it shows:
  - theme name;
  - theme folder;
  - YAML path;
  - file signature;
  - external-change status;
  - pending property-edit status;
  - selected path;
  - structure counts;
  - video summary;
  - generated-media summary;
  - missing asset reference summary;
  - undo/redo counts.

Pass criteria:

- Dialog opens without crashing.
- Report is read-only.
- Values update after external edits/reloads.

### 21. Copy diagnostics report

- Click `Copy Report`.
- Paste it into a text editor.

Pass criteria:

- Full report is copied.
- Paths and counts are useful for debugging.

## Classic editor fallback check

### 22. Advanced fallback gate

- Open the overflow menu.
- Click `Advanced / Legacy Editor…`.
- Confirm warning dialog appears.
- Click Cancel.
- Repeat and open only if explicitly validating fallback launch.

Pass criteria:

- Classic editor is not prominent.
- Opening it requires explicit confirmation.
- Normal GTK validation does not require using it.

## Final cleanup

After manual testing:

```bash
git restore res/themes/24/theme.yaml res/themes/24/preview.png

git status --short
```

Pass criteria:

- No unintended tracked changes remain.
- Disposable copied/renamed themes are removed or intentionally ignored.

## Release readiness decision

Mark the GTK editor release-ready only if all of these are true:

- Technical validation passes.
- Manual launch passes.
- Core editor smoke tests pass.
- Theme lifecycle actions pass or unsafe ones are validated on disposable copies only.
- Element structure workflows pass.
- Static image workflows pass.
- Video Inspector V2 workflows pass.
- Generated Media Manager opens and behaves safely.
- External-change guard blocks overwrites.
- Reload Theme From Disk recovers correctly.
- Theme Diagnostics opens and copies a useful report.
- The entire session is completed without needing the classic editor.

## Result template

Copy this into a PR, issue, or release note after a validation session:

```text
GTK Theme Editor release-readiness validation

Date:
Tester:
Branch/commit:
Theme tested:

Technical validation:
- py_compile:
- unit tests:
- diff check:

Manual validation:
- launch:
- core property edit:
- close guard:
- undo/redo:
- save/save-as/rename:
- add/duplicate/delete/reorder:
- static image layout:
- video inspector:
- generated media manager:
- file/YAML access:
- external-change guard:
- reload from disk:
- diagnostics/copy report:
- classic editor needed? yes/no

Issues found:
- 

Decision:
- release-ready / needs fixes / needs another observation session
```

## Current decision

Until this checklist passes in a real editing session, keep the classic editor available behind `Advanced / Legacy Editor…`.
