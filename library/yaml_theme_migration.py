# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only compatibility analysis for migrating legacy YAML themes to HTML."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import yaml

from library.media_profiles import DISPLAY_SIZE_RESOLUTIONS, oriented_dimensions


class YamlThemeMigrationError(RuntimeError):
    """Raised when a legacy theme cannot be analyzed safely."""


@dataclass(frozen=True)
class YamlOverlayCandidate:
    path: tuple[str, ...]
    kind: str
    visible: bool
    x: int
    y: int
    width: int
    height: int
    binding: Optional[str]
    formatter: Optional[str]
    status: str
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = ".".join(self.path)
        return payload


@dataclass(frozen=True)
class YamlThemeMigrationReport:
    source: Path
    theme_name: str
    display_size: str
    orientation: str
    width: int
    height: int
    display_source: str
    native_video: bool
    native_video_path: str
    static_images: int
    static_texts: int
    overlays: tuple[YamlOverlayCandidate, ...]
    fonts: tuple[str, ...]
    assets: tuple[str, ...]
    missing_assets: tuple[str, ...]
    warnings: tuple[str, ...]
    readiness: str

    @property
    def visible_overlays(self) -> tuple[YamlOverlayCandidate, ...]:
        return tuple(overlay for overlay in self.overlays if overlay.visible)

    @property
    def ready_overlays(self) -> tuple[YamlOverlayCandidate, ...]:
        return tuple(
            overlay
            for overlay in self.visible_overlays
            if overlay.status == "ready"
        )

    def as_dict(self) -> dict[str, Any]:
        visible = self.visible_overlays
        ready = self.ready_overlays
        return {
            "source": str(self.source),
            "themeName": self.theme_name,
            "display": {
                "size": self.display_size,
                "orientation": self.orientation,
                "width": self.width,
                "height": self.height,
                "source": self.display_source,
            },
            "nativeVideo": {
                "enabled": self.native_video,
                "path": self.native_video_path,
            },
            "static": {
                "images": self.static_images,
                "texts": self.static_texts,
            },
            "summary": {
                "overlays": len(self.overlays),
                "visibleOverlays": len(visible),
                "readyOverlays": len(ready),
                "needsAssistance": len(visible) - len(ready),
                "readiness": self.readiness,
            },
            "overlays": [overlay.as_dict() for overlay in self.overlays],
            "fonts": list(self.fonts),
            "assets": list(self.assets),
            "missingAssets": list(self.missing_assets),
            "warnings": list(self.warnings),
        }


