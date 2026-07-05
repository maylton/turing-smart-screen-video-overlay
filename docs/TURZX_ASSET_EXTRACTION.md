# TURZX Windows theme asset extraction

## Decision

For now, we are not reviving the old TURZX_COMPAT converter.

The first supported workflow is intentionally simpler:

1. Select a Windows .turtheme file.
2. Extract embedded image/video assets.
3. Save the assets to a normal folder.
4. Recreate the theme manually in the Linux editor.

Later, the app can expose this through a button named:

Extract Windows theme assets

## Script

Standalone extractor:

tools/turzx_extract_assets.py

It uses only the Python standard library.

## Usage

Example:

python3 tools/turzx_extract_assets.py /home/mayltonf/Downloads/t-nzxt/TRX02.turtheme --output /tmp/TRX02-assets --overwrite

## Output

The output folder may contain:

images/
videos/
manifest.json

## Manifest

manifest.json includes:

- input path
- input size
- input SHA-256
- whether the input looked like a ZIP archive
- image count
- video count
- total asset count
- skipped duplicate count
- metadata for each extracted asset

## Detection strategy

The extractor checks:

- ZIP-like theme entries with media extensions
- base64 data URLs
- raw embedded file signatures

Currently recognized media:

Images:
- PNG
- JPEG
- WEBP
- GIF
- BMP

Videos:
- MP4 / MOV-style ISO-BMFF
- WEBM, when present as file entry
- MKV, when present as file entry
- AVI

## Non-goals

This script does not:

- convert theme layout
- interpret Windows widget positions
- generate a Linux theme JSON
- emulate the Windows runtime
- support encrypted proprietary payloads

## Validation

Run from the repository root:

python3 -m py_compile tools/turzx_extract_assets.py

python3 tools/turzx_extract_assets.py /home/mayltonf/Downloads/t-nzxt/TRX02.turtheme --output /tmp/TRX02-assets --overwrite

find /tmp/TRX02-assets -maxdepth 3 -type f | sort

python3 -m json.tool /tmp/TRX02-assets/manifest.json | head -120

## Next step

After this standalone extractor is validated, integrate it into the app with a button:

Extract Windows theme assets

Only after this works should we copy or synchronize extracted assets into:

~/.local/share/turing-smart-screen
