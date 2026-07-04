# Main App UI Review

## Findings

The main GTK app already had the important surfaces integrated into one window: Theme Gallery, Theme Editor, and Video Manager. The remaining rough spot on the landing page was the Overview preview: it still behaved like a static image even when the active theme used native video.

## Implemented polish

- Added `library/main_app_ui_polish.py` as a focused runtime polish layer.
- Added `OverviewLivePreviewAnimator` to detect the active theme's `video:` block.
- Theme video detection supports both prepared local video references and display-side remote paths by looking up the corresponding prepared local media.
- When a theme video is enabled and available, the app generates a short 3.5 second animated preview using `ffmpeg`.
- The generated `preview.gif` is cached per theme/video/theme-yaml revision under `~/.cache/turing-smart-screen/overview-preview/<theme-key>/preview.gif`.
- Preview generation now renders the video frame at the theme's real canvas size and composites visible `static_images` and `static_text` over every frame before downscaling for the Overview.
- The Overview preview cycles cached PNG frames from the generated preview so the app can animate inside the existing `Gtk.Picture` reliably.
- The extra preview caption/label was removed from the UI; the preview itself should be enough.
- If no video is available, the Overview preview remains the normal static theme preview.

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
2. Use an active theme with `video.ENABLED: true` and either a valid `video.LOCAL_PATH` or a display-side `video.PATH` whose prepared local media exists.
3. Confirm the preview animates with the video's frames.
4. Confirm static image/text overlays are visible over the animated background.
5. Check `~/.cache/turing-smart-screen/overview-preview/` and confirm a `preview.gif` was generated for the theme.
6. Use a theme with no video and confirm it falls back to the normal static preview.
