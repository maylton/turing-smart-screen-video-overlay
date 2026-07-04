# Main App UI Review

## Findings

The main GTK app already had the important surfaces integrated into one window: Theme Gallery, Theme Editor, and Video Manager. The remaining rough spot on the landing page was the Overview preview: it still behaved like a static image even when the active theme used native video.

## Implemented polish

- Added `library/main_app_ui_polish.py` as a focused runtime polish layer.
- Added `OverviewLivePreviewAnimator` to detect the active theme's `video:` block.
- Theme video detection supports both prepared local video references and display-side remote paths by looking up the corresponding prepared local media.
- When a theme video is enabled and available, the app generates a short 3.5 second animated preview using `ffmpeg`.
- The generated `preview.gif` is cached per theme/video/theme-yaml revision under `~/.cache/turing-smart-screen/overview-preview/<theme-key>/preview.gif`.
- Added `library/theme_preview_mock_data.py` with deterministic sample values for CPU/GPU/RAM/date/time/network/fans/etc.
- Added `library/theme_preview_renderer.py` as the reusable full-theme preview renderer foundation.
- Preview generation now renders the video frame at the theme's real canvas size and sends every frame through `render_theme_preview_frame()` before downscaling for the Overview.
- The renderer currently supports static images, static text, image-like nodes, text-like nodes, and first-pass mock dynamic widgets for bars/graphs/metrics based on theme geometry and keys.
- The Overview preview cycles cached PNG frames from the generated preview so the app can animate inside the existing `Gtk.Picture` reliably.
- The extra preview caption/label was removed from the UI; the preview itself should be enough.
- If no video is available, the Overview preview remains the normal static theme preview.

## Phase split

Completed for validation now:

- Phase 21.3A — mock preview data provider.
- Phase 21.3B — reusable full-theme preview renderer foundation.
- Phase 21.3C — wire Overview GIF generation through the renderer.

Deferred until after local validation:

- Phase 21.3D — refine renderer coverage for the exact live monitor widgets that still do not appear.
- Phase 21.3E — optional static-theme preview regeneration without video.
- Phase 21.3F — diagnostics/reporting for skipped theme nodes in the preview renderer.

## Safety notes

- GIF/frame generation runs in a background thread.
- Extracted assets are cached under `~/.cache/turing-smart-screen/overview-preview/`.
- Theme files are not modified.
- If `ffmpeg` is missing, extraction fails, or rendering cannot produce frames, the app falls back to the existing static preview.

## Validation

```bash
.venv/bin/python -m py_compile library/theme_preview_mock_data.py
.venv/bin/python -m py_compile library/theme_preview_renderer.py
.venv/bin/python -m py_compile library/main_app_ui_polish.py
./install.sh --no-deps
grep -n "render_theme_preview_frame" ~/.local/share/turing-smart-screen/library/main_app_ui_polish.py
grep -n "draw_dynamic_widgets" ~/.local/share/turing-smart-screen/library/theme_preview_renderer.py
turing-smart-screen
```

Manual test:

1. Clear the previous no-overlay GIF cache with `rm -rf ~/.cache/turing-smart-screen/overview-preview`.
2. Open Overview.
3. Use an active theme with `video.ENABLED: true` and either a valid `video.LOCAL_PATH` or a display-side `video.PATH` whose prepared local media exists.
4. Confirm the preview animates with the video's frames.
5. Confirm static image/text overlays are visible over the animated background.
6. Confirm first-pass mock dynamic bars/graphs/metric text appear for at least some monitor widgets.
7. Check `~/.cache/turing-smart-screen/overview-preview/` and confirm a `preview.gif` was generated for the theme.
8. Use a theme with no video and confirm it falls back to the normal static preview.
