# SPDX-License-Identifier: GPL-3.0-or-later
"""Non-destructive YAML-to-HTML theme draft generation."""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional

import yaml

from library.html_theme_components import (
    HtmlGeneratedWidget,
    render_generated_widget_block,
    render_widget_runtime_script,
)
from library.html_theme_visual_editor import (
    EDITOR_SCHEMA_VERSION,
    EDITOR_STYLESHEET_FILENAME,
    OVERLAY_DOCUMENT_FILENAME,
    OVERLAY_DOCUMENT_FORMAT,
    OVERLAY_DOCUMENT_FORMAT_VERSION,
    HtmlVisualElementStyle,
    render_overlay_document,
    render_visual_stylesheet,
)
from library.theme_engine import ThemeManifest
from library.theme_package import ThemePackageDescriptor, write_theme_package
from library.video_media import MediaProbeError, probe_video
from library.yaml_theme_migration import (
    YamlOverlayCandidate,
    YamlThemeMigrationError,
    YamlThemeMigrationReport,
    analyze_yaml_theme,
)


@dataclass(frozen=True)
class YamlThemeConversionResult:
    source: Path
    output: Path
    packaged: bool
    theme_name: str
    converted: tuple[str, ...]
    skipped: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": str(self.source),
            "output": str(self.output),
            "packaged": self.packaged,
            "themeName": self.theme_name,
            "converted": list(self.converted),
            "skipped": list(self.skipped),
            "warnings": list(self.warnings),
        }


