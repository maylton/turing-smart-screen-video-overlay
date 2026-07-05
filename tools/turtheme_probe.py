#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Inspect original Turing .turtheme files for convertible metadata."""

from __future__ import annotations

import argparse
import json
import re
import string
import zipfile
from pathlib import Path


KEYWORDS = (
    "cpu", "gpu", "ram", "memory", "temp", "temperature", "fan", "fps",
    "time", "date", "clock", "text", "font", "color", "colour",
    "x", "y", "width", "height", "rotate", "rotation", "align",
    "image", "background", "overlay", "sensor", "value", "percent",
    "usage", "network", "upload", "download", "disk", "hdd", "ssd",
)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-._")
    return value or "theme"


def printable_ascii_strings(data: bytes, min_length: int = 4) -> list[str]:
    allowed = set(bytes(string.printable, "ascii"))
    result: list[str] = []
    buffer = bytearray()

    for byte in data:
        if byte in allowed and byte not in {0x0b, 0x0c}:
            buffer.append(byte)
        else:
            if len(buffer) >= min_length:
                text = buffer.decode("ascii", errors="ignore").strip()
                if text:
                    result.append(text)
            buffer.clear()

    if len(buffer) >= min_length:
        text = buffer.decode("ascii", errors="ignore").strip()
        if text:
            result.append(text)

    return result


def printable_utf16le_strings(data: bytes, min_length: int = 4) -> list[str]:
    try:
        decoded = data.decode("utf-16le", errors="ignore")
    except Exception:
        return []

    pieces = re.split(r"[^\x20-\x7EÀ-ÿ]+", decoded)
    return [piece.strip() for piece in pieces if len(piece.strip()) >= min_length]


def interesting_strings(strings: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for item in strings:
        lower = item.lower()
        if any(keyword in lower for keyword in KEYWORDS):
            if item not in seen:
                found.append(item)
                seen.add(item)

    return found


def signature_offsets(data: bytes) -> dict[str, list[int]]:
    signatures = {
        "zip_pk": b"PK\x03\x04",
        "png": b"\x89PNG\r\n\x1a\n",
        "jpg": b"\xff\xd8\xff",
        "json_object": b"{",
        "json_array": b"[",
        "mp4_ftyp": b"ftyp",
    }

    output: dict[str, list[int]] = {}

    for name, signature in signatures.items():
        offsets = []
        index = 0

        while True:
            found = data.find(signature, index)
            if found < 0:
                break
            offsets.append(found)
            index = found + 1
            if len(offsets) >= 50:
                break

        if offsets:
            output[name] = offsets

    return output


def extract_json_like_candidates(text: str, limit: int = 80) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r"[\{\[]", text):
        start = match.start()
        chunk = text[start:start + 4000]

        if not any(keyword in chunk.lower() for keyword in KEYWORDS):
            continue

        cleaned = re.sub(r"\s+", " ", chunk).strip()
        cleaned = cleaned[:1200]

        if cleaned not in seen:
            candidates.append(cleaned)
            seen.add(cleaned)

        if len(candidates) >= limit:
            break

    return candidates


def inspect_zip(path: Path) -> dict[str, object]:
    members = []

    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            members.append(
                {
                    "filename": info.filename,
                    "size": info.file_size,
                    "compressed": info.compress_size,
                }
            )

    return {
        "is_zip": True,
        "members": members,
    }


def write_lines(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect .turtheme files for metadata useful for conversion."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("turtheme-inspect"),
    )
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    out_dir = args.output_dir / slugify(source.stem)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = source.read_bytes()

    ascii_strings = printable_ascii_strings(data)
    utf16_strings = printable_utf16le_strings(data)
    all_strings = ascii_strings + utf16_strings
    interesting = interesting_strings(all_strings)

    decoded_latin = data.decode("latin-1", errors="ignore")
    decoded_utf16 = data.decode("utf-16le", errors="ignore")
    json_candidates = (
        extract_json_like_candidates(decoded_latin)
        + extract_json_like_candidates(decoded_utf16)
    )

    report = {
        "source": str(source),
        "size_bytes": source.stat().st_size,
        "is_zip": zipfile.is_zipfile(source),
        "signature_offsets": signature_offsets(data),
        "string_counts": {
            "ascii": len(ascii_strings),
            "utf16le": len(utf16_strings),
            "interesting": len(interesting),
            "json_like_candidates": len(json_candidates),
        },
    }

    if zipfile.is_zipfile(source):
        report["zip"] = inspect_zip(source)

    (out_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    write_lines(out_dir / "strings_ascii.txt", ascii_strings[:5000])
    write_lines(out_dir / "strings_utf16le.txt", utf16_strings[:5000])
    write_lines(out_dir / "metadata_candidates.txt", interesting[:1000])
    write_lines(out_dir / "json_like_candidates.txt", json_candidates[:200])

    summary = [
        f"Source: {source}",
        f"Output: {out_dir}",
        f"Size: {source.stat().st_size} bytes",
        f"ZIP: {zipfile.is_zipfile(source)}",
        "",
        "Signature offsets:",
        json.dumps(report["signature_offsets"], indent=2, ensure_ascii=False),
        "",
        "String counts:",
        json.dumps(report["string_counts"], indent=2, ensure_ascii=False),
        "",
        "Files written:",
        "  report.json",
        "  strings_ascii.txt",
        "  strings_utf16le.txt",
        "  metadata_candidates.txt",
        "  json_like_candidates.txt",
    ]

    write_lines(out_dir / "report.txt", summary)
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
