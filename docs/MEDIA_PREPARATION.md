# Media preparation editor

The media preparation editor converts GIFs and common video files into native
Rev. C display media without requiring manual FFmpeg commands.

## Compatible input

- GIF
- MP4
- MKV
- WebM
- MOV
- AVI

## Output contract

Prepared files use:

- MP4 container;
- H.264 video;
- 480 × 480 resolution;
- `yuv420p`;
- 24 or 30 FPS;
- no audio stream.

## Basic framing

- **Fit** preserves the complete source and adds background space when needed.
- **Fill / Cover** fills the square and clips overflow.
- **Stretch** forces the source into the square.
- Zoom and drag positioning remain available for all modes.

## Advanced framing

- **Original size** keeps the cropped/rotated source dimensions before zoom.
- **Custom size** gives explicit foreground width and height.
- Numeric crop margins remove pixels from each source edge.
- Rotation supports 0°, 90°, 180°, and 270°.
- Nine-point alignment places the foreground on any canvas edge or corner.
- Dragging the preview still applies fine positioning.

## Backgrounds

- Solid RGB color.
- Blurred copy of the source.
- Custom PNG, JPEG, WebP, or BMP image.

The custom background image is scaled and center-cropped to the 480 × 480
canvas.

## Timing

- Trim start and end.
- Playback speed from 0.25× to 4×.
- Up to 20 extra input loops.
- 24 or 30 FPS output.

For GIFs, the embedded infinite-loop instruction is ignored so conversion
remains finite. Extra loops are controlled explicitly by the editor.

## Cache and privacy

Temporary previews and converted files are written to:

```text
${XDG_CACHE_HOME:-~/.cache}/turing-smart-screen/media-preparation
```

The editor does not upload anything until **Upload** is selected.

## Validation

Run:

```bash
python -m unittest -v tests.test_media_preparation
python scripts/test-media-preparation-advanced.py
```

The integration test creates temporary synthetic media, tests blurred and
custom-image backgrounds, rotation, crop, speed, loops, preview generation,
and validates the resulting H.264 480 × 480 files.
