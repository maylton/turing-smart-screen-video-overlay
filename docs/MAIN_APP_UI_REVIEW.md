# Main App UI Review

## Findings

The main GTK app already had the important surfaces integrated into one window: Theme Gallery, Theme Editor, and Video Manager. The remaining rough spot on the landing page was the Overview preview: it still behaved like a static image even when the active theme used native video.

## Implemented polish

- Added `library/main_app_ui_polish.py` as a focused runtime polish layer.
- Wrapped the Overview preview in an overlay with a status caption.
- Added `OverviewLivePreviewAnimator` to detect the active theme's `video:` block.
- Theme video detection now supports both prepared local video references and display-side remote paths by looking up the corresponding prepared local media.
- When a theme video is enabled and available, the app generates a short 3.5 second GIF preview using `ffmpeg`.
- The generated GIF is cached per theme/video revision under `~/.cache/turing-smart-screen/overview-preview/<theme-key>/preview.gif`.
- The Overview preview also cycles cached PNG frames from that same generated preview so the app can animate inside the existing `Gtk.Picture` reliably.
- If no video is available, the Overview preview remains static and labels itself as a static preview.

## Safety notes

- GIF/frame generation runs in a background thread.
- Extracted assets are cached under `~/.cache/turing-smart-screen/overview-preview/`.
- Theme files are not modified.
- If `ffmpeg` is missing or extraction fails, the app falls back to the static preview.

## Validation

```bash
.venv/bin/python -m py_compile library/main_app_ui_polish.py
./install.sh --no-deps
grep -n "OverviewLivePreviewAnimator" ~/.local/share/turing-smart-screen/library/main_app_ui_polish.py
turing-smart-screen
```

Manual test:

1. Open Overview.
2. Confirm the preview shows a caption.
3. Use an active theme with `video.ENABLED: true` and either a valid `video.LOCAL_PATH` or a display-side `video.PATH` whose prepared local media exists.
4. Confirm the caption changes from `Generating theme GIF preview…` to `Animated theme preview · preview.gif`.
5. Confirm the preview cycles video frames.
6. Check `~/.cache/turing-smart-screen/overview-preview/` and confirm a `preview.gif` was generated for the theme.
7. Use a theme with no video and confirm it falls back to `Static theme preview`.
