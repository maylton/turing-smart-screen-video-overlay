# Media preparation editor MVP

The media preparation editor converts common GIF/video inputs into the
native-video profile validated for the Turing Rev. C 2.1-inch display.

## Open the editor

Open **Video Manager** and select **Import and prepare media…**, or run:

```bash
media-preparation-gtk.py
```

## Supported inputs

- GIF
- MP4
- MKV
- WebM
- MOV
- AVI

## Current target profile

- MP4 container;
- H.264 video;
- 480×480;
- `yuv420p`;
- 24 or 30 FPS;
- no audio.

## Workflow

1. Choose a source file.
2. Review codec, size, duration, FPS, and audio metadata.
3. Select Fit, Fill/Cover, or Stretch.
4. Adjust zoom and X/Y position, or drag directly on the preview.
5. Set trim start/end and output FPS.
6. Convert to the cache directory.
7. Preview the converted loop.
8. Upload to SD or internal storage through the hardened video backend.

The original source is never modified. Generated files are stored under:

```text
$XDG_CACHE_HOME/turing-smart-screen/media-preparation
```

or `~/.cache/turing-smart-screen/media-preparation` when
`XDG_CACHE_HOME` is unset.

## CLI

Analyze:

```bash
./venv/bin/python3 media-preparation.py --json probe source.gif
```

Render a preview frame:

```bash
./venv/bin/python3 media-preparation.py --json preview source.mp4 \
  --mode fill --zoom 1.15 --x 12 --y -4 --output /tmp/preview.png
```

Convert:

```bash
./venv/bin/python3 media-preparation.py --json convert source.webm \
  --mode fit --fps 30 --output /tmp/prepared.mp4
```

## Scope after the MVP

Later phases will add crop handles, rotation, custom/background images,
blurred backgrounds, playback speed, richer GIF loop controls, and
reusable profiles for other display dimensions.
