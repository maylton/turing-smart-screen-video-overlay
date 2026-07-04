# Main App UI Review

## Findings

The main GTK app already had the important surfaces integrated into one window: Theme Gallery, Theme Editor, and Video Manager. The main rough spot on the landing page was the Overview preview: it behaved like a static image even when the active theme used native video, and early preview-renderer attempts did not match the Theme Editor/runtime overlay rendering closely enough.

## Implemented polish

- Added `library/main_app_ui_polish.py` as a focused runtime polish layer.
- Added `OverviewLivePreviewAnimator` to detect the active theme's `video:` block.
- Theme video detection supports both prepared local video references and display-side remote paths by looking up the corresponding prepared local media.
- When a theme video is enabled and available, the app generates a short 3.5 second animated preview using `ffmpeg`.
- The generated `preview.gif` is cached per theme/video/theme asset tree/renderer revision under `~/.cache/turing-smart-screen/overview-preview/<theme-key>/preview.gif`.
- Added `library/theme_preview_renderer.py` as the reusable full-theme preview renderer foundation.
- Preview generation renders the video frame at the theme's real canvas size and sends every frame through `render_theme_preview_frame()` before showing it in Overview.
- The renderer supports static images, static text, image-like nodes, text-like nodes, dynamic text, and first-pass mock dynamic bars/graphs/metrics based on theme geometry and keys.
- The text path now mirrors the runtime `DisplayText` semantics closely enough for Theme Editor parity: anchor, width/height, background transparency for video overlay themes, glow/outline/shadow effects, and crop/paste behavior.
- Added `library/theme_preview_mock_data.py` as the preview context provider.
- Preview mock values now derive from the same static sensor basis used by the Theme Editor's `HW_SENSORS=STATIC` preview.
- Date/time preview values now use the same static timestamp and `babel.dates` formatting semantics used by `stats.Date.stats()`.
- The Overview preview cycles cached PNG frames from the generated preview so the app can animate inside the existing `Gtk.Picture` reliably.
- If no video is available, the Overview preview remains the normal static theme preview.

## Completed phase split

Validated locally through Phase 21.3K:

- Phase 21.3A — mock preview data provider.
- Phase 21.3B — reusable full-theme preview renderer foundation.
- Phase 21.3C — wire Overview GIF generation through the renderer.
- Phase 21.3D — avoid broad renderer refactors that break video-theme previews; rebaseline to focused renderer fixes.
- Phase 21.3E — keep video preview overlays transparent and improve asset-aware cache invalidation.
- Phase 21.3F — preserve runtime-like text layout boxes and compensate glyph bounds.
- Phase 21.3G/21.3H — correct date/time overlay interpretation to separate runtime nodes instead of synthetic compound blocks.
- Phase 21.3I — mirror runtime `DisplayText` semantics for preview text rendering.
- Phase 21.3J — align date/time mock values with the Theme Editor STATIC preview.
- Phase 21.3K — derive Overview preview mock values from the static sensor/runtime basis.

## Safety notes

- GIF/frame generation runs in a background thread.
- Extracted assets are cached under `~/.cache/turing-smart-screen/overview-preview/`.
- Theme files are not modified by Overview preview generation.
- If `ffmpeg` is missing, extraction fails, or rendering cannot produce frames, the app falls back to the existing static preview.
- The renderer remains intentionally separate from hardware/display writes.

## Validation

```bash
.venv/bin/python -m py_compile library/theme_preview_mock_data.py
.venv/bin/python -m py_compile library/theme_preview_renderer.py
.venv/bin/python -m py_compile library/main_app_ui_polish.py
./install.sh --no-deps
grep -n "render_theme_preview_frame" ~/.local/share/turing-smart-screen/library/main_app_ui_polish.py
grep -n "draw_dynamic_widgets" ~/.local/share/turing-smart-screen/library/theme_preview_renderer.py
grep -n "STATIC_PREVIEW_TIMESTAMP" ~/.local/share/turing-smart-screen/library/theme_preview_mock_data.py
rm -rf ~/.cache/turing-smart-screen/overview-preview
turing-smart-screen
```

Manual test:

1. Clear the previous preview cache with `rm -rf ~/.cache/turing-smart-screen/overview-preview`.
2. Open Overview.
3. Use an active theme with `video.ENABLED: true` and either a valid `video.LOCAL_PATH` or a display-side `video.PATH` whose prepared local media exists.
4. Confirm the preview animates with the video's frames.
5. Confirm image and text overlays appear over the animated background.
6. Confirm text position, size, anchor, outline/glow/shadow, and transparent overlay behavior match the Theme Editor preview.
7. Confirm date/time values match the Theme Editor STATIC preview.
8. Check `~/.cache/turing-smart-screen/overview-preview/` and confirm a `preview.gif` was generated for the theme.
9. Use a theme with no video and confirm it falls back to the normal static preview.
