# 24_converted_video_theme

Converted from `24.turtheme` from the Windows TURZX 2.1-inch app.

## What was extracted

- `ui_overlay.png`: transparent UI overlay extracted from the `.turtheme` file.
- `windows_preview_full.png`: the Windows app's full preview frame, useful as a reference.
- `windows_video_reference_frame.png`: reference frame/background extracted from the `.turtheme`.
- `transparent.png`: helper image used as transparent background for text fields.
- `theme.yaml`: best-effort theme for `turing-smart-screen-python`.

## Required video

The original theme points to:

```text
/mnt/SDCARD/video/24.mp4
```

So the video must already exist on the screen/SD card at that path.

## Installation

Copy this folder into:

```text
res/themes/24/
```

Then set in `config.yaml`:

```yaml
config:
  THEME: 24
```

This theme assumes you are using the native video overlay patch for Rev. C / 2.1-inch screens.

## Notes

This is a best-effort conversion. The Windows `.turtheme` is a serialized app-specific format, not the same as `theme.yaml`. The extracted UI layer and video path are reliable; sensor mappings and exact text/font positions may need small manual adjustments.