def _mapping_at(document: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    wanted = str(key).casefold()
    for candidate, value in document.items():
        if str(candidate).casefold() == wanted and isinstance(value, Mapping):
            return value
    return {}


def _value_at(document: Mapping[str, Any], path: tuple[str, ...]) -> Mapping[str, Any]:
    value: Any = document
    for part in path:
        if not isinstance(value, Mapping):
            return {}
        if part in value:
            value = value[part]
            continue
        folded = str(part).casefold()
        value = next(
            (
                item
                for key, item in value.items()
                if str(key).casefold() == folded
            ),
            None,
        )
    return value if isinstance(value, Mapping) else {}


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


def _slug(value: str, fallback: str = "theme") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")
    return normalized[:80] or fallback


def converted_theme_name(source_name: str) -> str:
    return _slug(str(source_name) + "-html")


def _overlay_id(candidate: YamlOverlayCandidate, used: set[str]) -> str:
    base = "yaml-" + _slug("-".join(candidate.path[1:]), "overlay")
    value = base[:58]
    suffix = 1
    while value in used:
        suffix += 1
        value = f"{base[:54]}-{suffix}"
    used.add(value)
    return value


def _hex_color(value: Any, default: str = "#ffffff") -> str:
    if isinstance(value, str):
        raw = value.strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
            return raw.casefold()
        parts = [part.strip() for part in raw.split(",")]
    elif isinstance(value, (list, tuple)):
        parts = list(value[:3])
    else:
        return default
    if len(parts) < 3:
        return default
    try:
        channels = [max(0, min(255, int(float(part)))) for part in parts[:3]]
    except (TypeError, ValueError):
        return default
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _font_weight(raw_font: Any) -> int:
    name = str(raw_font or "").casefold()
    if "black" in name or "heavy" in name:
        return 900
    if "extrabold" in name or "extra-bold" in name:
        return 800
    if "bold" in name:
        return 700
    if "semibold" in name or "semi-bold" in name:
        return 600
    if "medium" in name:
        return 500
    if "light" in name:
        return 300
    return 400


def _sample(formatter: str, kind: str) -> str:
    if kind == "bar":
        return "50"
    return {
        "temperature": "49°C",
        "percent": "62%",
        "gigabytes": "14.5 GB",
        "megabytes": "4096 M",
        "gigahertz": "4.70 GHz",
        "gigahertz-from-megahertz": "1.50 GHz",
        "megabytes-per-second": "18.4 MB/s",
        "bytes": "1.2 GB",
        "duration": "12:34:56",
        "fps": "120 FPS",
        "load": "1.25",
        "time": "10:32",
        "date": "02/08/2026",
        "integer": "42",
        "decimal": "42.00",
    }.get(formatter, "--")


def _anchor_position(
    candidate: YamlOverlayCandidate,
    node: Mapping[str, Any],
    report: YamlThemeMigrationReport,
) -> tuple[int, int]:
    x, y = candidate.x, candidate.y
    anchor = str(node.get("ANCHOR") or "").strip().casefold()
    if len(anchor) == 2:
        if anchor[0] == "m":
            x -= candidate.width // 2
        elif anchor[0] == "r":
            x -= candidate.width
        if anchor[1] == "m":
            y -= candidate.height // 2
        elif anchor[1] == "b":
            y -= candidate.height
    return (
        max(0, min(x, max(0, report.width - candidate.width))),
        max(0, min(y, max(0, report.height - candidate.height))),
    )


def _style_from_candidate(
    candidate: YamlOverlayCandidate,
    node: Mapping[str, Any],
    report: YamlThemeMigrationReport,
    element_id: str,
    z_index: int,
) -> HtmlVisualElementStyle:
    kind = candidate.kind
    if kind not in {"text", "bar"} or candidate.binding is None or candidate.formatter is None:
        raise YamlThemeMigrationError(
            f"Overlay is not directly convertible: {'.'.join(candidate.path)}"
        )
    x, y = _anchor_position(candidate, node, report)
    effects = _mapping_at(node, "EFFECTS")
    gradient = _mapping_at(effects, "GRADIENT")
    outline = _mapping_at(effects, "OUTLINE")
    glow = _mapping_at(effects, "GLOW")
    color_key = "BAR_COLOR" if kind == "bar" else "FONT_COLOR"
    color = _hex_color(node.get(color_key), "#ffffff")
    align = str(node.get("ALIGN") or "inherit").strip().casefold()
    if align not in {"left", "center", "right"}:
        align = "inherit"
    direction = str(gradient.get("DIRECTION") or "horizontal").strip().casefold()
    if direction not in {"horizontal", "vertical", "diagonal"}:
        direction = "horizontal"
    return HtmlVisualElementStyle(
        element_id=element_id,
        x=x,
        y=y,
        width=candidate.width,
        height=candidate.height,
        font_size=max(6, min(160, _safe_int(node.get("FONT_SIZE"), 16))),
        color=color,
        font_weight=_font_weight(node.get("FONT")),
        text_align=align,
        opacity=100,
        z_index=z_index,
        visible=True,
        generated_widget=True,
        binding=candidate.binding,
        formatter=candidate.formatter,
        sample=_sample(candidate.formatter, kind),
        element_kind=kind,
        effects_managed=bool(effects),
        gradient_enabled=_truthy(gradient.get("ENABLED"), False),
        gradient_start_color=_hex_color(gradient.get("START_COLOR"), color),
        gradient_end_color=_hex_color(gradient.get("END_COLOR"), color),
        gradient_direction=direction,
        outline_width=max(
            0,
            min(
                8,
                _safe_int(outline.get("WIDTH"), 1)
                if _truthy(outline.get("ENABLED"), False)
                else 0,
            ),
        ),
        outline_color=_hex_color(outline.get("COLOR"), "#000000"),
        glow_radius=max(
            0,
            min(
                40,
                _safe_int(glow.get("BLUR_RADIUS"), 8)
                if _truthy(glow.get("ENABLED"), False)
                else 0,
            ),
        ),
        glow_color=_hex_color(glow.get("COLOR"), color),
    )


def _safe_asset_target(raw_path: str, category: str) -> PurePosixPath:
    source_name = Path(str(raw_path).replace("\\", "/")).name
    stem = _slug(Path(source_name).stem, category)
    suffix = Path(source_name).suffix.casefold()
    digest = hashlib.sha256(str(raw_path).encode("utf-8")).hexdigest()[:8]
    return PurePosixPath("assets", category, f"{stem}-{digest}{suffix}")


def _resolve_local_asset(theme_dir: Path, raw_path: Any) -> Optional[Path]:
    value = str(raw_path or "").strip().strip("\"'")
    if not value or value.startswith("/mnt/SDCARD/") or value.startswith("/root/video/"):
        return None
    path = Path(value).expanduser()
    candidate = path if path.is_absolute() else theme_dir / value
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    return resolved if resolved.is_file() else None


def _copy_asset(
    source: Path,
    root: Path,
    relative: PurePosixPath,
) -> str:
    destination = root.joinpath(*relative.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return relative.as_posix()


def _static_layers(
    document: Mapping[str, Any],
    report: YamlThemeMigrationReport,
    output_root: Path,
) -> tuple[list[str], list[str], list[str]]:
    markup: list[str] = []
    css: list[str] = []
    copied: list[str] = []
    theme_dir = report.source.parent
    image_nodes = _mapping_at(document, "static_images")
    for index, (name, value) in enumerate(image_nodes.items(), 1):
        if not isinstance(value, Mapping) or not _truthy(value.get("SHOW"), True):
            continue
        source = _resolve_local_asset(theme_dir, value.get("PATH"))
        if source is None:
            continue
        target = _safe_asset_target(str(value.get("PATH")), "images")
        relative = _copy_asset(source, output_root, target)
        copied.append(relative)
        element_id = f"static-image-{index}-{_slug(str(name), 'layer')}"
        x = max(0, _safe_int(value.get("X")))
        y = max(0, _safe_int(value.get("Y")))
        width = max(1, _safe_int(value.get("WIDTH"), report.width))
        height = max(1, _safe_int(value.get("HEIGHT"), report.height))
        markup.append(
            f'    <img id="{element_id}" class="static-layer" src="{html.escape(relative, quote=True)}" alt="">'
        )
        css.append(
            f"#{element_id} {{ left: {x}px; top: {y}px; width: {width}px; height: {height}px; }}"
        )

    static_text = _mapping_at(document, "static_text")
    for index, (name, value) in enumerate(static_text.items(), 1):
        if not isinstance(value, Mapping) or not _truthy(value.get("SHOW"), True):
            continue
        text = str(value.get("TEXT") or name)
        element_id = f"static-text-{index}-{_slug(str(name), 'label')}"
        x = max(0, _safe_int(value.get("X")))
        y = max(0, _safe_int(value.get("Y")))
        width = max(1, _safe_int(value.get("WIDTH"), max(80, len(text) * 12)))
        height = max(1, _safe_int(value.get("HEIGHT"), 32))
        size = max(6, min(160, _safe_int(value.get("FONT_SIZE"), 16)))
        color = _hex_color(value.get("FONT_COLOR"), "#ffffff")
        align = str(value.get("ALIGN") or "left").casefold()
        if align not in {"left", "center", "right"}:
            align = "left"
        markup.append(
            f'    <div id="{element_id}" class="static-label">{html.escape(text)}</div>'
        )
        css.append(
            f"#{element_id} {{ left: {x}px; top: {y}px; width: {width}px; height: {height}px; "
            f"font-size: {size}px; color: {color}; text-align: {align}; }}"
        )
    return markup, css, copied


def _font_rules(
    styles_with_nodes: list[tuple[HtmlVisualElementStyle, Mapping[str, Any]]],
    report: YamlThemeMigrationReport,
    output_root: Path,
) -> tuple[list[str], list[str]]:
    rules: list[str] = []
    copied: list[str] = []
    families: dict[str, tuple[str, str]] = {}
    project = next(
        (
            parent
            for parent in report.source.parents
            if (parent / "res" / "fonts").is_dir()
        ),
        report.source.parent,
    )
    for style, node in styles_with_nodes:
        raw = str(node.get("FONT") or "").strip().strip("\"'")
        if not raw:
            continue
        if raw not in families:
            source = _resolve_local_asset(report.source.parent, raw)
            if source is None:
                source = _resolve_local_asset(project / "res" / "fonts", raw)
            if source is None:
                continue
            target = _safe_asset_target(raw, "fonts")
            relative = _copy_asset(source, output_root, target)
            family = f"turing-yaml-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:10]}"
            families[raw] = (family, relative)
            copied.append(relative)
            rules.append(
                f'@font-face {{ font-family: "{family}"; src: url("{relative}"); font-display: swap; }}'
            )
        family, _relative = families[raw]
        rules.append(
            f'[id="{style.element_id}"] {{ font-family: "{family}", sans-serif !important; }}'
        )
    return rules, copied


def _native_video_manifest(
    document: Mapping[str, Any],
    report: YamlThemeMigrationReport,
    output_root: Path,
    warnings: list[str],
) -> Optional[dict[str, Any]]:
    if not report.native_video or (report.width, report.height) != (480, 480):
        return None
    video = _mapping_at(document, "video")
    local_raw = video.get("LOCAL_PATH")
    source = _resolve_local_asset(report.source.parent, local_raw)
    if source is None:
        path_value = str(video.get("PATH") or "")
        if not path_value.startswith(("/mnt/SDCARD/", "/root/video/")):
            source = _resolve_local_asset(report.source.parent, path_value)
    if source is None:
        warnings.append(
            "Native video was not included because the YAML theme has no resolvable local MP4."
        )
        return None
    try:
        probe = probe_video(source)
    except (FileNotFoundError, MediaProbeError) as exc:
        warnings.append(f"Native video could not be probed and was omitted: {exc}")
        return None
    if not probe.compatible or probe.fps is None or probe.duration is None:
        detail = "; ".join(probe.issues) or "missing FPS/duration"
        warnings.append(f"Native video is not display-compatible and was omitted: {detail}")
        return None
    fps = min((24, 30), key=lambda value: abs(value - probe.fps))
    duration = min(60.0, math.floor(probe.duration * fps + 1e-9) / fps)
    if duration <= 0:
        warnings.append("Native video duration is invalid and was omitted.")
        return None
    filename = _slug(source.stem, "background") + ".mp4"
    shutil.copy2(source, output_root / filename)
    if report.static_images or report.static_texts:
        warnings.append(
            "Static YAML layers are visible in HTML preview but are not baked into the copied native video yet."
        )
    return {
        "enabled": True,
        "localPath": filename,
        "devicePath": f"/mnt/SDCARD/video/{filename}",
        "fps": fps,
        "duration": duration,
        "backgroundFrame": 0,
    }


def _load_document(source: Path) -> Mapping[str, Any]:
    try:
        value = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise YamlThemeMigrationError(f"Could not parse {source}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise YamlThemeMigrationError(f"Theme YAML must contain an object: {source}")
    return value


def _write_converted_directory(
    report: YamlThemeMigrationReport,
    output_root: Path,
    *,
    allow_partial: bool,
) -> tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    if report.width <= 0 or report.height <= 0:
        raise YamlThemeMigrationError("Theme display dimensions are unknown")
    if report.readiness != "automatic" and not allow_partial:
        raise YamlThemeMigrationError(
            f"Theme requires {report.readiness} migration; use --allow-partial to convert only supported overlays"
        )
    document = _load_document(report.source)
    output_root.mkdir(parents=True, exist_ok=False)
    (output_root / "source").mkdir()
    shutil.copy2(report.source, output_root / "source" / "theme.yaml")

    theme_name = converted_theme_name(report.theme_name)
    used_ids: set[str] = set()
    converted: list[str] = []
    skipped: list[str] = []
    styles_with_nodes: list[tuple[HtmlVisualElementStyle, Mapping[str, Any]]] = []
    for candidate in report.visible_overlays:
        label = ".".join(candidate.path)
        if candidate.status != "ready":
            skipped.append(label)
            continue
        node = _value_at(document, candidate.path)
        element_id = _overlay_id(candidate, used_ids)
        style = _style_from_candidate(
            candidate,
            node,
            report,
            element_id,
            1000 + len(styles_with_nodes),
        )
        styles_with_nodes.append((style, node))
        converted.append(label)
    if not styles_with_nodes:
        raise YamlThemeMigrationError("Theme has no directly convertible visible overlays")

    static_markup, static_css, static_assets = _static_layers(
        document,
        report,
        output_root,
    )
    font_css, font_assets = _font_rules(styles_with_nodes, report, output_root)
    warnings = list(report.warnings)
    native_video = _native_video_manifest(
        document,
        report,
        output_root,
        warnings,
    )
    preview = report.source.parent / "preview.png"
    if preview.is_file():
        shutil.copy2(preview, output_root / "preview.png")

    widgets = tuple(
        HtmlGeneratedWidget(
            element_id=style.element_id,
            binding=style.binding,
            formatter=style.formatter,
            sample=style.sample,
            kind=style.element_kind,
        )
        for style, _node in styles_with_nodes
    )
    static_block = "\n".join(static_markup) or "    <!-- No static YAML layers. -->"
    widget_block = render_generated_widget_block(widgets)
    index = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width={report.width},height={report.height},initial-scale=1">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' data:; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'none'; media-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'">
  <title>{html.escape(report.theme_name)} — converted HTML draft</title>
  <link rel="stylesheet" href="style.css">
  <link rel="stylesheet" href="{EDITOR_STYLESHEET_FILENAME}">
</head>
<body>
  <main id="theme-canvas" aria-label="Converted system monitor theme">
{static_block}
  </main>
{widget_block}
</body>
</html>
"""
    (output_root / "index.html").write_text(index, encoding="utf-8")
    base_css = "\n".join(
        [
            "/* Generated draft. Safe to edit in an IDE. */",
            "* { box-sizing: border-box; }",
            f"html, body {{ margin: 0; width: {report.width}px; height: {report.height}px; overflow: hidden; background: transparent; }}",
            f"#theme-canvas {{ position: fixed; inset: 0; width: {report.width}px; height: {report.height}px; overflow: hidden; }}",
            ".static-layer, .static-label { position: absolute; display: block; }",
            ".static-label { line-height: 1.1; white-space: nowrap; }",
            *font_css,
            *static_css,
        ]
    ) + "\n"
    (output_root / "style.css").write_text(base_css, encoding="utf-8")
    (output_root / EDITOR_STYLESHEET_FILENAME).write_text(
        render_visual_stylesheet(style for style, _node in styles_with_nodes),
        encoding="utf-8",
    )
    (output_root / "theme-editor-widgets.js").write_text(
        render_widget_runtime_script(),
        encoding="utf-8",
    )

    initial_overlay = {
        "format": OVERLAY_DOCUMENT_FORMAT,
        "formatVersion": OVERLAY_DOCUMENT_FORMAT_VERSION,
        "schemaVersion": EDITOR_SCHEMA_VERSION,
        "display": {"width": report.width, "height": report.height},
        "elements": [],
    }
    (output_root / OVERLAY_DOCUMENT_FILENAME).write_text(
        json.dumps(initial_overlay, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_payload: dict[str, Any] = {
        "engine": "html",
        "name": f"{report.theme_name} (HTML draft)",
        "version": 1,
        "display": {"width": report.width, "height": report.height},
        "refreshRate": 1,
        "entrypoint": "index.html",
        "overlayDocument": OVERLAY_DOCUMENT_FILENAME,
        "permissions": ["sensors"],
        "network": False,
        "dataUpdateIntervals": {
            "default": 1,
            **{style.binding: 1 for style, _node in styles_with_nodes},
        },
        "atomicRegions": [
            {
                "name": f"overlay:{style.element_id}",
                "x": style.x,
                "y": style.y,
                "width": style.width,
                "height": style.height,
            }
            for style, _node in styles_with_nodes
        ],
    }
    if native_video is not None:
        manifest_payload["nativeVideoOverlay"] = native_video
    (output_root / "manifest.json").write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = ThemeManifest.load(output_root)
    styles = tuple(
        style.validated(manifest) for style, _node in styles_with_nodes
    )
    (output_root / OVERLAY_DOCUMENT_FILENAME).write_text(
        render_overlay_document(manifest, styles),
        encoding="utf-8",
    )

    conversion_payload = report.as_dict()
    conversion_payload["source"] = "source/theme.yaml"
    conversion_payload["sourceTheme"] = report.theme_name
    conversion_payload["conversion"] = {
        "converted": converted,
        "skipped": skipped,
        "allowPartial": allow_partial,
        "nativeVideoIncluded": native_video is not None,
        "copiedAssets": sorted({*static_assets, *font_assets}),
        "warnings": list(dict.fromkeys(warnings)),
    }
    (output_root / "migration-report.json").write_text(
        json.dumps(conversion_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_root / "README.md").write_text(
        "# Converted HTML theme draft\n\n"
        f"Source theme: `{report.theme_name}` (`source/theme.yaml`)\n\n"
        f"Converted overlays: {len(converted)}  \n"
        f"Skipped overlays: {len(skipped)}\n\n"
        "Review `migration-report.json`, compare the preview with the YAML theme, "
        "and keep the original YAML theme until physical validation is complete.\n",
        encoding="utf-8",
    )
    ThemeManifest.load(output_root)
    return (
        theme_name,
        tuple(converted),
        tuple(skipped),
        tuple(dict.fromkeys(warnings)),
    )


def convert_yaml_theme(
    source: str | Path,
    destination: str | Path,
    *,
    allow_partial: bool = False,
) -> YamlThemeConversionResult:
    """Create a new HTML directory or `.theme`; never overwrite either side."""

    report = analyze_yaml_theme(source)
    target = Path(destination).expanduser().resolve()
    packaged = target.suffix.casefold() == ".theme"
    if target.exists():
        raise FileExistsError(f"Conversion destination already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{target.stem or 'theme'}.convert-",
            dir=str(target.parent),
        )
    )
    workspace = temporary / "theme"
    try:
        theme_name, converted, skipped, warnings = _write_converted_directory(
            report,
            workspace,
            allow_partial=allow_partial,
        )
        if packaged:
            descriptor = ThemePackageDescriptor(
                name=theme_name,
                engine="html",
                definition="manifest.json",
            )
            write_theme_package(workspace, target, descriptor)
        else:
            os.replace(workspace, target)
        return YamlThemeConversionResult(
            source=report.source,
            output=target,
            packaged=packaged,
            theme_name=theme_name,
            converted=converted,
            skipped=skipped,
            warnings=warnings,
        )
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
