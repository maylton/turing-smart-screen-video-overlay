# Main App UI Review

## Findings

The main GTK app already had the important surfaces integrated into one window: Theme Gallery, Theme Editor, and Video Manager. The remaining rough spot on the landing page was the Overview preview: it still behaved like a static image even when the active theme used native video.

## Implemented polish

- Added `library/main_app_ui_polish.py` as a focused runtime polish layer.
- Wrapped the Overview preview in an overlay with a status caption.
- Added `OverviewLivePreviewAnimator` to detect the active theme's `video:` block.
- When a theme video is enabled and available, the app extracts a tiny cached frame loop using `ffmpeg`.
- The Overview preview cycles those frames inside the existing `Gtk.Picture`, approximating the real display output without opening another window.
- If no video is available, the Overview preview remains static and labels itself as a static preview.

## Safety notes

- The frame extraction runs in a background thread.
- Extracted frames are cached under `~/.cache/turing-smart-screen/overview-preview/`.
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
3. Use an active theme with `video.ENABLED: true` and a valid `video.PATH`.
4. Confirm the caption changes from `Preparing live preview…` to `Live theme preview`.
5. Confirm the preview cycles video frames.
6. Use a theme with no video and confirm it falls back to `Static theme preview`.
