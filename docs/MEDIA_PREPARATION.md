# Media preparation editor

The media preparation editor converts GIFs and common video files into
profile-aware H.264 media without requiring manual FFmpeg commands.

## Compatible input

- GIF
- MP4
- MKV
- WebM
- MOV
- AVI

## Display profiles

The editor loads the active target from:

1. `config.yaml` → `config.THEME` and `display.REVISION`;
2. the active theme's `theme.yaml` → `DISPLAY_SIZE` and
   `DISPLAY_ORIENTATION`.

The active profile therefore follows the same dimensions used by the system
monitor. Reusable preview profiles are also available for common portrait,
landscape, square, and ultrawide canvases.

The profile panel shows:

- target width and height;
- hardware-validation status;
- native-upload availability;
- firmware-specific notes;
- an estimated output-size range.

## Native upload safety

Native upload remains enabled only for the profile physically validated by
this fork:

- Turing Rev. C 2.1-inch;
- 480 × 480;
- H.264;
- `yuv420p`;
- ROM 88 validation baseline.

Other profiles support conversion and local preview, but the editor disables
the Upload button until that hardware/profile combination is validated.

## Output contract

All current profiles use:

- MP4 container;
- H.264 through `libx264`;
- profile-selected dimensions;
- `yuv420p`;
- 24 or 30 FPS;
- no audio stream.

The backend validates codec, dimensions, pixel format, and audio removal after
every conversion.

## Framing

- **Fit** preserves the complete source and adds background space when needed.
- **Fill / Cover** fills the target canvas and clips overflow.
- **Stretch** forces the source into the profile dimensions.
- **Original size** keeps the cropped/rotated source dimensions before zoom.
- **Custom size** gives explicit foreground width and height.
- Numeric crop margins remove pixels from each source edge.
- Rotation supports 0°, 90°, 180°, and 270°.
- Nine-point alignment places the foreground on any canvas edge or corner.
- Dragging the preview provides fine positioning.

The preview canvas changes aspect ratio with the selected profile.

## Backgrounds

- Solid RGB color.
- Blurred copy of the source.
- Custom PNG, JPEG, WebP, or BMP image.

Background sources are scaled and center-cropped to the selected target
profile.

## Timing

- Trim start and end.
- Playback speed from 0.25× to 4×.
- Up to 20 extra input loops.
- 24 or 30 FPS output.

For GIFs, the embedded infinite-loop instruction is ignored so conversion
remains finite. Extra loops are controlled explicitly by the editor.

## Storage estimation

Before conversion, the editor estimates a low-to-high output-size range using:

- target resolution;
- selected FPS;
- effective output duration;
- encoder quality assumptions.

After conversion, the estimate is replaced by the exact local file size.
The estimate is advisory because H.264 size varies with motion and visual
complexity.

## Cache and privacy

Temporary previews and converted files are written to:

```text
${XDG_CACHE_HOME:-~/.cache}/turing-smart-screen/media-preparation
```

The editor does not upload anything until **Upload** is selected.

## CLI

List profiles:

```bash
./venv/bin/python3 media-preparation.py --json profiles
```

Estimate storage:

```bash
./venv/bin/python3 media-preparation.py --json estimate source.mp4 \
  --profile active-theme --mode fit
```

Convert for the active theme:

```bash
./venv/bin/python3 media-preparation.py --json convert source.mp4 \
  --profile active-theme --mode fit --output /tmp/prepared.mp4
```

## Validation

Run:

```bash
python -m unittest -v \
  tests.test_media_preparation \
  tests.test_media_profiles

python scripts/test-media-preparation-advanced.py
python scripts/test-media-profiles.py
```

The integration tests create temporary synthetic media and validate square,
portrait, and landscape H.264 outputs with real FFmpeg.
