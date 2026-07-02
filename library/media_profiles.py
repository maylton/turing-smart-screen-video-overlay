"""Reusable media conversion profiles derived from display and theme configuration."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from ruamel.yaml import YAML

    def _load_yaml(path: Path) -> dict[str, Any]:
        parser = YAML(typ="safe")
        with path.open("r", encoding="utf-8") as stream:
            return parser.load(stream) or {}
except ImportError:
    import yaml

    def _load_yaml(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream) or {}


DISPLAY_SIZE_RESOLUTIONS: dict[str, tuple[int, int]] = {
    '0.96"': (80, 160),
    '2.1"': (480, 480),
    '2.8"': (480, 480),
    '3.5"': (320, 480),
    '4.6"': (320, 960),
    '5"': (480, 800),
    '5.2"': (720, 1280),
    '8"': (800, 1280),
    '8.8"': (480, 1920),
    '9.2"': (480, 1920),
    '12.3"': (720, 1920),
}


@dataclass(frozen=True)
class DisplayProfile:
    id: str
    label: str
    width: int
    height: int
    display_size: str
    orientation: str
    revision: str
    encoder: str = "libx264"
    codec: str = "h264"
    pixel_format: str = "yuv420p"
    fps_presets: tuple[int, ...] = (24, 30)
    upload_supported: bool = False
    hardware_validated: bool = False
    source: str = "preset"
    firmware_note: str = ""
    estimate_bpp: float = 0.075

    def validated(self) -> "DisplayProfile":
        if not self.id or not self.label:
            raise ValueError("Profile id and label are required.")
        if not 2 <= int(self.width) <= 4096 or not 2 <= int(self.height) <= 4096:
            raise ValueError("Profile dimensions must be between 2 and 4096.")
        if self.encoder != "libx264" or self.codec != "h264":
            raise ValueError("Only the H.264/libx264 profile is currently supported.")
        if self.pixel_format != "yuv420p":
            raise ValueError("Only yuv420p output is currently supported.")
        fps = tuple(sorted({int(value) for value in self.fps_presets}))
        if not fps or any(value not in {24, 30} for value in fps):
            raise ValueError("Profiles may currently use only 24 or 30 FPS.")
        if not math.isfinite(self.estimate_bpp) or self.estimate_bpp <= 0:
            raise ValueError("Profile estimate_bpp must be positive.")
        return DisplayProfile(
            id=self.id,
            label=self.label,
            width=int(self.width),
            height=int(self.height),
            display_size=self.display_size,
            orientation=self.orientation,
            revision=self.revision,
            encoder=self.encoder,
            codec=self.codec,
            pixel_format=self.pixel_format,
            fps_presets=fps,
            upload_supported=bool(self.upload_supported),
            hardware_validated=bool(self.hardware_validated),
            source=self.source,
            firmware_note=self.firmware_note,
            estimate_bpp=float(self.estimate_bpp),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self.validated())
        data["fps_presets"] = list(self.fps_presets)
        data["aspect_ratio"] = self.width / self.height
        return data


def oriented_dimensions(
    display_size: str,
    orientation: str,
) -> tuple[int, int]:
    width, height = DISPLAY_SIZE_RESOLUTIONS.get(display_size, (320, 480))
    normalized = str(orientation or "portrait").strip().lower()
    if normalized == "landscape":
        return height, width
    return width, height


def _native_capability(
    revision: str,
    display_size: str,
    width: int,
    height: int,
) -> tuple[bool, bool, str]:
    if revision == "C" and display_size == '2.1"' and (width, height) == (480, 480):
        return (
            True,
            True,
            "Native H.264 upload is physically validated on Rev. C 2.1-inch ROM 88.",
        )
    if revision == "C":
        return (
            False,
            False,
            "Rev. C conversion is available for preview, but native upload is not "
            "enabled because this size has not been hardware validated.",
        )
    return (
        False,
        False,
        "This revision has no validated native-video upload profile in this fork.",
    )


def load_active_theme_profile(
    root: str | Path,
) -> DisplayProfile:
    project = Path(root).expanduser().resolve()
    config_path = project / "config.yaml"
    config = _load_yaml(config_path)
    theme_name = str((config.get("config") or {}).get("THEME") or "").strip()
    if not theme_name:
        raise ValueError(f"No active theme is configured in {config_path}.")
    theme_path = project / "res" / "themes" / theme_name / "theme.yaml"
    if not theme_path.is_file():
        raise FileNotFoundError(f"Active theme was not found: {theme_path}")
    theme = _load_yaml(theme_path)
    display = theme.get("display") or {}
    display_size = str(display.get("DISPLAY_SIZE") or '3.5"')
    orientation = str(display.get("DISPLAY_ORIENTATION") or "portrait").lower()
    width, height = oriented_dimensions(display_size, orientation)
    revision = str((config.get("display") or {}).get("REVISION") or "UNKNOWN").upper()
    upload_supported, validated, note = _native_capability(
        revision,
        display_size,
        width,
        height,
    )
    return DisplayProfile(
        id="active-theme",
        label=f"Active theme — {theme_name} ({width}×{height})",
        width=width,
        height=height,
        display_size=display_size,
        orientation=orientation,
        revision=revision,
        upload_supported=upload_supported,
        hardware_validated=validated,
        source="active-theme",
        firmware_note=note,
    ).validated()


def preset_profiles() -> list[DisplayProfile]:
    return [
        DisplayProfile(
            id="square-480-preview",
            label="Square preview — 480×480",
            width=480,
            height=480,
            display_size='2.1"',
            orientation="landscape",
            revision="UNVERIFIED",
            firmware_note=(
                "Reusable square conversion preset. Native upload is enabled only "
                "through a matching validated active-theme profile."
            ),
        ),
        DisplayProfile(
            id="portrait-320x480-preview",
            label="Portrait preview — 320×480",
            width=320,
            height=480,
            display_size='3.5"',
            orientation="portrait",
            revision="UNVERIFIED",
            firmware_note="Conversion and preview only; native upload is disabled.",
        ),
        DisplayProfile(
            id="landscape-480x320-preview",
            label="Landscape preview — 480×320",
            width=480,
            height=320,
            display_size='3.5"',
            orientation="landscape",
            revision="UNVERIFIED",
            firmware_note="Conversion and preview only; native upload is disabled.",
        ),
        DisplayProfile(
            id="portrait-480x800-preview",
            label="Portrait preview — 480×800",
            width=480,
            height=800,
            display_size='5"',
            orientation="portrait",
            revision="UNVERIFIED",
            firmware_note="Conversion and preview only; native upload is disabled.",
        ),
        DisplayProfile(
            id="landscape-800x480-preview",
            label="Landscape preview — 800×480",
            width=800,
            height=480,
            display_size='5"',
            orientation="landscape",
            revision="UNVERIFIED",
            firmware_note="Conversion and preview only; native upload is disabled.",
        ),
        DisplayProfile(
            id="ultrawide-1920x480-preview",
            label="Ultrawide preview — 1920×480",
            width=1920,
            height=480,
            display_size='8.8"',
            orientation="landscape",
            revision="UNVERIFIED",
            firmware_note="Conversion and preview only; native upload is disabled.",
            estimate_bpp=0.06,
        ),
    ]


def list_profiles(root: str | Path) -> list[DisplayProfile]:
    profiles = [load_active_theme_profile(root), *preset_profiles()]
    seen: set[str] = set()
    result: list[DisplayProfile] = []
    for profile in profiles:
        validated = profile.validated()
        if validated.id in seen:
            continue
        seen.add(validated.id)
        result.append(validated)
    return result


def get_profile(profile_id: str, root: str | Path) -> DisplayProfile:
    normalized = str(profile_id or "active-theme").strip()
    for profile in list_profiles(root):
        if profile.id == normalized:
            return profile
    available = ", ".join(profile.id for profile in list_profiles(root))
    raise KeyError(f"Unknown media profile {normalized!r}. Available: {available}")


def estimate_output_size(
    profile: DisplayProfile,
    duration: float,
    fps: int,
    crf: int,
) -> dict[str, Any]:
    profile = profile.validated()
    duration = max(0.0, float(duration))
    fps = int(fps)
    crf = int(crf)
    quality_factor = min(3.2, max(0.30, 2 ** ((20 - crf) / 6)))
    middle = (
        profile.width
        * profile.height
        * fps
        * duration
        * profile.estimate_bpp
        * quality_factor
        / 8
    )
    middle += max(32_768, middle * 0.02)
    low = max(1, round(middle * 0.60))
    high = max(low, round(middle * 1.55))
    return {
        "duration": duration,
        "fps": fps,
        "crf": crf,
        "low_bytes": low,
        "estimated_bytes": round(middle),
        "high_bytes": high,
    }


def format_bytes(value: int | float) -> str:
    amount = float(value)
    units = ("B", "KiB", "MiB", "GiB")
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} GiB"