def _mapping_at(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    wanted = key.casefold()
    for candidate, value in document.items():
        if str(candidate).casefold() == wanted and isinstance(value, Mapping):
            return value
    return {}


def _truthy(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().strip("\"'").casefold() in {
            "1",
            "true",
            "yes",
            "on",
            "enabled",
            "show",
        }
    return bool(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _iter_mappings(
    node: Any,
    path: tuple[str, ...] = (),
) -> Iterable[tuple[tuple[str, ...], Mapping[str, Any]]]:
    if not isinstance(node, Mapping):
        return
    for key, value in node.items():
        child_path = (*path, str(key))
        if isinstance(value, Mapping):
            yield child_path, value
            yield from _iter_mappings(value, child_path)


def _candidate_kind(path: tuple[str, ...]) -> str:
    leaf = path[-1].upper()
    if leaf == "GRAPH":
        return "bar"
    if leaf == "RADIAL":
        return "radial"
    if leaf == "LINE_GRAPH":
        return "history"
    return "text"


def _metric_tokens(path: tuple[str, ...]) -> tuple[str, ...]:
    tokens = tuple(str(part).upper() for part in path)
    if tokens and tokens[0] == "STATS":
        tokens = tokens[1:]
    if tokens and tokens[-1] in {"TEXT", "GRAPH", "RADIAL", "LINE_GRAPH"}:
        tokens = tokens[:-1]
    return tokens


def _binding_for_path(
    path: tuple[str, ...],
    kind: str,
) -> tuple[Optional[str], Optional[str], str]:
    tokens = _metric_tokens(path)
    joined = ".".join(tokens)
    formatter = "bar-percent" if kind == "bar" else "text"

    if not tokens:
        return None, None, "Metric path is empty."

    if tokens[0] == "DATE":
        if any(token in tokens for token in ("HOUR", "TIME")):
            return "system.time", "time", ""
        return "$timestamp", "date", ""

    if tokens[0] == "CPU":
        if "PERCENTAGE" in tokens:
            return "cpu.usage", formatter if kind == "bar" else "percent", ""
        if "TEMPERATURE" in tokens:
            return "cpu.temperature", formatter if kind == "bar" else "temperature", ""
        if "FREQUENCY" in tokens:
            return "cpu.frequency", formatter if kind == "bar" else "gigahertz", ""
        if "LOAD" in tokens:
            indexes = {"ONE": 0, "FIVE": 1, "FIFTEEN": 2}
            index = next((value for token, value in indexes.items() if token in tokens), 0)
            return f"cpu.load.{index}", formatter if kind == "bar" else "load", ""
        if "FAN_SPEED" in tokens or "FAN" in tokens:
            return None, None, "The HTML sensor snapshot does not expose CPU fan speed yet."

    if tokens[0] == "GPU":
        if "PERCENTAGE" in tokens:
            return "gpu.usage", formatter if kind == "bar" else "percent", ""
        if "TEMPERATURE" in tokens:
            return "gpu.temperature", formatter if kind == "bar" else "temperature", ""
        if "FREQUENCY" in tokens:
            return (
                "gpu.frequency",
                formatter if kind == "bar" else "gigahertz-from-megahertz",
                "",
            )
        if "FPS" in tokens:
            return "gpu.fps", formatter if kind == "bar" else "fps", ""
        if "FAN_SPEED" in tokens or "FAN" in tokens:
            return "gpu.fan", formatter if kind == "bar" else "percent", ""
        if "MEMORY_USED" in tokens:
            return "gpu.vramUsed", formatter if kind == "bar" else "gigabytes", ""
        if "MEMORY_TOTAL" in tokens:
            return "gpu.vramTotal", formatter if kind == "bar" else "gigabytes", ""
        if "MEMORY_PERCENT" in tokens:
            return "gpu.vramUsage", formatter if kind == "bar" else "percent", ""
        if "MEMORY" in tokens:
            if kind == "text":
                return "gpu.vramUsed", "gigabytes", ""
            return "gpu.vramUsage", formatter, ""

    if tokens[0] == "MEMORY":
        if "SWAP" in tokens:
            return "memory.swapUsage", formatter if kind == "bar" else "percent", ""
        if "USED" in tokens:
            return "memory.used", formatter if kind == "bar" else "gigabytes", ""
        if "FREE" in tokens or "AVAILABLE" in tokens:
            return "memory.available", formatter if kind == "bar" else "gigabytes", ""
        if "TOTAL" in tokens:
            return "memory.total", formatter if kind == "bar" else "gigabytes", ""
        return "memory.usage", formatter if kind == "bar" else "percent", ""

    if tokens[0] == "DISK":
        if "FREE" in tokens:
            return "disk.free", formatter if kind == "bar" else "gigabytes", ""
        if "TOTAL" in tokens:
            return "disk.total", formatter if kind == "bar" else "gigabytes", ""
        if kind == "text" and tokens[-1] == "USED":
            return "disk.used", "gigabytes", ""
        if "TEXT" in tokens and "USED" in tokens:
            return "disk.used", "gigabytes", ""
        return "disk.usage", formatter if kind == "bar" else "percent", ""

    if tokens[0] == "NET":
        if "DOWNLOADED" in tokens:
            return "network.downloaded", "bytes", ""
        if "UPLOADED" in tokens:
            return "network.uploaded", "bytes", ""
        if "DOWNLOAD" in tokens:
            return "network.download", "megabytes-per-second", ""
        if "UPLOAD" in tokens:
            return "network.upload", "megabytes-per-second", ""

    if tokens[0] == "WEATHER":
        if "TEMPERATURE_FELT" in tokens:
            return "weather.feelsLike", "temperature", ""
        if "TEMPERATURE" in tokens:
            return "weather.temperature", "temperature", ""
        if "WEATHER_DESCRIPTION" in tokens or "DESCRIPTION" in tokens:
            return "weather.description", "text", ""
        if "HUMIDITY" in tokens:
            return "weather.humidity", "percent", ""
        if "UPDATE_TIME" in tokens:
            return "weather.updatedAt", "text", ""

    if tokens[0] == "UPTIME":
        return "system.uptime", "duration", ""
    if tokens[0] == "PING":
        return None, None, "The HTML sensor snapshot does not expose ping yet."
    if tokens[0] == "CUSTOM":
        return None, None, f"Custom sensor {joined} requires a data adapter."
    return None, None, f"No HTML sensor binding is known for {joined}."


def _bar_has_supported_range(node: Mapping[str, Any]) -> bool:
    minimum = _safe_int(node.get("MIN_VALUE"), 0)
    maximum = _safe_int(node.get("MAX_VALUE"), 100)
    return minimum == 0 and maximum == 100


def _candidate_dimensions(
    node: Mapping[str, Any],
    *,
    kind: str,
    canvas_width: int,
    canvas_height: int,
) -> tuple[int, int, int, int]:
    x = max(0, _safe_int(node.get("X")))
    y = max(0, _safe_int(node.get("Y")))
    font_size = max(6, _safe_int(node.get("FONT_SIZE"), 16))
    if kind == "radial":
        radius = max(1, _safe_int(node.get("RADIUS"), 30))
        default_width = default_height = radius * 2
    elif kind == "bar":
        default_width, default_height = 120, 12
    else:
        default_width, default_height = max(48, font_size * 8), max(20, round(font_size * 1.5))
    width = max(1, _safe_int(node.get("WIDTH"), default_width))
    height = max(1, _safe_int(node.get("HEIGHT"), default_height))
    if canvas_width > 0:
        width = min(width, max(1, canvas_width - min(x, canvas_width - 1)))
    if canvas_height > 0:
        height = min(height, max(1, canvas_height - min(y, canvas_height - 1)))
    return x, y, width, height


def _infer_geometry(document: Mapping[str, Any]) -> tuple[int, int]:
    width = height = 0
    for _path, node in _iter_mappings(document):
        if not {"X", "Y", "WIDTH", "HEIGHT"}.issubset(node):
            continue
        width = max(width, _safe_int(node.get("X")) + _safe_int(node.get("WIDTH")))
        height = max(height, _safe_int(node.get("Y")) + _safe_int(node.get("HEIGHT")))
    return width, height


def _display_geometry(
    document: Mapping[str, Any],
) -> tuple[str, str, int, int, str, list[str]]:
    display = _mapping_at(document, "display")
    display_size = str(display.get("DISPLAY_SIZE") or "").strip()
    orientation = str(display.get("DISPLAY_ORIENTATION") or "portrait").strip().lower()
    warnings: list[str] = []
    if display_size in DISPLAY_SIZE_RESOLUTIONS:
        width, height = oriented_dimensions(display_size, orientation)
        return display_size, orientation, width, height, "display-size", warnings
    width, height = _infer_geometry(document)
    if width > 0 and height > 0:
        warnings.append("Display dimensions were inferred from theme element geometry.")
        return display_size, orientation, width, height, "geometry", warnings
    warnings.append("Display dimensions could not be determined safely.")
    return display_size, orientation, 0, 0, "unknown", warnings


def _resolve_theme_file(source: Path) -> Path:
    path = Path(source).expanduser().resolve()
    if path.is_dir():
        for name in ("theme.yaml", "theme.yml"):
            candidate = path / name
            if candidate.is_file():
                return candidate
        raise YamlThemeMigrationError(f"Theme directory has no theme.yaml/theme.yml: {path}")
    if not path.is_file():
        raise YamlThemeMigrationError(f"Theme YAML does not exist: {path}")
    if path.suffix.casefold() not in {".yaml", ".yml"}:
        raise YamlThemeMigrationError(f"Theme source must be YAML: {path}")
    return path


def _project_root(theme_file: Path) -> Path:
    for parent in theme_file.parents:
        if (parent / "res" / "fonts").is_dir():
            return parent
    return theme_file.parent


def _references(
    document: Mapping[str, Any],
    theme_file: Path,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], list[str]]:
    fonts: set[str] = set()
    assets: set[str] = set()
    missing: set[str] = set()
    warnings: list[str] = []
    project = _project_root(theme_file)
    theme_dir = theme_file.parent
    for _path, node in _iter_mappings(document):
        for key in ("FONT", "AXIS_FONT"):
            raw = str(node.get(key) or "").strip().strip("\"'")
            if not raw:
                continue
            fonts.add(raw)
            if not any(
                candidate.is_file()
                for candidate in (theme_dir / raw, project / "res" / "fonts" / raw)
            ):
                missing.add(raw)
        for key in ("PATH", "BACKGROUND_IMAGE"):
            raw = str(node.get(key) or "").strip().strip("\"'")
            if not raw:
                continue
            assets.add(raw)
            if raw.startswith("/mnt/SDCARD/"):
                warnings.append(f"Device-only media path cannot be packaged directly: {raw}")
                continue
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = theme_dir / raw
            if not candidate.is_file():
                missing.add(raw)
    return (
        tuple(sorted(fonts, key=str.casefold)),
        tuple(sorted(assets, key=str.casefold)),
        tuple(sorted(missing, key=str.casefold)),
        warnings,
    )


def analyze_yaml_theme(source: str | Path) -> YamlThemeMigrationReport:
    """Analyze one YAML theme without modifying the source or its assets."""

    theme_file = _resolve_theme_file(Path(source))
    try:
        document = yaml.safe_load(theme_file.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise YamlThemeMigrationError(f"Could not parse {theme_file}: {exc}") from exc
    if not isinstance(document, Mapping):
        raise YamlThemeMigrationError(f"Theme YAML must contain an object: {theme_file}")

    display_size, orientation, width, height, display_source, warnings = _display_geometry(document)
    stats = _mapping_at(document, "STATS")
    overlays: list[YamlOverlayCandidate] = []
    network_interface_collapsed = False
    for path, node in _iter_mappings(stats, ("STATS",)):
        if not {"X", "Y"}.issubset(node):
            continue
        if "PATH" in node and not any(
            key in node
            for key in ("FONT", "FONT_SIZE", "BAR_COLOR", "LINE_COLOR", "RADIUS")
        ):
            continue
        kind = _candidate_kind(path)
        visible = _truthy(node.get("SHOW"), True)
        binding, formatter, note = _binding_for_path(path, kind)
        status = "ready"
        if not visible:
            status = "hidden"
        elif kind in {"radial", "history"}:
            status = "needs-component"
            note = f"The {kind} renderer is not implemented in overlays.json yet."
        elif binding is None:
            status = "needs-binding"
        elif kind == "bar" and not _bar_has_supported_range(node):
            status = "needs-range"
            note = "The bar uses a range other than 0-100."
        if len(path) > 2 and path[1].upper() == "NET" and any(
            part.upper() in {"ETH", "WLO"} for part in path
        ):
            network_interface_collapsed = True
        x, y, candidate_width, candidate_height = _candidate_dimensions(
            node,
            kind=kind,
            canvas_width=width,
            canvas_height=height,
        )
        overlays.append(
            YamlOverlayCandidate(
                path=path,
                kind=kind,
                visible=visible,
                x=x,
                y=y,
                width=candidate_width,
                height=candidate_height,
                binding=binding,
                formatter=formatter,
                status=status,
                note=note,
            )
        )

    if network_interface_collapsed:
        warnings.append(
            "Ethernet/Wi-Fi widgets currently map to the single selected HTML network interface."
        )

    video = _mapping_at(document, "video")
    native_video = _truthy(video.get("ENABLED"), False) and str(
        video.get("MODE") or ""
    ).strip().casefold() == "native"
    native_video_path = str(video.get("PATH") or "").strip().strip("\"'")
    static_images = sum(
        1
        for node in _mapping_at(document, "static_images").values()
        if isinstance(node, Mapping) and _truthy(node.get("SHOW"), True)
    )
    static_texts = sum(
        1
        for node in _mapping_at(document, "static_text").values()
        if isinstance(node, Mapping) and _truthy(node.get("SHOW"), True)
    )
    fonts, assets, missing_assets, reference_warnings = _references(document, theme_file)
    warnings.extend(reference_warnings)
    if missing_assets:
        warnings.append(f"{len(missing_assets)} referenced local asset(s) could not be resolved.")

    visible = [overlay for overlay in overlays if overlay.visible]
    non_ready = [overlay for overlay in visible if overlay.status != "ready"]
    if display_source == "unknown" or any(
        overlay.status == "needs-binding" and len(overlay.path) > 1 and overlay.path[1].upper() == "CUSTOM"
        for overlay in non_ready
    ):
        readiness = "manual"
    elif non_ready:
        readiness = "assisted"
    else:
        readiness = "automatic"

    return YamlThemeMigrationReport(
        source=theme_file,
        theme_name=theme_file.parent.name,
        display_size=display_size,
        orientation=orientation,
        width=width,
        height=height,
        display_source=display_source,
        native_video=native_video,
        native_video_path=native_video_path,
        static_images=static_images,
        static_texts=static_texts,
        overlays=tuple(overlays),
        fonts=fonts,
        assets=assets,
        missing_assets=missing_assets,
        warnings=tuple(dict.fromkeys(warnings)),
        readiness=readiness,
    )


def format_migration_report(report: YamlThemeMigrationReport) -> str:
    visible = report.visible_overlays
    status_counts: dict[str, int] = {}
    for overlay in visible:
        status_counts[overlay.status] = status_counts.get(overlay.status, 0) + 1
    statuses = ", ".join(
        f"{status}={count}" for status, count in sorted(status_counts.items())
    ) or "none"
    lines = [
        f"Theme: {report.theme_name}",
        f"Source: {report.source}",
        f"Display: {report.width}x{report.height} ({report.display_source})",
        f"Readiness: {report.readiness}",
        f"Visible overlays: {len(visible)} ({statuses})",
        f"Static layers: images={report.static_images}, texts={report.static_texts}",
        f"Native video: {'yes' if report.native_video else 'no'}",
        f"Missing assets: {len(report.missing_assets)}",
    ]
    if report.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in report.warnings)
    return "\n".join(lines)
