#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import struct
import sys
import zipfile
from pathlib import Path

IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}
VIDEO_EXTS = {"mp4", "mov", "m4v", "webm", "mkv", "avi"}

EXT_KIND = {}
for _ext in IMAGE_EXTS:
    EXT_KIND[_ext] = "image"
for _ext in VIDEO_EXTS:
    EXT_KIND[_ext] = "video"

MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u32be(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def u32le(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def find_all(data: bytes, needle: bytes):
    pos = 0
    while True:
        pos = data.find(needle, pos)
        if pos < 0:
            break
        yield pos
        pos += 1


def safe_stem(name: str, fallback: str) -> str:
    stem = Path(name.replace("\\", "/")).stem
    out = []
    for ch in stem:
        if ch.isalnum() or ch in "-_.() ":
            out.append(ch)
        else:
            out.append("_")
    value = "".join(out).strip(" ._")
    return value[:80] or fallback


def png_end(data: bytes, start: int) -> int | None:
    if not data.startswith(b"\x89PNG\r\n\x1a\n", start):
        return None

    pos = start + 8
    while pos + 12 <= len(data):
        length = u32be(data, pos)
        chunk_type = data[pos + 4 : pos + 8]
        end = pos + 12 + length
        if end > len(data):
            return None
        pos = end
        if chunk_type == b"IEND":
            return pos

    return None


def jpg_end(data: bytes, start: int) -> int | None:
    if not data.startswith(b"\xff\xd8\xff", start):
        return None

    end = data.find(b"\xff\xd9", start + 2)
    if end < 0:
        return None

    return end + 2


def gif_end(data: bytes, start: int) -> int | None:
    if not (data.startswith(b"GIF87a", start) or data.startswith(b"GIF89a", start)):
        return None

    end = data.find(b"\x3b", start + 6)
    if end < 0:
        return None

    return end + 1


def bmp_end(data: bytes, start: int) -> int | None:
    if not data.startswith(b"BM", start):
        return None
    if start + 14 > len(data):
        return None

    size = u32le(data, start + 2)
    if size < 54:
        return None
    if start + size > len(data):
        return None

    return start + size


def riff_end(data: bytes, start: int, riff_kind: bytes) -> int | None:
    if not data.startswith(b"RIFF", start):
        return None
    if start + 12 > len(data):
        return None
    if data[start + 8 : start + 12] != riff_kind:
        return None

    size = u32le(data, start + 4)
    end = start + 8 + size
    if end <= start or end > len(data):
        return None

    return end


def mp4_end(data: bytes, start: int) -> int | None:
    if start < 0 or start + 12 > len(data):
        return None
    if data[start + 4 : start + 8] != b"ftyp":
        return None

    pos = start
    last_end = start
    seen_ftyp = False

    while pos + 8 <= len(data):
        size = u32be(data, pos)
        box = data[pos + 4 : pos + 8]

        if not all(32 <= b <= 126 for b in box):
            break

        header = 8
        if size == 1:
            if pos + 16 > len(data):
                break
            size = struct.unpack_from(">Q", data, pos + 8)[0]
            header = 16
        elif size == 0:
            break

        if size < header:
            break

        box_end = pos + size
        if box_end > len(data):
            break

        if box == b"ftyp":
            seen_ftyp = True

        last_end = box_end
        pos = box_end

    if seen_ftyp and last_end > start:
        return last_end

    return None


def raw_candidates(data: bytes):
    found = []

    for start in find_all(data, b"\x89PNG\r\n\x1a\n"):
        end = png_end(data, start)
        if end:
            found.append((start, end, "png", "image", "raw PNG signature"))

    for start in find_all(data, b"\xff\xd8\xff"):
        end = jpg_end(data, start)
        if end:
            found.append((start, end, "jpg", "image", "raw JPEG signature"))

    for start in find_all(data, b"GIF87a"):
        end = gif_end(data, start)
        if end:
            found.append((start, end, "gif", "image", "raw GIF87a signature"))

    for start in find_all(data, b"GIF89a"):
        end = gif_end(data, start)
        if end:
            found.append((start, end, "gif", "image", "raw GIF89a signature"))

    for start in find_all(data, b"BM"):
        end = bmp_end(data, start)
        if end:
            found.append((start, end, "bmp", "image", "raw BMP signature"))

    for start in find_all(data, b"RIFF"):
        webp_end = riff_end(data, start, b"WEBP")
        if webp_end:
            found.append((start, webp_end, "webp", "image", "raw WEBP signature"))
            continue

        avi_end = riff_end(data, start, b"AVI ")
        if avi_end:
            found.append((start, avi_end, "avi", "video", "raw AVI signature"))

    for ftyp_pos in find_all(data, b"ftyp"):
        start = ftyp_pos - 4
        end = mp4_end(data, start)
        if end:
            found.append((start, end, "mp4", "video", "raw MP4/MOV signature"))

    found.sort(key=lambda item: (item[0], item[1]))

    filtered = []
    occupied_until = -1
    for item in found:
        start, end, *_ = item
        if start < occupied_until:
            continue
        filtered.append(item)
        occupied_until = end

    return filtered


class AssetExtractor:
    def __init__(self, theme: Path, output: Path):
        self.theme = theme
        self.output = output
        self.assets = []
        self.hashes = set()
        self.images = 0
        self.videos = 0
        self.duplicates = 0

    def write_asset(
        self,
        blob: bytes,
        ext: str,
        kind: str,
        source: str,
        original_name: str | None = None,
        offset: int | None = None,
        note: str | None = None,
    ):
        digest = sha256(blob)
        if digest in self.hashes:
            self.duplicates += 1
            return

        self.hashes.add(digest)

        if kind == "image":
            self.images += 1
            index = self.images
            folder = self.output / "images"
        else:
            self.videos += 1
            index = self.videos
            folder = self.output / "videos"

        folder.mkdir(parents=True, exist_ok=True)

        fallback = f"offset_{offset}" if offset is not None else f"{kind}_{index:04d}"
        stem = safe_stem(original_name or "", fallback)
        path = folder / f"{kind}_{index:04d}_{stem}.{ext}"

        path.write_bytes(blob)

        self.assets.append(
            {
                "path": str(path.relative_to(self.output)),
                "kind": kind,
                "extension": ext,
                "bytes": len(blob),
                "sha256": digest,
                "source": source,
                "original_name": original_name,
                "offset": offset,
                "note": note,
            }
        )

    def scan_raw(self, data: bytes, source: str):
        for start, end, ext, kind, note in raw_candidates(data):
            self.write_asset(
                data[start:end],
                ext,
                kind,
                source,
                offset=start,
                note=note,
            )

    def scan_data_urls(self, data: bytes, source: str):
        text = data.decode("utf-8", errors="ignore")
        pattern = re.compile(
            r"data:(image/(?:png|jpe?g|webp|gif|bmp)|video/(?:mp4|webm)|video/quicktime);base64,([A-Za-z0-9+/=]+)",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            mime = match.group(1).lower()
            encoded = match.group(2)
            ext = MIME_EXT.get(mime)
            if not ext:
                continue

            try:
                blob = base64.b64decode(encoded, validate=True)
            except Exception:
                continue

            kind = EXT_KIND.get(ext)
            if kind:
                self.write_asset(blob, ext, kind, source, note="base64 data URL")

    def scan_zip(self) -> bool:
        if not zipfile.is_zipfile(self.theme):
            return False

        with zipfile.ZipFile(self.theme) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue

                name = info.filename
                ext = Path(name).suffix.lower().lstrip(".")
                data = archive.read(info)

                if ext == "jpeg":
                    ext = "jpg"

                if ext in EXT_KIND:
                    self.write_asset(
                        data,
                        ext,
                        EXT_KIND[ext],
                        "zip entry",
                        original_name=name,
                        note="media file inside zip-like theme",
                    )

                self.scan_data_urls(data, f"zip:{name}")
                self.scan_raw(data, f"zip:{name}")

        return True

    def run(self):
        data = self.theme.read_bytes()

        was_zip = self.scan_zip()
        self.scan_data_urls(data, "root")
        self.scan_raw(data, "root")

        manifest = {
            "input": str(self.theme),
            "input_bytes": len(data),
            "input_sha256": sha256(data),
            "was_zip": was_zip,
            "summary": {
                "images": self.images,
                "videos": self.videos,
                "total_assets": self.images + self.videos,
                "duplicates_skipped": self.duplicates,
            },
            "assets": sorted(self.assets, key=lambda item: item["path"]),
        }

        (self.output / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return manifest


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract embedded image/video assets from Windows .turtheme files."
    )
    parser.add_argument("theme", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.theme.is_file():
        print(f"Input theme not found: {args.theme}", file=sys.stderr)
        return 2

    if args.output.exists():
        if args.overwrite:
            shutil.rmtree(args.output)
        elif any(args.output.iterdir()):
            print(f"Output directory already exists and is not empty: {args.output}", file=sys.stderr)
            return 2

    args.output.mkdir(parents=True, exist_ok=True)

    manifest = AssetExtractor(args.theme, args.output).run()
    summary = manifest["summary"]

    print(f"Extracted assets to: {args.output}")
    print(f"Images: {summary['images']}")
    print(f"Videos: {summary['videos']}")
    print(f"Total:  {summary['total_assets']}")
    print(f"Manifest: {args.output / 'manifest.json'}")

    if summary["total_assets"] == 0:
        print(
            "No assets found. The theme may be compressed, encrypted, or use an unsupported container.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
